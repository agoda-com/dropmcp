"""Hybrid recall: cosine over stored embeddings, merged with keyword rank."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest
from sqlalchemy import update

from dropmcp.memory import vectors
from dropmcp.memory.context import MemoryContext
from dropmcp.memory.store import memory_table
from dropmcp.memory.vectors import pack, unpack, vector_ranked
from fakes import FailingEmbedder, FakeEmbedder

_KEY = re.compile(r"\[(MEM-[A-Z0-9]{6})\]")
_CONTEXT = {"repo": "example-org/payments-api", "language": "python"}
# Docstring pair: shared concepts, no shared keyword tokens.
_STORED = "tests fail locally"
_QUERY = "specs break on my laptop"
_DISTRACTOR = "deploy pipeline uses helm charts"
_STAMP = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


async def _remember(mem, *, title: str, body: str, context: dict | None = None) -> str:
    text = await mem.remember(
        context=context if context is not None else _CONTEXT,
        kind="gotcha",
        title=title,
        body=body,
    )
    assert text.startswith("Remembered ["), text
    match = _KEY.search(text)
    assert match is not None, text
    return match.group(1)


def _update(mem, key: str, **values) -> None:
    mem.sql(update(memory_table).where(memory_table.c.key == key).values(**values))


def _id(mem, key: str) -> str:
    rows = mem.sql("SELECT id FROM memory WHERE key = :key", key=key)
    assert len(rows) == 1
    return rows[0]["id"]


def _embedded(embedder, row_id: str, text: str, **overrides) -> dict:
    vector = embedder.embed([text])[0]
    row = {
        "id": row_id,
        "embedding": pack(vector),
        "embedding_model": embedder.model,
        "embedding_dim": embedder.dimension,
    }
    row.update(overrides)
    return row


def test_stored_and_query_share_no_keyword_tokens():
    assert not (_tokens(_STORED) & _tokens(_QUERY))


def test_pack_unpack_round_trip():
    vector = [0.0, -1.5, 2.25, 0.125, -0.5]
    assert unpack(pack(vector)) == pytest.approx(vector)


def test_vector_ranked_is_empty_without_an_embedder_or_query():
    embedder = FailingEmbedder()
    row = _embedded(FakeEmbedder(), "mem-1", _STORED)
    context = MemoryContext()
    assert vector_ranked([row], _QUERY, context, None) == []
    assert vector_ranked([row], None, context, embedder) == []
    assert vector_ranked([row], "", context, embedder) == []
    assert vector_ranked([row], "   ", context, embedder) == []


def test_vector_ranked_skips_mismatched_or_missing_embeddings():
    embedder = FakeEmbedder()
    context = MemoryContext()
    kept = _embedded(embedder, "kept", _STORED)
    wrong_model = _embedded(embedder, "model", _STORED, embedding_model="other-model")
    wrong_dim = _embedded(embedder, "dim", _STORED, embedding_dim=embedder.dimension + 1)
    missing = _embedded(embedder, "null", _STORED, embedding=None)
    ranked = vector_ranked(
        [wrong_model, missing, wrong_dim, kept], _QUERY, context, embedder
    )
    assert ranked == ["kept"]


def test_numpy_and_python_rank_the_same_inputs(monkeypatch):
    assert vectors.use_numpy is True
    embedder = FakeEmbedder()
    context = MemoryContext()
    candidates = [
        _embedded(embedder, "helm", _DISTRACTOR),
        _embedded(embedder, "boot", "service boot fails"),
        _embedded(embedder, "tests", _STORED),
    ]
    monkeypatch.setattr(vectors, "use_numpy", True)
    numpy_order = vector_ranked(candidates, _QUERY, context, embedder)
    monkeypatch.setattr(vectors, "use_numpy", False)
    python_order = vector_ranked(candidates, _QUERY, context, embedder)
    assert numpy_order == python_order
    assert numpy_order[0] == "tests"


async def test_paraphrase_is_recalled_only_with_an_embedder(memory_server):
    # The distractor has no embedding and more confirmations, so a scope-only
    # fallback at limit 1 hides the paraphrase. A no-hit query that returns
    # nothing hides it too. Either way the embedder has to surface the target.
    async with memory_server(memory_embedder=FailingEmbedder()) as failing:
        distractor = await _remember(failing, title=_DISTRACTOR, body=_DISTRACTOR)
        _update(failing, distractor, occurrence_count=2, last_confirmed_at=_STAMP)

    async with memory_server(memory_embedder=FakeEmbedder()) as mem:
        target = await _remember(mem, title=_STORED, body=_STORED)
        _update(mem, target, occurrence_count=1, last_confirmed_at=_STAMP)
        found = await mem.recall(context=_CONTEXT, query=_QUERY, limit=1)

        assert target in found
        assert distractor not in found

    async with memory_server() as plain:
        missed = await plain.recall(context=_CONTEXT, query=_QUERY, limit=1)

        assert target not in missed


async def test_hybrid_merge_returns_keyword_and_vector_hits(memory_server, monkeypatch):
    async with memory_server(memory_embedder=FakeEmbedder()) as mem:
        keyword_key = await _remember(mem, title=_DISTRACTOR, body=_DISTRACTOR)
        vector_key = await _remember(mem, title=_STORED, body=_STORED)
        keyword_id = _id(mem, keyword_key)

        def ranked(engine, query, candidate_ids):
            return [keyword_id]

        monkeypatch.setattr("dropmcp.memory.keyword.keyword_ranked", ranked)
        text = await mem.recall(context=_CONTEXT, query=_QUERY)

        assert keyword_key in text
        assert vector_key in text


async def test_changed_embedding_model_is_skipped_by_vector_scoring(memory_server):
    async with memory_server(memory_embedder=FakeEmbedder()) as mem:
        changed = await _remember(mem, title=_STORED, body=_STORED)
        kept = await _remember(mem, title="service boot fails", body="service boot fails")
        mem.sql(
            "UPDATE memory SET embedding_model = 'other-model' WHERE key = :key",
            key=changed,
        )
        rows = mem.sql("SELECT * FROM memory")
        ranked = vector_ranked(rows, _QUERY, MemoryContext(**_CONTEXT), FakeEmbedder())

        assert _id(mem, changed) not in ranked
        assert ranked == [_id(mem, kept)]


async def test_null_embedding_is_still_found_by_keyword(memory_server):
    async with memory_server(memory_embedder=FailingEmbedder()) as mem:
        key = await _remember(mem, title=_DISTRACTOR, body=_DISTRACTOR)
        rows = mem.sql(
            "SELECT id, embedding FROM memory WHERE key = :key", key=key
        )
        assert rows[0]["embedding"] is None
        assert vector_ranked(
            mem.sql("SELECT * FROM memory"),
            _DISTRACTOR,
            MemoryContext(**_CONTEXT),
            FakeEmbedder(),
        ) == []

        text = await mem.recall(context=_CONTEXT, query="helm charts")

        assert key in text
        assert "could not be recalled" not in text


async def test_failing_query_embedder_still_returns_keyword_hits(memory_server):
    async with memory_server(memory_embedder=FakeEmbedder()) as writer:
        key = await _remember(writer, title=_DISTRACTOR, body=_DISTRACTOR)

    async with memory_server(memory_embedder=FailingEmbedder()) as reader:
        text = await reader.recall(context=_CONTEXT, query="helm charts")

        assert key in text
        assert "could not be recalled" not in text
