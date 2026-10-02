"""Catalog admin routes for memories, open reports, recall stats and deletes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastmcp import FastMCP
from sqlalchemy import delete, func, or_, select, text, update
from starlette.requests import Request
from starlette.responses import JSONResponse

from dropmcp.config import Settings
from dropmcp.identity import user_from_request
from dropmcp.memory.store import (
    MemoryStore,
    memory_recall_log_table,
    memory_report_table,
    memory_table,
    memory_to_dict,
    report_to_dict,
)

_SCOPE_FIELDS = ("repo", "system", "language", "domain", "task", "path")


def register_admin_routes(
    mcp: FastMCP, store: MemoryStore, settings: Settings
) -> None:
    def _require_user(request: Request) -> JSONResponse | None:
        if user_from_request(request, settings.user_header) is None:
            return JSONResponse(
                {"error": "identity header required"}, status_code=401
            )
        return None

    # "reports" and "stats" are registered before "{key}" so they are not keys.
    @mcp.custom_route("/api/memory", methods=["GET"])
    async def memory_list(request: Request) -> JSONResponse:
        if denied := _require_user(request):
            return denied
        params = request.query_params
        return JSONResponse(
            list_memories(
                store,
                repo=_blank(params.get("repo")),
                language=_blank(params.get("language")),
                kind=_blank(params.get("kind")),
                status=_blank(params.get("status")),
                hidden=_flag(params.get("hidden")),
                search=_blank(params.get("search")),
                sort=_blank(params.get("sort")) or "confirmations",
            )
        )

    @mcp.custom_route("/api/memory/reports", methods=["GET"])
    async def memory_open_reports(request: Request) -> JSONResponse:
        if denied := _require_user(request):
            return denied
        return JSONResponse(list_open_reports(store))

    @mcp.custom_route("/api/memory/stats", methods=["GET"])
    async def memory_stats(request: Request) -> JSONResponse:
        if denied := _require_user(request):
            return denied
        return JSONResponse(recall_stats(store))

    @mcp.custom_route("/api/memory/{key}", methods=["GET"])
    async def memory_get(request: Request) -> JSONResponse:
        if denied := _require_user(request):
            return denied
        detail = memory_detail(store, request.path_params["key"])
        if detail is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse(detail)

    @mcp.custom_route("/api/memory/{key}", methods=["DELETE"])
    async def memory_delete(request: Request) -> JSONResponse:
        if denied := _require_user(request):
            return denied
        key = request.path_params["key"]
        if not delete_memory(store, key):
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({"deleted": key.strip().upper()})


def list_memories(
    store: MemoryStore,
    *,
    repo: str | None,
    language: str | None,
    kind: str | None,
    status: str | None,
    hidden: bool | None,
    search: str | None,
    sort: str,
) -> dict[str, Any]:
    stmt = select(memory_table)
    if repo:
        stmt = stmt.where(memory_table.c.repo == repo)
    if language:
        stmt = stmt.where(memory_table.c.language == language)
    if kind:
        stmt = stmt.where(memory_table.c.kind == kind)
    if status:
        stmt = stmt.where(memory_table.c.status == status)
    if hidden is True:
        stmt = stmt.where(memory_table.c.hidden_at.is_not(None))
    elif hidden is False:
        stmt = stmt.where(memory_table.c.hidden_at.is_(None))
    if search:
        stmt = stmt.where(_search_clause(search))
    if sort == "recent":
        stmt = stmt.order_by(
            memory_table.c.last_confirmed_at.desc(),
            memory_table.c.key.asc(),
        )
    else:
        stmt = stmt.order_by(
            memory_table.c.occurrence_count.desc(),
            memory_table.c.last_confirmed_at.desc(),
            memory_table.c.key.asc(),
        )
    with store.engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        counts = _open_report_counts(conn)
        facets = _facets(conn)
    return {
        "items": [
            _list_item(memory_to_dict(row), counts.get(row.id, 0)) for row in rows
        ],
        **facets,
    }


def memory_detail(store: MemoryStore, key: str) -> dict[str, Any] | None:
    memory = store.get_memory_by_key(key)
    if memory is None:
        return None
    stmt = (
        select(memory_report_table)
        .where(memory_report_table.c.memory_id == memory["id"])
        .order_by(
            memory_report_table.c.created_at.desc(),
            memory_report_table.c.id.asc(),
        )
    )
    with store.engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
    reports = [
        _report_view(report_to_dict(row), memory["key"]) for row in rows
    ]
    open_reports = sum(1 for report in reports if report["status"] == "open")
    item = _list_item(memory, open_reports)
    item["body"] = memory["body"]
    item["evidence"] = memory["evidence"]
    return {"memory": item, "reports": reports}


def list_open_reports(store: MemoryStore) -> dict[str, Any]:
    stmt = (
        select(memory_report_table)
        .where(memory_report_table.c.status == "open")
        .order_by(
            memory_report_table.c.created_at.desc(),
            memory_report_table.c.id.asc(),
        )
    )
    with store.engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        reports = [report_to_dict(row) for row in rows]
        keys = _memory_keys(
            conn, [report["memory_id"] for report in reports if report["memory_id"]]
        )
    return {
        "items": [
            _report_view(report, keys.get(report["memory_id"])) for report in reports
        ]
    }


def recall_stats(store: MemoryStore) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    with store.engine.connect() as conn:
        periods = [_period(conn, now, days) for days in (7, 30)]
    return {"periods": periods}


def delete_memory(store: MemoryStore, key: str) -> bool:
    normalized = key.strip().upper()
    with store.engine.begin() as conn:
        row = conn.execute(
            select(memory_table.c.id).where(memory_table.c.key == normalized)
        ).first()
        if row is None:
            return False
        memory_id = row.id
        conn.execute(
            delete(memory_report_table).where(
                memory_report_table.c.memory_id == memory_id
            )
        )
        conn.execute(
            update(memory_table)
            .where(memory_table.c.superseded_by == memory_id)
            .values(superseded_by=None)
        )
        _remove_recall_id(conn, store.engine.dialect.name, memory_id)
        conn.execute(delete(memory_table).where(memory_table.c.id == memory_id))
    return True


def _remove_recall_id(conn: Any, dialect: str, memory_id: str) -> None:
    if dialect == "postgresql":
        conn.execute(
            text(
                "UPDATE memory_recall_log "
                "SET returned_ids = array_remove(returned_ids, :memory_id)"
            ),
            {"memory_id": memory_id},
        )
        return
    rows = conn.execute(
        select(
            memory_recall_log_table.c.id,
            memory_recall_log_table.c.returned_ids,
        )
    ).fetchall()
    for row in rows:
        current = list(row.returned_ids or [])
        updated = [item for item in current if item != memory_id]
        if updated == current:
            continue
        conn.execute(
            update(memory_recall_log_table)
            .where(memory_recall_log_table.c.id == row.id)
            .values(returned_ids=updated)
        )


def _period(conn: Any, now: datetime, days: int) -> dict[str, Any]:
    since = now - timedelta(days=days)
    recalls = conn.execute(
        select(memory_recall_log_table.c.returned_ids).where(
            memory_recall_log_table.c.created_at >= since
        )
    ).fetchall()
    recall_count = len(recalls)
    with_results = sum(1 for row in recalls if row.returned_ids)
    report_count = int(
        conn.execute(
            select(func.count())
            .select_from(memory_report_table)
            .where(memory_report_table.c.created_at >= since)
        ).scalar_one()
    )
    writers = int(
        conn.execute(
            select(func.count(func.distinct(memory_table.c.created_by)))
            .where(memory_table.c.created_at >= since)
            .where(memory_table.c.created_by.is_not(None))
            .where(memory_table.c.created_by != "")
        ).scalar_one()
    )
    return {
        "days": days,
        "label": f"Last {days} days",
        "recall_count": recall_count,
        "recalls_with_results": with_results,
        "recalls_without_results": recall_count - with_results,
        "share_returning": _percent(with_results, recall_count),
        "report_count": report_count,
        "reports_per_recall": _per_recall(report_count, recall_count),
        "distinct_writers": writers,
    }


def _open_report_counts(conn: Any) -> dict[str, int]:
    stmt = (
        select(memory_report_table.c.memory_id, func.count())
        .where(memory_report_table.c.status == "open")
        .where(memory_report_table.c.memory_id.is_not(None))
        .group_by(memory_report_table.c.memory_id)
    )
    return {row[0]: int(row[1]) for row in conn.execute(stmt)}


def _facets(conn: Any) -> dict[str, list[str]]:
    return {
        "repos": _distinct(conn, memory_table.c.repo),
        "languages": _distinct(conn, memory_table.c.language),
        "kinds": _distinct(conn, memory_table.c.kind),
    }


def _distinct(conn: Any, column: Any) -> list[str]:
    stmt = select(column).where(column.is_not(None)).where(column != "").distinct()
    return sorted({str(row[0]) for row in conn.execute(stmt)})


def _memory_keys(conn: Any, memory_ids: list[str]) -> dict[str, str]:
    if not memory_ids:
        return {}
    stmt = select(memory_table.c.id, memory_table.c.key).where(
        memory_table.c.id.in_(memory_ids)
    )
    return {row.id: row.key for row in conn.execute(stmt)}


def _list_item(memory: dict[str, Any], open_reports: int) -> dict[str, Any]:
    hidden = memory.get("hidden_at") is not None
    confirmations = int(memory["occurrence_count"])
    return {
        "key": memory["key"],
        "title": memory["title"],
        "kind": memory["kind"],
        "status": memory["status"],
        "repo": memory.get("repo"),
        "language": memory.get("language"),
        "scope": _scope_label(memory),
        "confirmations": confirmations,
        "confirmations_label": _count_label(confirmations, "confirmation"),
        "open_reports": open_reports,
        "open_reports_label": _count_label(open_reports, "open report"),
        "hidden": hidden,
        "hidden_label": "Hidden" if hidden else None,
        "created_at": memory.get("created_at"),
        "last_confirmed_at": memory.get("last_confirmed_at"),
        "display_created_at": _display_datetime(memory.get("created_at")),
        "display_confirmed_at": _display_datetime(memory.get("last_confirmed_at")),
    }


def _report_view(report: dict[str, Any], memory_key: str | None) -> dict[str, Any]:
    keys = list(report.get("candidate_keys") or [])
    problem = str(report.get("problem") or "")
    return {
        "id": report["id"],
        "problem": problem,
        "problem_label": problem.replace("_", " "),
        "reason": report.get("reason"),
        "correction": report.get("correction"),
        "status": report.get("status"),
        "reported_key": report.get("reported_key"),
        "memory_key": memory_key,
        "described_memory": report.get("described_memory"),
        "candidate_keys": keys,
        "candidate_keys_label": ", ".join(keys) if keys else None,
        "keyed": memory_key is not None,
        "link_label": memory_key or "Unkeyed",
        "created_at": report.get("created_at"),
        "display_created_at": _display_datetime(report.get("created_at")),
    }


def _scope_label(memory: dict[str, Any]) -> str:
    parts = [str(memory[field]) for field in _SCOPE_FIELDS if memory.get(field)]
    stack = memory.get("stack") or []
    if stack:
        parts.append(", ".join(str(tag) for tag in stack))
    return " · ".join(parts) if parts else "general"


def _search_clause(search: str):
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    return or_(
        memory_table.c.title.ilike(pattern, escape="\\"),
        memory_table.c.body.ilike(pattern, escape="\\"),
    )


def _display_datetime(value: Any) -> str | None:
    if not value:
        return None
    text_value = str(value).replace("T", " ")
    if text_value.endswith("Z"):
        text_value = text_value[:-1]
    if "+" in text_value[10:]:
        text_value = text_value.split("+", 1)[0]
    if "." in text_value:
        text_value = text_value.split(".", 1)[0]
    return text_value.strip()


def _count_label(count: int, noun: str) -> str:
    suffix = noun if count == 1 else f"{noun}s"
    return f"{count} {suffix}"


def _percent(part: int, whole: int) -> str:
    if whole == 0:
        return "0%"
    value = 100 * part / whole
    if value == int(value):
        return f"{int(value)}%"
    return f"{value:.1f}%"


def _per_recall(reports: int, recalls: int) -> str:
    if recalls == 0:
        return "0"
    value = reports / recalls
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text_value = value.strip()
    return text_value or None


def _flag(value: str | None) -> bool | None:
    if value is None or not value.strip():
        return None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes"}:
        return True
    if lowered in {"0", "false", "no"}:
        return False
    return None
