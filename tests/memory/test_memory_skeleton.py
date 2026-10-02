"""Walking skeleton for shared memory: remember, recall and report end to end."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx
from fakes import FailingEmbedder, FakeEmbedder
from sqlalchemy import insert, select

from dropmcp.memory.context import MemoryContext
from dropmcp.memory.keys import KEY_ALPHABET, is_valid_key, new_key
from dropmcp.memory.search import rrf_merge
from dropmcp.memory.store import (
    memory_recall_log_table,
    memory_report_table,
    memory_table,
    memory_to_dict,
    report_to_dict,
)
from dropmcp.memory.vectors import cosine
from dropmcp.memory.vocabulary import DEFAULT_VOCABULARY

MEMORY_TOOLS = {"memory_remember", "memory_recall", "memory_report"}
PAYMENTS = {"repo": "example-org/payments-api", "language": "csharp"}
_KEY_IN_TEXT = re.compile(r"\[(MEM-[A-Z0-9]{6})\]")


async def _remember(mem, context=None, title="Validation failures return HTTP 200"):
    text = await mem.remember(
        context=PAYMENTS if context is None else context,
        kind="gotcha",
        title=title,
        body="Check the error body; the status code stays 200.",
    )
    match = _KEY_IN_TEXT.search(text)
    assert match is not None, text
    return match.group(1)


def _memory_row(mem, key):
    return mem.sql("SELECT * FROM memory WHERE key = :key", key=key)[0]


async def test_memory_tools_hidden_when_flag_is_off(memory_server):
    async with memory_server(memory_enabled=False) as mem:
        assert MEMORY_TOOLS.isdisjoint(await mem.list_tools())
        assert "memory_recall" not in (mem.instructions or "")


async def test_memory_tools_and_instructions_present_when_flag_is_on(memory_server):
    async with memory_server() as mem:
        assert MEMORY_TOOLS <= set(await mem.list_tools())
        assert "## Shared memory" in mem.instructions


async def test_catalog_reports_memory_enabled(memory_server):
    async with memory_server(ui_enabled=True) as mem:
        transport = httpx.ASGITransport(app=mem.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as http:
            catalog = await http.get("/catalog")
        assert catalog.json()["memory_enabled"] is True


async def test_remembered_memory_is_recalled_in_its_repo(memory_server):
    async with memory_server() as mem:
        key = await _remember(mem)
        assert is_valid_key(key)

        text = await mem.recall(context={"repo": "example-org/payments-api"})

        assert f"\n[{key}] Validation failures return HTTP 200\n" in text
        row = _memory_row(mem, key)
        assert row["created_by"] == "agent@example.com"
        assert row["server"] == mem.settings.name
        assert row["status"] == "active"


async def test_recall_excludes_conflicting_repo_and_includes_no_repo(memory_server):
    async with memory_server() as mem:
        key = await _remember(mem)

        other = await mem.recall(context={"repo": "example-org/other"})
        anywhere = await mem.recall()

        assert key not in other
        assert key in anywhere


async def test_general_memory_is_recalled_for_any_repo(memory_server):
    async with memory_server() as mem:
        key = await _remember(mem, context={"language": "csharp"})

        text = await mem.recall(context={"repo": "example-org/anything"})

        assert key in text


async def test_sensitive_report_hides_memory_and_stale_does_not(memory_server):
    async with memory_server() as mem:
        stale_key = await _remember(mem, title="Tests need a roll-forward flag")
        sensitive_key = await _remember(mem, title="Connection details for staging")

        stale = await mem.report(key=stale_key, problem="stale", reason="Removed.")
        sensitive = await mem.report(
            key=sensitive_key.lower(),
            problem="sensitive",
            reason="Contained a credential.",
        )

        assert stale.startswith("Reported (")
        assert sensitive.startswith("Reported (")
        text = await mem.recall(context=PAYMENTS)
        assert stale_key in text
        assert sensitive_key not in text
        assert _memory_row(mem, sensitive_key)["hidden_at"] is not None
        assert _memory_row(mem, stale_key)["hidden_at"] is None
        reports = mem.sql("SELECT memory_id, problem FROM memory_report")
        assert {(r["memory_id"], r["problem"]) for r in reports} == {
            (_memory_row(mem, stale_key)["id"], "stale"),
            (_memory_row(mem, sensitive_key)["id"], "sensitive"),
        }


async def test_report_with_mangled_key_is_stored_unkeyed(memory_server):
    async with memory_server() as mem:
        key = await _remember(mem)
        swapped = KEY_ALPHABET[(KEY_ALPHABET.index(key[-2]) + 1) % len(KEY_ALPHABET)]
        mangled = key[:-2] + swapped + key[-1]

        text = await mem.report(
            key=mangled,
            memory="Said validation failures return HTTP 200",
            problem="sensitive",
            reason="Contained a hostname.",
            context={"repo": "example-org/payments-api"},
        )

        assert text.startswith("Reported (")
        report = report_to_dict(mem.sql(select(memory_report_table))[0])
        assert report["memory_id"] is None
        assert report["reported_key"] == mangled
        assert report["described_memory"] == "Said validation failures return HTTP 200"
        assert report["context"] == {"repo": "example-org/payments-api"}
        assert key in report["candidate_keys"]
        assert _memory_row(mem, key)["hidden_at"] is None


async def test_every_recall_writes_one_log_row_with_returned_ids(memory_server):
    async with memory_server() as mem:
        key = await _remember(mem)
        memory_id = _memory_row(mem, key)["id"]

        await mem.recall(context=PAYMENTS, query="validation status")
        await mem.recall(context={"repo": "example-org/other"})

        logs = mem.sql(
            select(memory_recall_log_table).order_by(
                memory_recall_log_table.c.had_query.desc()
            )
        )
        assert [(log["had_query"], log["returned_ids"]) for log in logs] == [
            (True, [memory_id]),
            (False, []),
        ]
        assert logs[0]["created_by"] == "agent@example.com"
        assert MemoryContext.from_json(logs[1]["context"]).repo == "example-org/other"
        assert _memory_row(mem, key)["recall_count"] == 1


async def test_unknown_language_is_refused_and_nothing_stored(memory_server):
    async with memory_server() as mem:
        text = await mem.remember(
            context={"repo": "example-org/payments-api", "language": "cobol"},
            kind="gotcha",
            title="Something",
            body="Something else.",
        )

        assert text.startswith("Memory not stored:")
        assert "language 'cobol'" in text
        assert mem.sql("SELECT COUNT(*) AS n FROM memory")[0]["n"] == 0


async def test_failing_embedder_still_stores_memory(memory_server):
    async with memory_server(memory_embedder=FailingEmbedder()) as mem:
        key = await _remember(mem)

        row = _memory_row(mem, key)
        assert row["embedding"] is None
        assert row["embedding_model"] is None
        assert row["embedding_dim"] is None


async def test_embedder_embeds_memory_at_write_time(memory_server):
    async with memory_server(memory_embedder=FakeEmbedder()) as mem:
        key = await _remember(mem)

        row = _memory_row(mem, key)
        assert len(row["embedding"]) == 64 * 4
        assert row["embedding_model"] == "fake-concepts-v1"
        assert row["embedding_dim"] == 64


async def test_memory_to_dict_has_every_column(memory_server):
    async with memory_server() as mem:
        key = await _remember(
            mem,
            context={**PAYMENTS, "stack": ["NUnit", "dotnet", "nunit"], "task": "test"},
        )

        data = memory_to_dict(mem.sql(select(memory_table))[0])

        columns = {column.name for column in memory_table.columns}
        assert set(data) == columns - {"embedding"} | {"has_embedding"}
        assert data["key"] == key
        assert data["stack"] == ["nunit", "dotnet"]
        assert data["has_embedding"] is False
        assert data["created_at"].endswith("Z")
        assert data["hidden_at"] is None


async def test_report_to_dict_has_every_column(memory_server):
    async with memory_server() as mem:
        candidates = [new_key(), new_key()]
        created_at = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)
        mem.sql(
            insert(memory_report_table).values(
                id="report-1",
                created_at=created_at,
                last_seen_at=created_at,
                model="test-model",
                candidate_keys=candidates,
                problem="stale",
                context='{"repo":"example-org/payments-api"}',
                fingerprint="f" * 64,
                occurrence_count=1,
                status="open",
            )
        )

        data = report_to_dict(mem.sql(select(memory_report_table))[0])

        assert set(data) == {column.name for column in memory_report_table.columns}
        assert data["candidate_keys"] == candidates
        assert data["created_at"] == "2026-10-02T10:00:00Z"
        assert data["context"] == {"repo": "example-org/payments-api"}


def test_key_check_char_catches_every_one_character_change():
    for body in ("MEM-7K3F9", "MEM-22222", "MEM-ZZZZZ", new_key()[:-1]):
        checks = [char for char in KEY_ALPHABET if is_valid_key(body + char)]
        assert len(checks) == 1
        valid = body + checks[0]
        assert is_valid_key(valid.lower())
        for position in range(len("MEM-"), len(valid)):
            for char in KEY_ALPHABET:
                if char == valid[position]:
                    continue
                changed = valid[:position] + char + valid[position + 1 :]
                assert not is_valid_key(changed), changed


def test_memory_context_json_round_trip():
    context = MemoryContext.from_arguments(
        {
            "repo": "  Example-Org/Payments-API ",
            "language": "CSharp",
            "stack": ["React", "vite", "react"],
            "task": "test",
            "path": "src/Api",
        },
        DEFAULT_VOCABULARY,
    )

    assert context.repo == "example-org/payments-api"
    assert context.stack == ("react", "vite")
    assert MemoryContext.from_json(context.to_json()) == context
    assert context.to_json() == (
        '{"language":"csharp","path":"src/Api","repo":"example-org/payments-api",'
        '"stack":["react","vite"],"task":"test"}'
    )
    assert context.render_line() == (
        "repo=example-org/payments-api language=csharp stack=react,vite "
        "task=test path=src/Api"
    )
    assert MemoryContext.from_arguments(None, DEFAULT_VOCABULARY) == MemoryContext()
    assert MemoryContext.from_json(MemoryContext().to_json()) == MemoryContext()


def test_rrf_merge_sums_reciprocal_ranks_across_lists():
    scores = rrf_merge([["a", "b", "c"], ["b", "d"]])

    assert scores == {
        "a": 1 / 61,
        "b": 1 / 62 + 1 / 61,
        "c": 1 / 63,
        "d": 1 / 62,
    }
    assert max(scores, key=scores.__getitem__) == "b"


def test_fake_embedder_scores_paraphrases_high_and_unrelated_text_low():
    embedder = FakeEmbedder()

    def score(first, second):
        a, b = embedder.embed([first, second])
        return cosine(a, b)

    assert score("tests fail locally", "specs break on my laptop") >= 0.92
    assert score("service startup error", "service boot fails") >= 0.92
    assert score("tests fail locally", "deploy pipeline uses helm charts") < 0.5
