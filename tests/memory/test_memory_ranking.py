"""Recall ranking: scope boost, confirmation quality, limit and character budget."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from dropmcp.memory.context import MemoryContext
from dropmcp.memory.recall import NO_RESULTS, PREFACE
from dropmcp.memory.search import (
    HALF_LIFE_DAYS,
    apply_budget,
    quality_factor,
    render_entry,
    scope_boost,
)
from dropmcp.memory.store import memory_table

_KEY = re.compile(r"\[(MEM-[A-Z0-9]{6})\]")
_SENTENCE = "Validation failures return HTTP 200 with the error in the body."
# Fingerprints drop digits, so twelve memories need distinct words.
_LABELS = (
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "india",
    "juliet",
    "kilo",
    "lima",
)


def _body(size: int) -> str:
    text = _SENTENCE
    while len(text) < size:
        text = f"{text} {_SENTENCE}"
    text = text[:size]
    if text.endswith(" "):
        text = f"{text[:-1]}."
    return text


async def _remember(mem, *, context, title, body):
    text = await mem.remember(
        context=context, kind="gotcha", title=title, body=body
    )
    assert text.startswith("Remembered ["), text
    match = _KEY.search(text)
    assert match is not None, text
    return match.group(1)


def _update(mem, key, **values):
    mem.sql(update(memory_table).where(memory_table.c.key == key).values(**values))


def _row(**fields):
    row = {
        "repo": "",
        "system": "",
        "language": "",
        "domain": "",
        "stack": [],
        "task": "",
        "path": "",
        "occurrence_count": 1,
        "last_confirmed_at": datetime(2026, 10, 2, tzinfo=timezone.utc),
    }
    row.update(fields)
    return row


async def test_recall_orders_repo_then_language_then_general(memory_server):
    caller = {"repo": "example-org/payments-api", "language": "csharp"}
    async with memory_server() as mem:
        repo_key = await _remember(
            mem,
            context={"repo": "example-org/payments-api"},
            title="Repo validation returns HTTP 200",
            body="Read the error body; the status code stays 200.",
        )
        language_key = await _remember(
            mem,
            context={"language": "csharp"},
            title="Language validation returns HTTP 200",
            body="Read the error body; the status code stays 200.",
        )
        general_key = await _remember(
            mem,
            context={},
            title="General validation returns HTTP 200",
            body="Read the error body; the status code stays 200.",
        )

        text = await mem.recall(context=caller)

        assert text.index(repo_key) < text.index(language_key) < text.index(general_key)
        assert "scope: repo=example-org/payments-api\n" in text
        assert "scope: language=csharp\n" in text
        assert "scope: general\n" in text


async def test_recall_ranks_more_confirmations_first(memory_server):
    context = {"repo": "example-org/billing-api", "language": "python"}
    stamp = datetime(2026, 8, 1, tzinfo=timezone.utc)
    async with memory_server() as mem:
        few = await _remember(
            mem,
            context=context,
            title="Few confirmations for the retry header",
            body="The retry header is optional on this route.",
        )
        many = await _remember(
            mem,
            context=context,
            title="Many confirmations for the retry header",
            body="The retry header is optional on this route.",
        )
        _update(mem, few, occurrence_count=1, last_confirmed_at=stamp)
        _update(mem, many, occurrence_count=12, last_confirmed_at=stamp)

        text = await mem.recall(context=context)

        assert text.index(many) < text.index(few)
        assert "confirmations: 12\n" in text
        assert "confirmations: 1\n" in text


async def test_recall_ranks_more_recent_confirmation_first(memory_server):
    context = {"repo": "example-org/ledger-api", "language": "java"}
    async with memory_server() as mem:
        old = await _remember(
            mem,
            context=context,
            title="Older note about settlement cutoff",
            body="Settlement cutoff is 17:00 UTC.",
        )
        recent = await _remember(
            mem,
            context=context,
            title="Newer note about settlement cutoff",
            body="Settlement cutoff is 17:00 UTC.",
        )
        _update(
            mem,
            old,
            occurrence_count=4,
            last_confirmed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        _update(
            mem,
            recent,
            occurrence_count=4,
            last_confirmed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )

        text = await mem.recall(context=context)

        assert text.index(recent) < text.index(old)
        assert "last confirmed: 2026-09-01\n" in text
        assert "last confirmed: 2024-01-01\n" in text
        assert text.count("confirmations: 4\n") == 2


async def test_recall_clamps_limit(memory_server):
    context = {"repo": "example-org/limits-api", "language": "go"}
    async with memory_server() as mem:
        for label in _LABELS:
            await _remember(
                mem,
                context=context,
                title=f"Limit fact {label} about validation",
                body="See the error body.",
            )

        three = await mem.recall(context=context, limit=3)
        fifty = await mem.recall(context=context, limit=50)

        assert len(_KEY.findall(three)) == 3
        assert len(_KEY.findall(fifty)) == 10


async def test_recall_stops_at_the_character_budget(memory_server):
    context = {"repo": "example-org/budget-api", "language": "kotlin"}
    body = _body(1000)
    async with memory_server() as mem:
        for label in _LABELS:
            await _remember(
                mem,
                context=context,
                title=f"Budget fact {label} about validation",
                body=body,
            )

        text = await mem.recall(context=context, limit=10)

        found = _KEY.findall(text)
        assert text.startswith(f"{PREFACE}\n\n")
        assert text.count(PREFACE) == 1
        entries = text[len(PREFACE) + 2 :]
        assert 1 < len(found) < 10
        assert len(entries) <= 4000
        assert text.count(body) == len(found)


async def test_recalled_entry_shows_open_report_count(memory_server):
    context = {"repo": "example-org/reports-api", "language": "python"}
    async with memory_server() as mem:
        key = await _remember(
            mem,
            context=context,
            title="Tests needed a roll-forward flag",
            body="The flag was required for the test host.",
        )
        reported = await mem.report(
            key=key, problem="stale", reason="The flag was removed."
        )

        text = await mem.recall(context=context)

        assert reported.startswith("Reported (")
        assert f"[{key}] Tests needed a roll-forward flag\n" in text
        assert "kind: gotcha\n" in text
        assert "scope: repo=example-org/reports-api language=python\n" in text
        assert re.search(r"age: \d+ days\n", text)
        assert "confirmations: 1\n" in text
        assert "open reports: 1\n" in text


async def test_query_with_no_shared_token_returns_no_results(memory_server):
    context = {"repo": "example-org/payments-api", "language": "csharp"}
    async with memory_server() as mem:
        await _remember(
            mem,
            context=context,
            title="Repo validation returns HTTP 200",
            body="Read the error body; the status code stays 200.",
        )
        stored = await mem.recall(context=context)
        assert "Repo validation returns HTTP 200" in stored

        text = await mem.recall(context=context, query="xylophone")

        assert text == NO_RESULTS
        assert PREFACE not in text


async def test_preface_is_present_once_and_omitted_when_empty(memory_server):
    context = {"repo": "example-org/empty-api"}
    async with memory_server() as mem:
        empty = await mem.recall(context=context)
        assert empty == NO_RESULTS
        assert PREFACE not in empty

        await _remember(
            mem,
            context=context,
            title="Empty repo still has one note",
            body="Read the error body before changing the client.",
        )
        text = await mem.recall(context=context)

        assert text.count(PREFACE) == 1
        assert text.startswith(f"{PREFACE}\n\n")


def test_scope_boost_orders_narrower_scope_above_overlap():
    context = MemoryContext(
        repo="example-org/payments-api",
        system="payments",
        language="csharp",
        domain="billing",
        stack=("pytest", "nunit"),
        task="test",
        path="src/Api/Pay.cs",
    )
    overlap = {"stack": ["pytest", "nunit"], "task": "test", "path": "src/Api"}

    def score(**fields):
        return scope_boost(_row(**fields), context)

    assert score(repo="example-org/payments-api") > score(system="payments", **overlap)
    assert score(system="payments") > score(language="csharp", **overlap)
    assert score(language="csharp") > score(domain="billing", **overlap)
    assert score(domain="billing") > score(**overlap)
    assert score(**overlap) > score()
    assert score(stack=["pytest", "nunit"]) > score(stack=["pytest"])
    assert score(path="src/Api") > score()
    assert score(path="src/ApiOther") == score()
    assert score(repo="example-org/payments-api", language="csharp") > score(
        repo="example-org/payments-api"
    )

    omitted = MemoryContext(repo="example-org/payments-api")
    assert scope_boost(_row(language="csharp"), omitted) == scope_boost(
        _row(), omitted
    )

    broad = MemoryContext(
        domain="billing",
        stack=tuple(f"tag{i}" for i in range(40)),
        task="test",
        path="src/Api/Pay.cs",
    )
    many = _row(stack=[f"tag{i}" for i in range(40)], task="test", path="src/Api")
    assert scope_boost(_row(domain="billing"), broad) > scope_boost(many, broad)


def test_quality_factor_grows_slowly_and_decays_with_age():
    now = datetime(2026, 10, 2, tzinfo=timezone.utc)
    one = quality_factor(_row(occurrence_count=1, last_confirmed_at=now), now)
    fifty = quality_factor(_row(occurrence_count=50, last_confirmed_at=now), now)
    assert fifty > one
    assert fifty < one * 50

    recent = quality_factor(_row(occurrence_count=4, last_confirmed_at=now), now)
    older = quality_factor(
        _row(
            occurrence_count=4,
            last_confirmed_at=now - timedelta(days=HALF_LIFE_DAYS),
        ),
        now,
    )
    assert recent > older
    assert older == pytest.approx(recent / 2)

    ancient = quality_factor(
        _row(
            occurrence_count=1,
            last_confirmed_at=datetime(1, 1, 1, tzinfo=timezone.utc),
        ),
        now,
    )
    assert ancient > 0


def test_apply_budget_truncates_one_oversized_entry_and_clamps_limit():
    created = datetime(2026, 10, 2, tzinfo=timezone.utc)
    huge = {
        "key": "MEM-ABCDEF",
        "title": "Oversized note",
        "kind": "gotcha",
        "body": "y" * 5000,
        "occurrence_count": 1,
        "created_at": created,
        "last_confirmed_at": created,
        "open_reports": 0,
    }
    other = dict(huge)
    other["key"] = "MEM-GGGGGG"
    other["title"] = "Second note"
    other["body"] = "short"

    kept = apply_budget([huge, other], limit=5)

    assert len(kept) == 1
    assert kept[0]["body"].endswith("...")
    assert len(kept[0]["body"]) < 5000
    assert len(render_entry(kept[0])) <= 4000

    short = []
    for index in range(12):
        row = dict(huge)
        row["key"] = f"MEM-{index:06d}"
        row["title"] = f"Note {index}"
        row["body"] = "short"
        short.append(row)
    assert len(apply_budget(short, 50)) == 10
    assert len(apply_budget(short, 3)) == 3
    assert len(apply_budget(short, "nope")) == 5
