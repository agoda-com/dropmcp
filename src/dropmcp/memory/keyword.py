"""Keyword search over memories: FTS5 on SQLite, tsvector on Postgres."""

from __future__ import annotations

from sqlalchemy.engine import Engine


def ensure_sqlite_fts(engine: Engine) -> None:
    # TODO(S3): create the FTS5 table and its sync triggers.
    return None


def keyword_candidate_ids(engine: Engine, query: str | None, cap: int) -> list[str]:
    # TODO(S3): ids of the best keyword matches, at most ``cap``.
    return []


def keyword_ranked(
    engine: Engine, query: str | None, candidate_ids: list[str]
) -> list[str]:
    # TODO(S3): rank ``candidate_ids`` by bm25 / ts_rank, best first.
    return []
