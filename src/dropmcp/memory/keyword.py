"""Keyword search over memories: FTS5 on SQLite, tsvector on Postgres."""

from __future__ import annotations

import re

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

_TOKEN = re.compile(r"\w+")

_CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    title,
    body,
    content='memory',
    content_rowid='rowid'
)
"""

# 'delete' is FTS5's external-content command, not a stored value.
_CREATE_TRIGGERS = (
    """
    CREATE TRIGGER IF NOT EXISTS memory_fts_insert AFTER INSERT ON memory BEGIN
        INSERT INTO memory_fts(rowid, title, body)
        VALUES (new.rowid, new.title, new.body);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS memory_fts_delete AFTER DELETE ON memory BEGIN
        INSERT INTO memory_fts(memory_fts, rowid, title, body)
        VALUES ('delete', old.rowid, old.title, old.body);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS memory_fts_update AFTER UPDATE ON memory BEGIN
        INSERT INTO memory_fts(memory_fts, rowid, title, body)
        VALUES ('delete', old.rowid, old.title, old.body);
        INSERT INTO memory_fts(rowid, title, body)
        VALUES (new.rowid, new.title, new.body);
    END
    """,
)

_SQLITE_CANDIDATES = text(
    """
    SELECT memory.id AS id
    FROM memory_fts
    JOIN memory ON memory.rowid = memory_fts.rowid
    WHERE memory_fts MATCH :query
    ORDER BY bm25(memory_fts, 1.0, 0.4), memory.id
    LIMIT :cap
    """
)

_SQLITE_RANKED = text(
    """
    SELECT memory.id AS id
    FROM memory_fts
    JOIN memory ON memory.rowid = memory_fts.rowid
    WHERE memory_fts MATCH :query
      AND memory.id IN :ids
    ORDER BY bm25(memory_fts, 1.0, 0.4), memory.id
    """
).bindparams(bindparam("ids", expanding=True))

_POSTGRES_CANDIDATES = text(
    """
    SELECT id
    FROM memory
    WHERE search_text @@ websearch_to_tsquery('english', :query)
    ORDER BY ts_rank(
        search_text, websearch_to_tsquery('english', :query)
    ) DESC, id
    LIMIT :cap
    """
)

_POSTGRES_RANKED = text(
    """
    SELECT id
    FROM memory
    WHERE search_text @@ websearch_to_tsquery('english', :query)
      AND id IN :ids
    ORDER BY ts_rank(
        search_text, websearch_to_tsquery('english', :query)
    ) DESC, id
    """
).bindparams(bindparam("ids", expanding=True))


def ensure_sqlite_fts(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'table' AND name = 'memory_fts'"
            )
        ).first()
        conn.execute(text(_CREATE_FTS))
        for statement in _CREATE_TRIGGERS:
            conn.execute(text(statement))
        if existing is None:
            conn.execute(text("INSERT INTO memory_fts(memory_fts) VALUES ('rebuild')"))


def keyword_candidate_ids(engine: Engine, query: str | None, cap: int) -> list[str]:
    match = _match_query(query)
    if match is None or cap < 1:
        return []
    statement = _candidate_statement(engine.dialect.name)
    return _fetch_ids(engine, statement, {"query": match, "cap": cap})


def keyword_ranked(
    engine: Engine, query: str | None, candidate_ids: list[str]
) -> list[str]:
    match = _match_query(query)
    if match is None or not candidate_ids:
        return []
    statement = _ranked_statement(engine.dialect.name)
    return _fetch_ids(engine, statement, {"query": match, "ids": candidate_ids})


def _candidate_statement(dialect: str):
    if dialect == "sqlite":
        return _SQLITE_CANDIDATES
    return _POSTGRES_CANDIDATES


def _ranked_statement(dialect: str):
    if dialect == "sqlite":
        return _SQLITE_RANKED
    return _POSTGRES_RANKED


def _match_query(query: str | None) -> str | None:
    if not query or not query.strip():
        return None
    tokens = list(dict.fromkeys(_TOKEN.findall(query)))
    if not tokens:
        return None
    return " OR ".join(f'"{token}"' for token in tokens)


def _fetch_ids(engine: Engine, statement, params: dict) -> list[str]:
    with engine.connect() as conn:
        return [row.id for row in conn.execute(statement, params)]
