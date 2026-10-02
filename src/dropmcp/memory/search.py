"""Recall search: filter by scope, cap the candidates, rank, merge, cut."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from dropmcp.memory import keyword, vectors
from dropmcp.memory.context import MemoryContext
from dropmcp.memory.store import (
    MemoryStore,
    memory_report_table,
    memory_table,
    memory_to_dict,
)
from dropmcp.memory.vectors import MemoryEmbedder

RRF_K = 60

# One stronger scope field beats a weaker field, including that field's overlap.
REPO_BOOST = 8.0
SYSTEM_BOOST = 4.0
LANGUAGE_BOOST = 2.0
DOMAIN_BOOST = 1.5

STACK_TAG_BOOST = 0.02
TASK_BOOST = 0.05
PATH_BOOST = 0.05
# Capped so stack, task and path overlap alone stay below one domain match.
OVERLAP_CAP = 0.25

HALF_LIFE_DAYS = 180
_MIN_QUALITY = 1e-6
_SCOPE_BOOSTS = (
    ("repo", REPO_BOOST),
    ("system", SYSTEM_BOOST),
    ("language", LANGUAGE_BOOST),
    ("domain", DOMAIN_BOOST),
)
_ELLIPSIS = "..."


def search(
    store: MemoryStore,
    context: MemoryContext,
    query: str | None = None,
    *,
    limit: int = 5,
    candidate_cap: int = 500,
    embedder: MemoryEmbedder | None = None,
) -> list[dict[str, Any]]:
    scope_ids = scope_candidate_ids(store, context, candidate_cap)
    keyword_ids = (
        keyword.keyword_candidate_ids(store.engine, query, candidate_cap)
        if query
        else []
    )
    candidates = load_candidates(
        store, context, candidate_union(scope_ids, keyword_ids, candidate_cap)
    )
    if not candidates:
        return []

    now = datetime.now(timezone.utc)
    if query:
        lists = ranked_lists(
            store, list(candidates.values()), query, context, embedder
        )
        final = {
            row_id: score
            * scope_boost(candidates[row_id], context)
            * quality_factor(candidates[row_id], now)
            for row_id, score in rrf_merge(lists).items()
            if row_id in candidates
        }
    else:
        final = {
            row_id: scope_boost(row, context) * quality_factor(row, now)
            for row_id, row in candidates.items()
        }

    ordered_ids = sorted(final, key=lambda row_id: (-final[row_id], row_id))
    counts = open_report_counts(store, ordered_ids)
    rows: list[dict[str, Any]] = []
    for row_id in ordered_ids:
        row = candidates[row_id]
        row["open_reports"] = counts.get(row_id, 0)
        rows.append(row)
    results = []
    for row in apply_budget(rows, limit):
        data = memory_to_dict(row)
        data["open_reports"] = int(row.get("open_reports") or 0)
        results.append(data)
    return results


def scope_candidate_ids(
    store: MemoryStore, context: MemoryContext, cap: int
) -> list[str]:
    stmt = (
        select(memory_table.c.id)
        .where(store.scope_clause(context))
        .order_by(
            memory_table.c.occurrence_count.desc(),
            memory_table.c.last_confirmed_at.desc(),
            memory_table.c.id,
        )
        .limit(cap)
    )
    with store.engine.connect() as conn:
        return [row.id for row in conn.execute(stmt)]


def candidate_union(
    scope_ids: list[str], keyword_ids: list[str], cap: int
) -> list[str]:
    union = list(dict.fromkeys([*keyword_ids, *scope_ids]))
    return union[:cap]


def load_candidates(
    store: MemoryStore, context: MemoryContext, ids: list[str]
) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    stmt = (
        select(memory_table)
        .where(memory_table.c.id.in_(ids))
        .where(store.scope_clause(context))
    )
    with store.engine.connect() as conn:
        rows = {row.id: dict(row._mapping) for row in conn.execute(stmt)}
    return {row_id: rows[row_id] for row_id in ids if row_id in rows}


def ranked_lists(
    store: MemoryStore,
    candidates: list[dict[str, Any]],
    query: str,
    context: MemoryContext,
    embedder: MemoryEmbedder | None,
) -> list[list[str]]:
    candidate_ids = [row["id"] for row in candidates]
    return [
        keyword.keyword_ranked(store.engine, query, candidate_ids),
        vectors.vector_ranked(candidates, query, context, embedder),
    ]


def rrf_merge(lists: list[list[str]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranked in lists:
        for rank, row_id in enumerate(ranked, start=1):
            scores[row_id] = scores.get(row_id, 0.0) + 1.0 / (RRF_K + rank)
    return scores


def open_report_counts(store: MemoryStore, memory_ids: list[str]) -> dict[str, int]:
    if not memory_ids:
        return {}
    stmt = (
        select(memory_report_table.c.memory_id, func.count())
        .where(memory_report_table.c.status == "open")
        .where(memory_report_table.c.memory_id.in_(memory_ids))
        .group_by(memory_report_table.c.memory_id)
    )
    with store.engine.connect() as conn:
        return {
            memory_id: int(count)
            for memory_id, count in conn.execute(stmt)
            if memory_id is not None
        }


def scope_boost(row: dict[str, Any], context: MemoryContext) -> float:
    boost = 1.0
    for field, weight in _SCOPE_BOOSTS:
        if _field_matches(row, context, field):
            boost *= weight
    return boost * _overlap_factor(row, context)


def quality_factor(row: dict[str, Any], now: datetime) -> float:
    count = _occurrence_count(row)
    confirmation = 1.0 + math.log(max(count, 1))
    confirmed = _as_utc(row.get("last_confirmed_at"))
    moment = _as_utc(now) or datetime.now(timezone.utc)
    if confirmed is None:
        age_days = 0.0
    else:
        age_days = max(0.0, (moment - confirmed).total_seconds() / 86400.0)
    decay = 0.5 ** (age_days / HALF_LIFE_DAYS)
    return max(confirmation * decay, _MIN_QUALITY)


def apply_budget(
    rows: list[dict[str, Any]], limit: int, max_chars: int = 4000
) -> list[dict[str, Any]]:
    from dropmcp.memory.recall import render_entry

    chosen: list[dict[str, Any]] = []
    used = 0
    capped = _clamp_limit(limit)
    for row in rows:
        if len(chosen) >= capped:
            break
        rendered = render_entry(row)
        extra = len(rendered) if not chosen else len(rendered) + 2
        if not chosen and len(rendered) > max_chars:
            chosen.append(_ellipsize(row, max_chars, render_entry))
            break
        if used + extra > max_chars:
            break
        chosen.append(row)
        used += extra
    return chosen


def _clamp_limit(limit: int) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return 1
    return max(1, min(value, 10))


def _ellipsize(row: dict[str, Any], max_chars: int, render) -> dict[str, Any]:
    body = str(row.get("body") or "")
    lo = 0
    hi = len(body)
    best = _ELLIPSIS
    while lo <= hi:
        mid = (lo + hi) // 2
        prefix = body[:mid]
        candidate = f"{prefix}{_ELLIPSIS}" if prefix else _ELLIPSIS
        trial = dict(row)
        trial["body"] = candidate
        if len(render(trial)) <= max_chars:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1
    fitted = dict(row)
    fitted["body"] = best
    return fitted


def _field_matches(row: dict[str, Any], context: MemoryContext, field: str) -> bool:
    caller = getattr(context, field)
    if not caller:
        return False
    return _text(row, field).lower() == caller


def _overlap_factor(row: dict[str, Any], context: MemoryContext) -> float:
    shared = len(_tags(row.get("stack")) & set(context.stack))
    extra = STACK_TAG_BOOST * shared
    if context.task and _text(row, "task").lower() == context.task:
        extra += TASK_BOOST
    if _path_overlaps(_text(row, "path"), context.path):
        extra += PATH_BOOST
    return 1.0 + min(extra, OVERLAP_CAP)


def _tags(value: Any) -> set[str]:
    if not value or isinstance(value, str):
        items = [value] if value else []
    else:
        items = value
    return {str(item).strip().lower() for item in items if str(item).strip()}


def _path_overlaps(memory_path: str, caller_path: str) -> bool:
    left = _normal_path(memory_path)
    right = _normal_path(caller_path)
    if not left or not right:
        return False
    if left == right:
        return True
    return right.startswith(f"{left}/") or left.startswith(f"{right}/")


def _normal_path(path: str) -> str:
    return path.strip().replace("\\", "/").strip("/")


def _text(row: dict[str, Any], name: str) -> str:
    value = row.get(name)
    if value is None:
        return ""
    return str(value).strip()


def _occurrence_count(row: dict[str, Any]) -> int:
    try:
        return max(int(row.get("occurrence_count") or 0), 0)
    except (TypeError, ValueError):
        return 0


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
