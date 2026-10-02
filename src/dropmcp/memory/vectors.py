"""Embeddings: the injected embedder, float32 packing and cosine scoring."""

from __future__ import annotations

import logging
import math
import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from dropmcp.memory.context import MemoryContext

logger = logging.getLogger(__name__)

try:
    import numpy as _numpy
except ImportError:
    _numpy = None

# Tests force the pure-Python scorer by monkeypatching this flag.
use_numpy = _numpy is not None


@dataclass(frozen=True)
class MemoryEmbedder:
    embed: Callable[[list[str]], list[list[float]]]
    model: str
    dimension: int
    near_duplicate_threshold: float = 0.92


def pack(vector: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def unpack(data: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(data) // 4}f", data))


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if _numpy_enabled():
        return _cosine_numpy(a, b)
    return _cosine_python(a, b)


def _numpy_enabled() -> bool:
    return bool(use_numpy) and _numpy is not None


def _cosine_python(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _cosine_numpy(a: Sequence[float], b: Sequence[float]) -> float:
    left = _numpy.asarray(a, dtype=_numpy.float64)
    right = _numpy.asarray(b, dtype=_numpy.float64)
    width = min(int(left.size), int(right.size))
    dot = float(_numpy.dot(left[:width], right[:width]))
    denom = float(_numpy.linalg.norm(left) * _numpy.linalg.norm(right))
    if denom == 0.0:
        return 0.0
    return dot / denom


def _batch_cosine(query: Sequence[float], rows: list[list[float]]) -> list[float]:
    if not rows:
        return []
    if _numpy_enabled():
        matrix = _numpy.asarray(rows, dtype=_numpy.float64)
        query_vec = _numpy.asarray(query, dtype=_numpy.float64)
        dots = matrix @ query_vec
        denom = _numpy.linalg.norm(matrix, axis=1) * _numpy.linalg.norm(query_vec)
        scores = _numpy.zeros(len(rows), dtype=_numpy.float64)
        _numpy.divide(dots, denom, out=scores, where=denom != 0)
        return [float(score) for score in scores]
    return [_cosine_python(query, row) for row in rows]


def embed_text(title: str, body: str, context: MemoryContext) -> str:
    return f"{title}\n{body}\n{context.render_line()}"


def safe_embed(
    embedder: MemoryEmbedder | None, texts: list[str]
) -> list[list[float]] | None:
    if embedder is None:
        return None
    try:
        vectors = embedder.embed(texts)
        if len(vectors) != len(texts) or any(
            len(vector) != embedder.dimension for vector in vectors
        ):
            raise ValueError(
                f"embedder {embedder.model} returned vectors of the wrong shape"
            )
        return [[float(value) for value in vector] for vector in vectors]
    except Exception:
        logger.exception("Memory embedding failed; continuing without vectors")
        return None


def vector_ranked(
    candidates: list[dict[str, Any]],
    query: str | None,
    context: MemoryContext,
    embedder: MemoryEmbedder | None,
) -> list[str]:
    if embedder is None or query is None or not query.strip():
        return []
    embedded = safe_embed(embedder, [query])
    if not embedded:
        return []
    scored: list[tuple[str, list[float]]] = []
    for row in candidates:
        vector = _stored_vector(row, embedder)
        if vector is not None:
            scored.append((row["id"], vector))
    if not scored:
        return []
    similarities = _batch_cosine(embedded[0], [vector for _, vector in scored])
    order = sorted(
        range(len(scored)), key=lambda index: similarities[index], reverse=True
    )
    return [scored[index][0] for index in order]


def _stored_vector(
    row: dict[str, Any], embedder: MemoryEmbedder
) -> list[float] | None:
    if row.get("embedding_model") != embedder.model:
        return None
    if row.get("embedding_dim") != embedder.dimension:
        return None
    raw = row.get("embedding")
    if isinstance(raw, memoryview):
        data = raw.tobytes()
    elif isinstance(raw, (bytes, bytearray)):
        data = bytes(raw)
    else:
        return None
    if len(data) != embedder.dimension * 4:
        return None
    return unpack(data)
