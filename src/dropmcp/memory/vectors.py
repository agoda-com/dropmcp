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
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


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
    # TODO(S5): cosine of the query embedding against each candidate, best first.
    return []
