"""Recall search: filter by scope, cap the candidates, rank, merge, cut."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from dropmcp.memory import keyword, vectors
from dropmcp.memory.context import MemoryContext
from dropmcp.memory.store import MemoryStore, memory_table, memory_to_dict
from dropmcp.memory.vectors import MemoryEmbedder

RRF_K = 60


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

    scope_order = [row_id for row_id in scope_ids if row_id in candidates]
    scores = rrf_merge([scope_order])
    if query:
        lists = ranked_lists(store, list(candidates.values()), query, context, embedder)
        if any(lists):
            scores = rrf_merge(lists)

    now = datetime.now(timezone.utc)
    final = {
        row_id: score
        * scope_boost(candidates[row_id], context)
        * quality_factor(candidates[row_id], now)
        for row_id, score in scores.items()
    }
    ordered = sorted(final, key=final.__getitem__, reverse=True)
    rows = [candidates[row_id] for row_id in ordered]
    return [memory_to_dict(row) for row in apply_budget(rows, limit)]


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


def scope_boost(row: dict[str, Any], context: MemoryContext) -> float:
    # TODO(S4): repo > system > language > stack/task/path overlap.
    return 1.0


def quality_factor(row: dict[str, Any], now: datetime) -> float:
    # TODO(S4): confirmations and age since last_confirmed_at.
    return 1.0


def apply_budget(
    rows: list[dict[str, Any]], limit: int, max_chars: int = 4000
) -> list[dict[str, Any]]:
    # TODO(S4): also stop at ``max_chars`` of rendered entries.
    return rows[:limit]
