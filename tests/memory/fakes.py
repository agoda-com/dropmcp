"""Test doubles for the memory embedder."""

from __future__ import annotations

import hashlib
import re

from dropmcp.memory.vectors import MemoryEmbedder

FAKE_DIMENSION = 64

_SYNONYMS = {
    "fail": "failure",
    "fails": "failure",
    "failing": "failure",
    "failure": "failure",
    "break": "failure",
    "breaks": "failure",
    "broken": "failure",
    "error": "failure",
    "errors": "failure",
    "crash": "failure",
    "crashes": "failure",
    "start": "startup",
    "starts": "startup",
    "startup": "startup",
    "boot": "startup",
    "boots": "startup",
    "booting": "startup",
    "test": "test",
    "tests": "test",
    "testing": "test",
    "spec": "test",
    "specs": "test",
    "local": "local",
    "locally": "local",
    "laptop": "local",
    "http": "http",
    "status": "http",
    "response": "http",
    "responses": "http",
}
_STOPWORDS = {
    "a", "an", "the", "on", "in", "my", "of", "to", "with", "is", "are", "when",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def concepts(text: str) -> list[str]:
    return [
        _SYNONYMS.get(token, token)
        for token in _TOKEN_RE.findall(text.lower())
        if token not in _STOPWORDS
    ]


def _bucket(concept: str) -> int:
    digest = hashlib.sha256(concept.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % FAKE_DIMENSION


def _embed(texts: list[str]) -> list[list[float]]:
    vectors = []
    for text in texts:
        vector = [0.0] * FAKE_DIMENSION
        for concept in set(concepts(text)):
            vector[_bucket(concept)] += 1.0
        vectors.append(vector)
    return vectors


def FakeEmbedder() -> MemoryEmbedder:
    """Deterministic bag-of-concepts embedder.

    Tokens are lower-cased, stopwords dropped, and synonyms mapped to one
    concept; each concept adds 1 to a bucket picked by sha256. Paraphrases that
    share their concepts score high:

    - "tests fail locally" / "specs break on my laptop" -> cosine >= 0.92
    - "service startup error" / "service boot fails" -> cosine >= 0.92

    Unrelated text scores low:

    - "tests fail locally" / "deploy pipeline uses helm charts" -> cosine < 0.5
    """
    return MemoryEmbedder(embed=_embed, model="fake-concepts-v1", dimension=FAKE_DIMENSION)


def _fail(texts: list[str]) -> list[list[float]]:
    raise RuntimeError("embedder unavailable")


def FailingEmbedder() -> MemoryEmbedder:
    """An embedder whose every call raises."""
    return MemoryEmbedder(embed=_fail, model="failing-v1", dimension=FAKE_DIMENSION)
