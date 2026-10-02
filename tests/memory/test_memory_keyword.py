"""Keyword recall: exact tokens via FTS5 on SQLite and tsvector on Postgres."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, insert

from dropmcp.memory.keyword import (
    ensure_sqlite_fts,
    keyword_candidate_ids,
    keyword_ranked,
)
from dropmcp.memory.store import memory_table, metadata

PAYMENTS = {"repo": "example-org/payments-api", "language": "csharp"}
_KEY_IN_TEXT = re.compile(r"\[(MEM-[A-Z0-9]{6})\]")
_PUNCTUATION_QUERIES = (
    'foo(bar) -x OR "*',
    "C++",
    "a:b",
    "",
)


async def _remember(mem, *, title, body="Stored for keyword recall.", context=None):
    text = await mem.remember(
        context=PAYMENTS if context is None else context,
        kind="gotcha",
        title=title,
        body=body,
    )
    match = _KEY_IN_TEXT.search(text)
    assert match is not None, text
    return match.group(1)


def _keys(text: str) -> list[str]:
    return _KEY_IN_TEXT.findall(text)


def _id_for(mem, key: str) -> str:
    return mem.sql("SELECT id FROM memory WHERE key = :key", key=key)[0]["id"]


async def test_recall_query_returns_the_matching_memory_first(memory_server):
    async with memory_server() as mem:
        match = await _remember(mem, title="Enable DOTNET_ROLL_FORWARD in CI")
        other_a = await _remember(mem, title="Cache nuget packages locally")
        other_b = await _remember(mem, title="Prefer explicit package versions")

        text = await mem.recall(context=PAYMENTS, query="DOTNET_ROLL_FORWARD")

        found = _keys(text)
        assert found[0] == match
        assert other_a not in found
        assert other_b not in found
        ids = [_id_for(mem, key) for key in (match, other_a, other_b)]
        assert keyword_ranked(mem.engine, "DOTNET_ROLL_FORWARD", ids) == [ids[0]]


async def test_recall_query_finds_a_token_in_the_body(memory_server):
    async with memory_server() as mem:
        match = await _remember(
            mem,
            title="Compiler warning during build",
            body="Treat CS8618 nullable as an error in the project file.",
        )
        other = await _remember(
            mem,
            title="Cache nuget packages locally",
            body="Keep packages on disk.",
        )

        text = await mem.recall(context=PAYMENTS, query="CS8618 nullable")

        found = _keys(text)
        assert found[0] == match
        assert other not in found


async def test_recall_query_matches_any_shared_token(memory_server):
    async with memory_server() as mem:
        match = await _remember(
            mem,
            title="Nullable reference warning",
            body="The project sets CS8618 as an error.",
        )
        other = await _remember(
            mem,
            title="Cache nuget packages locally",
            body="Keep packages on disk.",
        )

        text = await mem.recall(
            context=PAYMENTS,
            query="how do I fix CS8618 nullable references in a new service",
        )

        found = _keys(text)
        assert match in found
        assert other not in found


async def test_recall_query_excludes_hidden_superseded_and_other_repos(
    memory_server,
):
    async with memory_server() as mem:
        active = await _remember(mem, title="ZEBRA_TOKEN belongs in this service")
        hidden = await _remember(mem, title="ZEBRA_TOKEN was hidden")
        superseded = await _remember(mem, title="ZEBRA_TOKEN was replaced")
        other = await _remember(
            mem,
            title="ZEBRA_TOKEN lives elsewhere",
            context={"repo": "example-org/other"},
        )
        reported = await mem.report(
            key=hidden, problem="sensitive", reason="Contained a credential."
        )
        assert reported.startswith("Reported (")
        mem.sql(
            "UPDATE memory SET status = 'superseded' WHERE key = :key",
            key=superseded,
        )

        text = await mem.recall(context=PAYMENTS, query="ZEBRA_TOKEN")

        found = _keys(text)
        assert active in found
        assert hidden not in found
        assert superseded not in found
        assert other not in found


async def test_punctuation_queries_return_without_error(memory_server):
    async with memory_server() as mem:
        key = await _remember(mem, title="Ordinary setup note")
        memory_id = _id_for(mem, key)
        ensure_sqlite_fts(mem.engine)

        for query in _PUNCTUATION_QUERIES:
            text = await mem.recall(context=PAYMENTS, query=query)
            assert "could not be recalled" not in text
            assert isinstance(keyword_candidate_ids(mem.engine, query, 5), list)
            assert isinstance(
                keyword_ranked(mem.engine, query, [memory_id]), list
            )


async def test_keyword_candidate_ids_respects_the_candidate_cap(memory_server):
    async with memory_server(memory_candidate_cap=2) as mem:
        titles = (
            "Alpha note mentions SHARED_TOKEN",
            "Beta note mentions SHARED_TOKEN",
            "Gamma note mentions SHARED_TOKEN",
            "Delta note mentions SHARED_TOKEN",
            "Epsilon note mentions SHARED_TOKEN",
        )
        keys = [await _remember(mem, title=title) for title in titles]
        stored = {_id_for(mem, key) for key in keys}

        ids = keyword_candidate_ids(
            mem.engine, "SHARED_TOKEN", mem.settings.memory_candidate_cap
        )

        assert len(ids) == 2
        assert set(ids) <= stored


async def test_sqlite_title_update_changes_what_fts_finds(memory_server, backend):
    if backend != "sqlite":
        pytest.skip("FTS5 sync triggers are SQLite-only")
    async with memory_server() as mem:
        key = await _remember(mem, title="ALPHA_TOKEN in the title")
        memory_id = _id_for(mem, key)
        assert keyword_candidate_ids(mem.engine, "ALPHA_TOKEN", 5) == [memory_id]

        mem.sql(
            "UPDATE memory SET title = :title WHERE key = :key",
            title="BETA_TOKEN in the title",
            key=key,
        )

        assert keyword_candidate_ids(mem.engine, "ALPHA_TOKEN", 5) == []
        assert keyword_candidate_ids(mem.engine, "BETA_TOKEN", 5) == [memory_id]


def test_sqlite_fts_rebuilds_rows_already_stored(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'memory.db'}", future=True)
    metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(
            insert(memory_table).values(
                id="id-already-stored",
                key="MEM-REBUILD1",
                created_at=now,
                server="test",
                last_confirmed_at=now,
                kind="gotcha",
                title="Already stored REBUILD_TOKEN",
                body="Present before the index.",
                stack=[],
                fingerprint="fp",
                model="test-model",
            )
        )
    try:
        ensure_sqlite_fts(engine)
        ensure_sqlite_fts(engine)
        assert keyword_candidate_ids(engine, "REBUILD_TOKEN", 5) == [
            "id-already-stored"
        ]
    finally:
        engine.dispose()
