"""Operators can list, inspect and delete memories from the catalog admin."""

from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select, update

from dropmcp.memory.store import (
    memory_recall_log_table,
    memory_report_table,
    memory_table,
)

_KEY = re.compile(r"\[(MEM-[A-Z0-9]{6})\]")
PAYMENTS = {"repo": "example-org/payments-api", "language": "csharp"}
LEDGER = {"repo": "example-org/ledger", "language": "python"}
BILLING = {"repo": "example-org/billing", "language": "go"}
USER_EMAIL = "agent@example.com"


@asynccontextmanager
async def _http(mem, *, identified: bool = False):
    transport = httpx.ASGITransport(app=mem.app)
    headers = {mem.settings.user_header: USER_EMAIL} if identified else None
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", headers=headers
    ) as http:
        yield http


def _ids(value) -> list:
    if not value:
        return []
    if isinstance(value, str):
        return json.loads(value)
    return list(value)


def _keys(payload) -> list[str]:
    return [item["key"] for item in payload["items"]]


async def _remember(mem, **kwargs) -> str:
    text = await mem.remember(**kwargs)
    match = _KEY.search(text)
    assert match is not None, text
    return match.group(1)


async def _ok(http, path: str) -> dict:
    response = await http.get(path)
    assert response.status_code == 200, response.text
    return response.json()


async def test_admin_routes_are_absent_without_the_ui(memory_server):
    async with memory_server() as mem:
        async with _http(mem) as http:
            response = await http.get("/api/memory")
        assert response.status_code == 404


async def test_admin_lists_filters_hidden_reports_and_stats(memory_server):
    async with memory_server(ui_enabled=True) as mem:
        payments = await _remember(
            mem,
            context=PAYMENTS,
            kind="gotcha",
            title="Validation failures return HTTP 200",
            body="Check the error body; the status code stays 200.",
            evidence="A failing request still answered 200.",
        )
        confirmed = await mem.remember(
            context=PAYMENTS,
            kind="gotcha",
            title="Validation failures return HTTP 200",
            body="Check the error body; the status code stays 200.",
        )
        assert payments in confirmed
        assert "confirmations: 2" in confirmed

        ledger = await _remember(
            mem,
            context=LEDGER,
            kind="convention",
            title="Ledger rounds half away from zero",
            body="Half amounts round away from zero, not to even.",
        )
        billing_old = await _remember(
            mem,
            context=BILLING,
            kind="decision",
            title="Billing closes the day in local time",
            body="The cutoff follows the server timezone.",
        )
        superseded = await mem.remember(
            context=BILLING,
            kind="howto",
            title="Billing closes the day in UTC",
            body="The cutoff is 00:00 UTC.",
            supersedes=billing_old,
        )
        found = _KEY.findall(superseded)
        assert found[0] != billing_old
        billing_new = found[0]

        stale = await mem.report(
            key=payments,
            problem="stale",
            reason="The status is now 422.",
        )
        assert stale.startswith("Reported")
        hidden = await mem.report(
            key=ledger,
            problem="sensitive",
            reason="It should not have been stored.",
        )
        assert hidden.startswith("Reported")
        unkeyed = await mem.report(
            memory="Retries are always safe.",
            problem="invalid",
            reason="Retries are not always safe.",
            context=LEDGER,
        )
        assert unkeyed.startswith("Reported")

        hit = await mem.recall(context={"repo": "example-org/payments-api"})
        miss = await mem.recall(context={"repo": "example-org/other"})
        assert payments in hit
        assert payments not in miss

        misses = [
            row
            for row in mem.sql(select(memory_recall_log_table))
            if not _ids(row["returned_ids"])
        ]
        assert len(misses) == 1
        mem.sql(
            update(memory_recall_log_table)
            .where(memory_recall_log_table.c.id == misses[0]["id"])
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=10))
        )
        unkeyed_rows = mem.sql(
            select(memory_report_table.c.id).where(
                memory_report_table.c.memory_id.is_(None)
            )
        )
        assert len(unkeyed_rows) == 1
        mem.sql(
            update(memory_report_table)
            .where(memory_report_table.c.id == unkeyed_rows[0]["id"])
            .values(candidate_keys=[payments])
        )
        mem.sql(
            update(memory_table)
            .where(memory_table.c.key == ledger)
            .values(created_by="other@example.com")
        )

        async with _http(mem, identified=True) as http:
            listed = await _ok(http, "/api/memory")
            assert _keys(listed)[0] == payments
            assert set(_keys(listed)) == {payments, ledger, billing_old, billing_new}
            payments_item = next(
                item for item in listed["items"] if item["key"] == payments
            )
            assert payments_item["confirmations"] == 2
            assert payments_item["confirmations_label"] == "2 confirmations"
            assert payments_item["open_reports"] == 1
            assert payments_item["scope"] == (
                "example-org/payments-api · csharp"
            )
            assert payments_item["hidden"] is False
            ledger_item = next(
                item for item in listed["items"] if item["key"] == ledger
            )
            assert ledger_item["hidden"] is True
            assert ledger_item["hidden_label"] == "Hidden"

            assert _keys(await _ok(http, "/api/memory?hidden=true")) == [ledger]
            assert payments in _keys(await _ok(http, "/api/memory?hidden=false"))
            assert ledger not in _keys(await _ok(http, "/api/memory?hidden=false"))
            assert _keys(
                await _ok(http, "/api/memory?repo=example-org/payments-api")
            ) == [payments]
            assert _keys(await _ok(http, "/api/memory?language=python")) == [ledger]
            assert _keys(await _ok(http, "/api/memory?kind=decision")) == [
                billing_old
            ]
            assert _keys(await _ok(http, "/api/memory?status=superseded")) == [
                billing_old
            ]
            assert _keys(await _ok(http, "/api/memory?search=error%20body")) == [
                payments
            ]
            assert _keys(await _ok(http, "/api/memory?search=Ledger")) == [ledger]
            recent = await _ok(http, "/api/memory?sort=recent")
            assert _keys(recent)[0] == billing_new

            detail = await _ok(http, f"/api/memory/{payments}")
            assert detail["memory"]["body"].startswith("Check the error body")
            assert detail["memory"]["evidence"].startswith("A failing request")
            assert [report["problem"] for report in detail["reports"]] == ["stale"]

            missing = await http.get("/api/memory/MEM-NOSUCH")
            assert missing.status_code == 404

            reports = await _ok(http, "/api/memory/reports")
            unkeyed_item = next(
                item for item in reports["items"] if item["keyed"] is False
            )
            assert unkeyed_item["described_memory"] == "Retries are always safe."
            assert unkeyed_item["candidate_keys"] == [payments]
            assert unkeyed_item["candidate_keys_label"] == payments
            assert any(
                item["keyed"] and item["memory_key"] == payments
                for item in reports["items"]
            )

            stats = await _ok(http, "/api/memory/stats")
            week, month = stats["periods"]
            assert week["days"] == 7
            assert week["recall_count"] == 1
            assert week["recalls_with_results"] == 1
            assert week["recalls_without_results"] == 0
            assert week["share_returning"] == "100%"
            assert week["report_count"] == 3
            assert week["reports_per_recall"] == "3"
            assert week["distinct_writers"] == 2
            assert month["days"] == 30
            assert month["recall_count"] == 2
            assert month["recalls_with_results"] == 1
            assert month["recalls_without_results"] == 1
            assert month["share_returning"] == "50%"
            assert month["reports_per_recall"] == "1.5"
            assert month["distinct_writers"] == 2


@pytest.mark.parametrize(
    "path",
    [
        "/api/memory",
        "/api/memory?hidden=true",
        "/api/memory/reports",
        "/api/memory/stats",
        "/api/memory/{key}",
    ],
)
async def test_admin_reads_require_header_so_hidden_memories_stay_hidden(
    memory_server, path
):
    async with memory_server(ui_enabled=True) as mem:
        hidden = await _remember(
            mem,
            context=LEDGER,
            kind="setup",
            title="Staging database uses the shared service login",
            body="Connect with the shared service login from the vault entry.",
        )
        reported = await mem.report(
            key=hidden,
            problem="sensitive",
            reason="It should not have been stored.",
        )
        assert reported.startswith("Reported")
        url = path.format(key=hidden)

        async with _http(mem) as http:
            denied = await http.get(url)
        async with _http(mem, identified=True) as http:
            allowed = await http.get(url)

        assert denied.status_code == 401
        assert denied.json() == {"error": "identity header required"}
        assert "shared service login" not in denied.text
        assert allowed.status_code == 200


async def test_admin_delete_requires_header_and_removes_memory(memory_server):
    async with memory_server(ui_enabled=True) as mem:
        payments = await _remember(
            mem,
            context=PAYMENTS,
            kind="gotcha",
            title="Validation failures return HTTP 200",
            body="Check the error body; the status code stays 200.",
        )
        billing_old = await _remember(
            mem,
            context=BILLING,
            kind="decision",
            title="Billing closes the day in local time",
            body="The cutoff follows the server timezone.",
        )
        superseded = await mem.remember(
            context=BILLING,
            kind="howto",
            title="Billing closes the day in UTC",
            body="The cutoff is 00:00 UTC.",
            supersedes=billing_old,
        )
        billing_new = _KEY.findall(superseded)[0]
        reported = await mem.report(
            key=payments,
            problem="stale",
            reason="The status is now 422.",
        )
        assert reported.startswith("Reported")
        recalled = await mem.recall(context={"repo": "example-org/payments-api"})
        assert payments in recalled
        payments_id = mem.sql(
            select(memory_table.c.id).where(memory_table.c.key == payments)
        )[0]["id"]
        header = {mem.settings.user_header: "agent@example.com"}

        async with _http(mem) as http:
            denied = await http.delete(f"/api/memory/{payments}")
            assert denied.status_code == 401
            still_there = await http.get(f"/api/memory/{payments}", headers=header)
            assert still_there.status_code == 200

            unknown = await http.delete("/api/memory/MEM-NOSUCH", headers=header)
            assert unknown.status_code == 404

            removed_new = await http.delete(
                f"/api/memory/{billing_new}", headers=header
            )
            assert removed_new.status_code == 200
            old_row = mem.sql(
                select(memory_table.c.superseded_by).where(
                    memory_table.c.key == billing_old
                )
            )[0]
            assert old_row["superseded_by"] is None
            assert mem.sql(
                select(memory_table.c.id).where(memory_table.c.key == billing_new)
            ) == []

            removed = await http.delete(f"/api/memory/{payments}", headers=header)
            assert removed.status_code == 200
            gone = await http.get(f"/api/memory/{payments}", headers=header)
            assert gone.status_code == 404

        assert mem.sql(
            select(memory_report_table.c.id).where(
                memory_report_table.c.memory_id == payments_id
            )
        ) == []
        assert mem.sql(
            select(memory_table.c.id).where(memory_table.c.id == payments_id)
        ) == []
        for row in mem.sql(select(memory_recall_log_table.c.returned_ids)):
            assert payments_id not in _ids(row["returned_ids"])
        after = await mem.recall(context={"repo": "example-org/payments-api"})
        assert payments not in after
