"""Repository feedback storage, MCP tool, and HTTP serializers.

Repo feedback is persisted beside agent feedback, using the same configured
database URL. Agents write via ``record_repo_feedback`` when the repository
itself creates friction, such as flaky tests or missing local setup docs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastmcp.server.providers import Provider
from fastmcp.tools.base import Tool, ToolResult
from mcp.types import TextContent
from pydantic import PrivateAttr
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    insert,
    select,
    text as sql_text,
    update,
)
from sqlalchemy.engine import Engine

from dropmcp.telemetry import client_bucket, track

logger = logging.getLogger(__name__)

REPO_FEEDBACK_CATEGORIES = (
    "tests_require_ci",
    "flaky_test",
    "build_warnings",
    "lint_noise",
    "slow_feedback",
    "local_setup",
    "docs_gap",
    "dependency_issue",
    "tooling_gap",
    "other",
)
REPO_FEEDBACK_STATUSES = ("new", "triaged", "actioned", "wontfix")
REPO_FEEDBACK_CLOSED_STATUSES = ("actioned", "wontfix")

_VOLATILE_HEX_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
_VOLATILE_NUMBER_RE = re.compile(
    r"\b\d+(?:[./:-]\d+)*(?:\.\d+)?(?:ms|s|sec|secs|seconds|m|min|mins|"
    r"minutes|h|hr|hrs|hours|%)?\b",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class RepoFeedbackEntry:
    id: str
    created_at: str
    last_seen_at: str
    category: str
    repo: str
    summary: str
    impact: str
    suggested_fix: str | None
    model: str
    client: str | None
    details: dict[str, Any] | None
    fingerprint: str
    occurrence_count: int
    status: str
    resolution_url: str | None


@dataclass(frozen=True)
class RepoFeedbackWriteResult:
    entry: RepoFeedbackEntry
    deduplicated: bool


def repo_feedback_to_dict(entry: RepoFeedbackEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "created_at": entry.created_at,
        "last_seen_at": entry.last_seen_at,
        "category": entry.category,
        "repo": entry.repo,
        "summary": entry.summary,
        "impact": entry.impact,
        "suggested_fix": entry.suggested_fix,
        "model": entry.model,
        "client": entry.client,
        "details": entry.details,
        "fingerprint": entry.fingerprint,
        "occurrence_count": entry.occurrence_count,
        "status": entry.status,
        "resolution_url": entry.resolution_url,
    }


def make_repo_feedback_fingerprint(repo: str, category: str, summary: str) -> str:
    normalized = "|".join(
        (
            _normalize_fingerprint_part(repo),
            category.strip().lower(),
            _normalize_fingerprint_part(summary),
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalize_fingerprint_part(value: str) -> str:
    normalized = value.strip().lower()
    normalized = _VOLATILE_HEX_RE.sub(" ", normalized)
    normalized = _VOLATILE_NUMBER_RE.sub(" ", normalized)
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def _row_value(row, key: str, default: Any = None) -> Any:
    mapping = getattr(row, "_mapping", {})
    return mapping[key] if key in mapping else default


def _serialize_details(details: dict[str, Any] | None) -> str | None:
    if details is None:
        return None
    return json.dumps(details, sort_keys=True, separators=(",", ":"))


def _deserialize_details(raw: Any) -> dict[str, Any] | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid repo feedback details JSON")
        return None
    return value if isinstance(value, dict) else None


def _format_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _row_to_entry(row) -> RepoFeedbackEntry:
    return RepoFeedbackEntry(
        id=_row_value(row, "id"),
        created_at=_format_datetime(_row_value(row, "created_at")),
        last_seen_at=_format_datetime(_row_value(row, "last_seen_at")),
        category=_row_value(row, "category"),
        repo=_row_value(row, "repo"),
        summary=_row_value(row, "summary"),
        impact=_row_value(row, "impact"),
        suggested_fix=_row_value(row, "suggested_fix"),
        model=_row_value(row, "model"),
        client=_row_value(row, "client"),
        details=_deserialize_details(_row_value(row, "details")),
        fingerprint=_row_value(row, "fingerprint"),
        occurrence_count=int(_row_value(row, "occurrence_count", 1) or 1),
        status=_row_value(row, "status"),
        resolution_url=_row_value(row, "resolution_url"),
    )


def _details_with_previous_entry(
    details: dict[str, Any] | None,
    previous_entry_id: str | None,
) -> dict[str, Any] | None:
    if previous_entry_id is None:
        return details
    enriched = dict(details or {})
    enriched.setdefault("previous_entry_id", previous_entry_id)
    return enriched


def _merge_details(
    existing: dict[str, Any] | None,
    latest: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if latest is None:
        return existing
    if existing is None or existing == latest:
        return latest if existing is None else existing

    merged = dict(existing)
    samples = merged.get("samples")
    if not isinstance(samples, list):
        samples = []
    if latest not in samples:
        samples.append(latest)
    merged["samples"] = samples[-5:]
    return merged


class RepoFeedbackStore:
    """SQLAlchemy Core store for repo friction backlog rows."""

    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url, future=True)
        self._metadata = MetaData()
        self._table = Table(
            "repo_feedback",
            self._metadata,
            Column("id", String(36), primary_key=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("last_seen_at", DateTime(timezone=True), nullable=False),
            Column("category", String(32), nullable=False),
            Column("repo", String(256), nullable=False),
            Column("summary", Text, nullable=False),
            Column("impact", Text, nullable=False),
            Column("suggested_fix", Text),
            Column("model", String(128), nullable=False),
            Column("client", String(64)),
            Column("details", Text),
            Column("fingerprint", String(64), nullable=False),
            Column("occurrence_count", Integer, nullable=False, default=1),
            Column("status", String(16), nullable=False, default="new"),
            Column("resolution_url", Text),
        )
        Index("ix_repo_feedback_fingerprint", self._table.c.fingerprint)
        Index("ix_repo_feedback_repo_status", self._table.c.repo, self._table.c.status)

        # Only auto-create schema for SQLite (local dev). Managed Postgres relies on SyncDB.
        if database_url.startswith("sqlite"):
            self._metadata.create_all(self._engine)
            self._ensure_sqlite_columns()

    def _ensure_sqlite_columns(self) -> None:
        """Add lightweight columns for existing local SQLite databases."""
        inspector = inspect(self._engine)
        if not inspector.has_table("repo_feedback"):
            return

        existing = {column["name"] for column in inspector.get_columns("repo_feedback")}
        statements: list[str] = []
        if "last_seen_at" not in existing:
            statements.append("ALTER TABLE repo_feedback ADD COLUMN last_seen_at DATETIME")
        if "category" not in existing:
            statements.append(
                "ALTER TABLE repo_feedback "
                "ADD COLUMN category VARCHAR(32) NOT NULL DEFAULT 'other'"
            )
        if "repo" not in existing:
            statements.append(
                "ALTER TABLE repo_feedback ADD COLUMN repo VARCHAR(256) NOT NULL DEFAULT ''"
            )
        if "summary" not in existing:
            statements.append(
                "ALTER TABLE repo_feedback ADD COLUMN summary TEXT NOT NULL DEFAULT ''"
            )
        if "impact" not in existing:
            statements.append(
                "ALTER TABLE repo_feedback ADD COLUMN impact TEXT NOT NULL DEFAULT ''"
            )
        if "suggested_fix" not in existing:
            statements.append("ALTER TABLE repo_feedback ADD COLUMN suggested_fix TEXT")
        if "details" not in existing:
            statements.append("ALTER TABLE repo_feedback ADD COLUMN details TEXT")
        if "fingerprint" not in existing:
            statements.append(
                "ALTER TABLE repo_feedback "
                "ADD COLUMN fingerprint VARCHAR(64) NOT NULL DEFAULT ''"
            )
        if "occurrence_count" not in existing:
            statements.append(
                "ALTER TABLE repo_feedback "
                "ADD COLUMN occurrence_count INTEGER NOT NULL DEFAULT 1"
            )
        if "resolution_url" not in existing:
            statements.append("ALTER TABLE repo_feedback ADD COLUMN resolution_url TEXT")
        if not statements:
            return

        with self._engine.begin() as conn:
            for statement in statements:
                conn.execute(sql_text(statement))
            if "last_seen_at" not in existing:
                conn.execute(
                    sql_text(
                        "UPDATE repo_feedback "
                        "SET last_seen_at = created_at "
                        "WHERE last_seen_at IS NULL"
                    )
                )

    def insert(
        self,
        *,
        category: str,
        repo: str,
        summary: str,
        impact: str,
        model: str,
        suggested_fix: str | None = None,
        client: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> RepoFeedbackWriteResult:
        if category not in REPO_FEEDBACK_CATEGORIES:
            raise ValueError(f"invalid category: {category}")

        fingerprint = make_repo_feedback_fingerprint(repo, category, summary)
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            open_stmt = (
                select(self._table)
                .where(self._table.c.fingerprint == fingerprint)
                .where(self._table.c.status.notin_(REPO_FEEDBACK_CLOSED_STATUSES))
                .order_by(self._table.c.last_seen_at.desc())
                .limit(1)
            )
            existing_open = conn.execute(open_stmt).fetchone()
            if existing_open is not None:
                entry_id = _row_value(existing_open, "id")
                occurrence_count = (
                    int(_row_value(existing_open, "occurrence_count", 1) or 1) + 1
                )
                merged_details = _merge_details(
                    _deserialize_details(_row_value(existing_open, "details")),
                    details,
                )
                conn.execute(
                    update(self._table)
                    .where(self._table.c.id == entry_id)
                    .values(
                        occurrence_count=occurrence_count,
                        last_seen_at=now,
                        details=_serialize_details(merged_details),
                    )
                )
                updated = conn.execute(
                    select(self._table).where(self._table.c.id == entry_id)
                ).fetchone()
                return RepoFeedbackWriteResult(_row_to_entry(updated), True)

            closed_stmt = (
                select(self._table.c.id)
                .where(self._table.c.fingerprint == fingerprint)
                .where(self._table.c.status.in_(REPO_FEEDBACK_CLOSED_STATUSES))
                .order_by(self._table.c.last_seen_at.desc())
                .limit(1)
            )
            previous_entry_id = conn.execute(closed_stmt).scalar_one_or_none()
            entry_id = str(uuid.uuid4())
            conn.execute(
                insert(self._table).values(
                    id=entry_id,
                    created_at=now,
                    last_seen_at=now,
                    category=category,
                    repo=repo,
                    summary=summary,
                    impact=impact,
                    suggested_fix=suggested_fix,
                    model=model,
                    client=client,
                    details=_serialize_details(
                        _details_with_previous_entry(details, previous_entry_id)
                    ),
                    fingerprint=fingerprint,
                    occurrence_count=1,
                    status="new",
                    resolution_url=None,
                )
            )
            inserted = conn.execute(
                select(self._table).where(self._table.c.id == entry_id)
            ).fetchone()
            return RepoFeedbackWriteResult(_row_to_entry(inserted), False)

    def list(
        self,
        *,
        search: str | None = None,
        repo: str | None = None,
        category: str | None = None,
        status: str | None = None,
        model: str | None = None,
        client: str | None = None,
        sort: str | None = None,
    ) -> list[RepoFeedbackEntry]:
        stmt = select(self._table)
        if repo:
            stmt = stmt.where(self._table.c.repo == repo)
        if category:
            stmt = stmt.where(self._table.c.category == category)
        if status:
            stmt = stmt.where(self._table.c.status == status)
        if model:
            stmt = stmt.where(self._table.c.model == model)
        if client:
            stmt = stmt.where(self._table.c.client == client)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                self._table.c.summary.ilike(pattern)
                | self._table.c.impact.ilike(pattern)
            )

        if sort == "recent":
            stmt = stmt.order_by(self._table.c.last_seen_at.desc())
        else:
            stmt = stmt.order_by(
                self._table.c.occurrence_count.desc(),
                self._table.c.last_seen_at.desc(),
            )

        with self._engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        return [_row_to_entry(row) for row in rows]

    def get(self, entry_id: str) -> RepoFeedbackEntry | None:
        stmt = select(self._table).where(self._table.c.id == entry_id)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).fetchone()
        return _row_to_entry(row) if row is not None else None

    def patch(
        self,
        entry_id: str,
        *,
        status: str | None = None,
        resolution_url: str | None = None,
    ) -> RepoFeedbackEntry | None:
        values: dict[str, Any] = {}
        if status is not None:
            if status not in REPO_FEEDBACK_STATUSES:
                raise ValueError(f"invalid status: {status}")
            values["status"] = status
        if resolution_url is not None:
            values["resolution_url"] = resolution_url or None
        if not values:
            return self.get(entry_id)

        stmt = (
            update(self._table)
            .where(self._table.c.id == entry_id)
            .values(**values)
        )
        with self._engine.begin() as conn:
            result = conn.execute(stmt)
            if result.rowcount == 0:
                return None
        return self.get(entry_id)


_RECORD_REPO_FEEDBACK_DESCRIPTION = (
    "Record friction encountered while working in a repository: tests that only "
    "run in CI, flaky tests, compiler or lint warning noise, slow builds, "
    "missing setup, missing docs, dependency issues, or missing tooling. "
    "Not for agent mistakes or skill gaps; use record_feedback for those. "
    "Do not include secrets, PII, customer data, or proprietary code."
)

_RECORD_REPO_FEEDBACK_PARAMETERS = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": list(REPO_FEEDBACK_CATEGORIES),
            "description": "The repo friction category.",
        },
        "repo": {
            "type": "string",
            "description": "Repository identifier, preferably group/project.",
        },
        "summary": {
            "type": "string",
            "description": "One stable sentence describing the friction.",
        },
        "impact": {
            "type": "string",
            "description": "Concrete cost or risk caused by the friction.",
        },
        "suggested_fix": {
            "type": "string",
            "description": "Optional fix or owner action that would remove the friction.",
        },
        "model": {
            "type": "string",
            "description": "The model you are running as.",
        },
        "details": {
            "type": "object",
            "description": "Optional evidence such as commands, counts, test names, or warnings.",
            "additionalProperties": True,
        },
    },
    "required": ["category", "repo", "summary", "impact", "model"],
}


class RecordRepoFeedbackTool(Tool):
    """MCP tool that persists repository friction feedback."""

    _store: RepoFeedbackStore = PrivateAttr()

    @classmethod
    def create(cls, store: RepoFeedbackStore) -> "RecordRepoFeedbackTool":
        tool = cls(
            name="record_repo_feedback",
            description=_RECORD_REPO_FEEDBACK_DESCRIPTION,
            parameters=_RECORD_REPO_FEEDBACK_PARAMETERS,
        )
        tool._store = store
        return tool

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        with track("skill", "record_repo_feedback"):
            category = str(arguments.get("category", "")).strip()
            repo = str(arguments.get("repo", "")).strip()
            summary = str(arguments.get("summary", "")).strip()
            impact = str(arguments.get("impact", "")).strip()
            model = str(arguments.get("model", "")).strip() or "unknown"

            if not repo or not summary or not impact:
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=(
                                "Repo feedback not recorded: repo, summary, and "
                                "impact are required."
                            ),
                        )
                    ]
                )
            if category not in REPO_FEEDBACK_CATEGORIES:
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=(
                                "Repo feedback not recorded: category must be "
                                f"one of {', '.join(REPO_FEEDBACK_CATEGORIES)}."
                            ),
                        )
                    ]
                )

            details = arguments.get("details")
            if details is not None and not isinstance(details, dict):
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text="Repo feedback not recorded: details must be an object.",
                        )
                    ]
                )

            suggested_fix = arguments.get("suggested_fix")
            try:
                result = self._store.insert(
                    category=category,
                    repo=repo,
                    summary=summary,
                    impact=impact,
                    suggested_fix=str(suggested_fix).strip()
                    if suggested_fix
                    else None,
                    model=model,
                    client=client_bucket(),
                    details=details,
                )
            except Exception:
                logger.exception("Failed to record repo feedback")
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=(
                                "Repo feedback could not be saved; continuing "
                                "without blocking."
                            ),
                        )
                    ]
                )

            entry = result.entry
            if result.deduplicated:
                text = (
                    f"Already tracked (id={entry.id}, "
                    f"occurrences={entry.occurrence_count})."
                )
            else:
                text = f"Repo feedback recorded (id={entry.id})."
            return ToolResult(content=[TextContent(type="text", text=text)])


class RepoFeedbackProvider(Provider):
    """Registers the built-in ``record_repo_feedback`` MCP tool."""

    def __init__(self, store: RepoFeedbackStore) -> None:
        super().__init__()
        self._store = store
        self._tool = RecordRepoFeedbackTool.create(store)

    async def _list_tools(self):
        return [self._tool]

    async def _get_tool(self, name, version=None):
        if name == "record_repo_feedback":
            return self._tool
        return None
