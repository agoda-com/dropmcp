"""Memory tables, the ``MemoryStore`` and JSON-safe row serializers."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    and_,
    create_engine,
    insert,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.types import TypeDecorator

from dropmcp.memory import keyword
from dropmcp.memory.context import SCOPE_FIELDS, MemoryContext
from dropmcp.memory.keys import new_key
from dropmcp.repo_feedback import _format_datetime, _normalize_fingerprint_part

logger = logging.getLogger(__name__)

_KEY_ATTEMPTS = 5


class StringList(TypeDecorator):
    """A list of strings: ``TEXT[]`` on Postgres, JSON text elsewhere."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(Text))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        items = [str(item) for item in value or ()]
        if dialect.name == "postgresql":
            return items
        return json.dumps(items)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        if dialect.name == "postgresql":
            return list(value)
        try:
            items = json.loads(value)
        except json.JSONDecodeError:
            logger.warning("Ignoring invalid memory string list JSON")
            return []
        return [str(item) for item in items] if isinstance(items, list) else []


metadata = MetaData()

memory_table = Table(
    "memory",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("key", String(16), nullable=False, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("created_by", Text),
    Column("server", Text, nullable=False),
    Column("last_confirmed_at", DateTime(timezone=True), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("title", Text, nullable=False),
    Column("body", Text, nullable=False),
    Column("evidence", Text),
    Column("repo", Text),
    Column("system", Text),
    Column("language", Text),
    Column("domain", Text),
    Column("stack", StringList, nullable=False),
    Column("task", Text),
    Column("path", Text),
    Column("status", String(16), nullable=False, default="active"),
    Column("superseded_by", String(36), ForeignKey("memory.id")),
    Column("hidden_at", DateTime(timezone=True)),
    Column("fingerprint", String(64), nullable=False),
    Column("occurrence_count", Integer, nullable=False, default=1),
    Column("recall_count", Integer, nullable=False, default=0),
    Column("promoted_url", Text),
    Column("model", String(128), nullable=False),
    Column("client", String(64)),
    Column("embedding", LargeBinary),
    Column("embedding_model", Text),
    Column("embedding_dim", Integer),
)
Index("ix_memory_status_repo", memory_table.c.status, memory_table.c.repo)
Index("ix_memory_status_language", memory_table.c.status, memory_table.c.language)
Index("ix_memory_fingerprint", memory_table.c.fingerprint)

memory_report_table = Table(
    "memory_report",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("created_by", Text),
    Column("client", String(64)),
    Column("model", String(128), nullable=False),
    Column("memory_id", String(36), ForeignKey("memory.id")),
    Column("reported_key", Text),
    Column("described_memory", Text),
    Column("candidate_keys", StringList, nullable=False),
    Column("problem", String(16), nullable=False),
    Column("reason", Text),
    Column("correction", Text),
    Column("context", Text),
    Column("fingerprint", String(64), nullable=False),
    Column("occurrence_count", Integer, nullable=False, default=1),
    Column("status", String(16), nullable=False, default="open"),
    Column("resolved_at", DateTime(timezone=True)),
    Column("resolution", Text),
)
Index("ix_memory_report_memory_id", memory_report_table.c.memory_id)
Index("ix_memory_report_fingerprint", memory_report_table.c.fingerprint)

memory_recall_log_table = Table(
    "memory_recall_log",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("created_by", Text),
    Column("server", Text, nullable=False),
    Column("client", String(64)),
    Column("context", Text),
    Column("had_query", Boolean, nullable=False),
    Column("returned_ids", StringList, nullable=False),
    Column("duration_ms", Integer, nullable=False),
)

memory_near_duplicate_log_table = Table(
    "memory_near_duplicate_log",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("embedding_model", Text),
    Column("threshold", Float),
    Column("top_similarity", Float),
    Column("choice", String(16)),
    Column("fingerprint", String(64)),
    Column("top_key", Text),
)


def make_memory_fingerprint(context: MemoryContext, title: str) -> str:
    parts = [
        _normalize_fingerprint_part(getattr(context, field)) for field in SCOPE_FIELDS
    ]
    parts.append(_normalize_fingerprint_part(title))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _mapping(row: Any) -> Mapping[str, Any]:
    return row if isinstance(row, Mapping) else row._mapping


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _format_datetime(value)
    return value


def _context_value(raw: Any) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        logger.warning("Ignoring invalid memory report context JSON")
        return None
    return value if isinstance(value, dict) else None


def memory_to_dict(row: Any) -> dict[str, Any]:
    mapping = _mapping(row)
    data: dict[str, Any] = {}
    for column in memory_table.columns:
        value = mapping.get(column.name)
        if column.name == "embedding":
            data["has_embedding"] = value is not None
        else:
            data[column.name] = _json_safe(value)
    return data


def report_to_dict(row: Any) -> dict[str, Any]:
    mapping = _mapping(row)
    data = {
        column.name: _json_safe(mapping.get(column.name))
        for column in memory_report_table.columns
    }
    data["context"] = _context_value(mapping.get("context"))
    return data


def _optional(value: str) -> str | None:
    return value or None


class MemoryStore:
    """SQLAlchemy Core store for memories and the recall log."""

    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        # Only auto-create schema for SQLite. Postgres uses the reference SQL.
        if self.engine.dialect.name == "sqlite":
            metadata.create_all(self.engine)
            keyword.ensure_sqlite_fts(self.engine)

    def insert_memory(
        self,
        *,
        context: MemoryContext,
        kind: str,
        title: str,
        body: str,
        evidence: str | None,
        fingerprint: str,
        model: str,
        server: str,
        created_by: str | None,
        client: str | None,
        embedding: bytes | None,
        embedding_model: str | None,
        embedding_dim: int | None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        memory_id = str(uuid.uuid4())
        values = {
            "id": memory_id,
            "created_at": now,
            "created_by": created_by,
            "server": server,
            "last_confirmed_at": now,
            "kind": kind,
            "title": title,
            "body": body,
            "evidence": evidence,
            "repo": _optional(context.repo),
            "system": _optional(context.system),
            "language": _optional(context.language),
            "domain": _optional(context.domain),
            "stack": list(context.stack),
            "task": _optional(context.task),
            "path": _optional(context.path),
            "status": "active",
            "fingerprint": fingerprint,
            "occurrence_count": 1,
            "recall_count": 0,
            "model": model,
            "client": client,
            "embedding": embedding,
            "embedding_model": embedding_model,
            "embedding_dim": embedding_dim,
        }
        for attempt in range(_KEY_ATTEMPTS):
            key = new_key()
            try:
                with self.engine.begin() as conn:
                    conn.execute(insert(memory_table).values(key=key, **values))
                break
            except IntegrityError:
                if attempt == _KEY_ATTEMPTS - 1 or not self._key_exists(key):
                    raise
        return self.get_memory(memory_id)

    def _key_exists(self, key: str) -> bool:
        stmt = select(memory_table.c.id).where(memory_table.c.key == key)
        with self.engine.connect() as conn:
            return conn.execute(stmt).first() is not None

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        stmt = select(memory_table).where(memory_table.c.id == memory_id)
        with self.engine.connect() as conn:
            row = conn.execute(stmt).fetchone()
        return memory_to_dict(row) if row is not None else None

    def get_memory_by_key(self, key: str) -> dict[str, Any] | None:
        stmt = select(memory_table).where(memory_table.c.key == key.strip().upper())
        with self.engine.connect() as conn:
            row = conn.execute(stmt).fetchone()
        return memory_to_dict(row) if row is not None else None

    def hide_memory(self, memory_id: str) -> None:
        stmt = (
            update(memory_table)
            .where(memory_table.c.id == memory_id)
            .where(memory_table.c.hidden_at.is_(None))
            .values(hidden_at=datetime.now(timezone.utc))
        )
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def log_recall(
        self,
        *,
        context: MemoryContext,
        had_query: bool,
        returned_ids: list[str],
        duration_ms: int,
        server: str,
        created_by: str | None,
        client: str | None,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(memory_recall_log_table).values(
                    id=str(uuid.uuid4()),
                    created_at=datetime.now(timezone.utc),
                    created_by=created_by,
                    server=server,
                    client=client,
                    context=context.to_json(),
                    had_query=had_query,
                    returned_ids=returned_ids,
                    duration_ms=duration_ms,
                )
            )
            if returned_ids:
                conn.execute(
                    update(memory_table)
                    .where(memory_table.c.id.in_(returned_ids))
                    .values(recall_count=memory_table.c.recall_count + 1)
                )

    def scope_clause(self, context: MemoryContext) -> ColumnElement[bool]:
        clauses: list[ColumnElement[bool]] = [
            memory_table.c.status == "active",
            memory_table.c.hidden_at.is_(None),
        ]
        for field in SCOPE_FIELDS:
            value = getattr(context, field)
            if value:
                column = memory_table.c[field]
                clauses.append(or_(column.is_(None), column == "", column == value))
        return and_(*clauses)
