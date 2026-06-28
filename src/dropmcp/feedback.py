"""Agent feedback storage, MCP tool, and HTTP read-model serializers.

Feedback is persisted to SQLite by default (``DROPMCP_DATABASE_URL`` unset) or
Postgres when a ``postgresql://`` URL is provided. Agents write via the
``record_feedback`` MCP tool; the catalog UI reads and triages over HTTP.
"""

from __future__ import annotations

import logging
import json
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

FEEDBACK_STATUSES = ("new", "triaged", "actioned")
FEEDBACK_TYPES = ("correction", "agent_work")
DEFAULT_FEEDBACK_TYPE = "correction"


@dataclass(frozen=True)
class FeedbackEntry:
    id: str
    created_at: str
    feedback_type: str
    feedback: str
    better_instruction: str
    suggested_skill: str | None
    model: str
    client: str | None
    skill_name: str | None
    repo: str | None
    details: dict[str, Any] | None
    status: str
    resolution_url: str | None


def feedback_to_dict(entry: FeedbackEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "created_at": entry.created_at,
        "feedback_type": entry.feedback_type,
        "feedback": entry.feedback,
        "better_instruction": entry.better_instruction,
        "suggested_skill": entry.suggested_skill,
        "model": entry.model,
        "client": entry.client,
        "skill_name": entry.skill_name,
        "repo": entry.repo,
        "details": entry.details,
        "status": entry.status,
        "resolution_url": entry.resolution_url,
    }


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
        logger.warning("Ignoring invalid feedback details JSON")
        return None
    return value if isinstance(value, dict) else None


def _row_to_entry(row) -> FeedbackEntry:
    created = _row_value(row, "created_at")
    if isinstance(created, datetime):
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        created_at = created.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    else:
        created_at = str(created)
    return FeedbackEntry(
        id=_row_value(row, "id"),
        created_at=created_at,
        feedback_type=_row_value(row, "feedback_type") or DEFAULT_FEEDBACK_TYPE,
        feedback=_row_value(row, "feedback"),
        better_instruction=_row_value(row, "better_instruction"),
        suggested_skill=_row_value(row, "suggested_skill"),
        model=_row_value(row, "model"),
        client=_row_value(row, "client"),
        skill_name=_row_value(row, "skill_name"),
        repo=_row_value(row, "repo"),
        details=_deserialize_details(_row_value(row, "details")),
        status=_row_value(row, "status"),
        resolution_url=_row_value(row, "resolution_url"),
    )


class FeedbackStore:
    """Thin SQLAlchemy Core store for agent feedback rows."""

    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url, future=True)
        self._metadata = MetaData()
        self._table = Table(
            "feedback",
            self._metadata,
            Column("id", String(36), primary_key=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column(
                "feedback_type",
                String(32),
                nullable=False,
                default=DEFAULT_FEEDBACK_TYPE,
            ),
            Column("feedback", Text, nullable=False),
            Column("better_instruction", Text, nullable=False),
            Column("suggested_skill", Text),
            Column("model", String(128), nullable=False),
            Column("client", String(64)),
            Column("skill_name", Text),
            Column("repo", String(256)),
            Column("details", Text),
            Column("status", String(16), nullable=False, default="new"),
            Column("resolution_url", Text),
        )
        # Only auto-create schema for SQLite (local dev). Managed Postgres relies on SyncDB.
        if database_url.startswith("sqlite"):
            self._metadata.create_all(self._engine)
            self._ensure_sqlite_columns()

    def _ensure_sqlite_columns(self) -> None:
        """Add lightweight columns for existing local SQLite databases."""
        inspector = inspect(self._engine)
        if not inspector.has_table("feedback"):
            return

        existing = {column["name"] for column in inspector.get_columns("feedback")}
        statements: list[str] = []
        if "feedback_type" not in existing:
            statements.append(
                "ALTER TABLE feedback "
                "ADD COLUMN feedback_type VARCHAR(32) NOT NULL DEFAULT 'correction'"
            )
        if "skill_name" not in existing:
            statements.append("ALTER TABLE feedback ADD COLUMN skill_name TEXT")
        if "details" not in existing:
            statements.append("ALTER TABLE feedback ADD COLUMN details TEXT")
        if not statements:
            return

        with self._engine.begin() as conn:
            for statement in statements:
                conn.execute(sql_text(statement))

    def insert(
        self,
        *,
        feedback: str,
        better_instruction: str,
        model: str,
        feedback_type: str = DEFAULT_FEEDBACK_TYPE,
        suggested_skill: str | None = None,
        client: str | None = None,
        skill_name: str | None = None,
        repo: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> str:
        if feedback_type not in FEEDBACK_TYPES:
            raise ValueError(f"invalid feedback_type: {feedback_type}")

        entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                insert(self._table).values(
                    id=entry_id,
                    created_at=now,
                    feedback_type=feedback_type,
                    feedback=feedback,
                    better_instruction=better_instruction,
                    suggested_skill=suggested_skill,
                    model=model,
                    client=client,
                    skill_name=skill_name,
                    repo=repo,
                    details=_serialize_details(details),
                    status="new",
                    resolution_url=None,
                )
            )
        return entry_id

    def list(
        self,
        *,
        search: str | None = None,
        model: str | None = None,
        client: str | None = None,
        skill_name: str | None = None,
        feedback_type: str | None = None,
        status: str | None = None,
    ) -> list[FeedbackEntry]:
        stmt = select(self._table).order_by(self._table.c.created_at.desc())
        if model:
            stmt = stmt.where(self._table.c.model == model)
        if client:
            stmt = stmt.where(self._table.c.client == client)
        if skill_name:
            stmt = stmt.where(self._table.c.skill_name == skill_name)
        if feedback_type:
            stmt = stmt.where(self._table.c.feedback_type == feedback_type)
        if status:
            stmt = stmt.where(self._table.c.status == status)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                self._table.c.feedback.ilike(pattern)
                | self._table.c.better_instruction.ilike(pattern)
            )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        return [_row_to_entry(row) for row in rows]

    def get(self, entry_id: str) -> FeedbackEntry | None:
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
    ) -> FeedbackEntry | None:
        values: dict[str, Any] = {}
        if status is not None:
            if status not in FEEDBACK_STATUSES:
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


_RECORD_FEEDBACK_DESCRIPTION = (
    "Record structured agent feedback for user corrections or reusable "
    "skill-artifact work the agent had to create after invoking a skill. "
    "Do not include verbatim user prompts, code, secrets, PII, or customer data. "
    "Keep feedback and better_instruction brief and paraphrased."
)

_RECORD_FEEDBACK_PARAMETERS = {
    "type": "object",
    "properties": {
        "feedback": {
            "type": "string",
            "description": "What went wrong or what reusable skill gap was hit.",
        },
        "feedback_type": {
            "type": "string",
            "enum": list(FEEDBACK_TYPES),
            "default": DEFAULT_FEEDBACK_TYPE,
            "description": (
                "correction for user corrections; agent_work for reusable work "
                "created after invoking a skill."
            ),
        },
        "better_instruction": {
            "type": "string",
            "description": (
                "Wording that would have prevented the mistake — reusable as a skill rule."
            ),
        },
        "model": {
            "type": "string",
            "description": "The model you are running as (e.g. claude-opus-4.8).",
        },
        "suggested_skill": {
            "type": "string",
            "description": "Optional candidate skill or rule name.",
        },
        "skill_name": {
            "type": "string",
            "description": (
                "Name of the skill that was invoked or active when the feedback "
                "was produced, if any."
            ),
        },
        "repo": {
            "type": "string",
            "description": "Optional high-level repo context (no full paths).",
        },
        "details": {
            "type": "object",
            "description": (
                "Optional structured supporting material, such as reusable "
                "scripts or procedural artifacts created for agent_work feedback."
            ),
            "additionalProperties": True,
        },
    },
    "required": ["feedback", "better_instruction", "model"],
}


class RecordFeedbackTool(Tool):
    """MCP tool that persists agent correction feedback."""

    _store: FeedbackStore = PrivateAttr()

    @classmethod
    def create(cls, store: FeedbackStore) -> "RecordFeedbackTool":
        tool = cls(
            name="record_feedback",
            description=_RECORD_FEEDBACK_DESCRIPTION,
            parameters=_RECORD_FEEDBACK_PARAMETERS,
        )
        tool._store = store
        return tool

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        with track("skill", "record_feedback"):
            feedback = str(arguments.get("feedback", "")).strip()
            better_instruction = str(arguments.get("better_instruction", "")).strip()
            model = str(arguments.get("model", "")).strip() or "unknown"
            feedback_type = (
                str(arguments.get("feedback_type") or DEFAULT_FEEDBACK_TYPE).strip()
                or DEFAULT_FEEDBACK_TYPE
            )
            if not feedback or not better_instruction:
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=(
                                "Feedback not recorded: feedback and "
                                "better_instruction are required."
                            ),
                        )
                    ]
                )
            if feedback_type not in FEEDBACK_TYPES:
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=(
                                "Feedback not recorded: feedback_type must be "
                                f"one of {', '.join(FEEDBACK_TYPES)}."
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
                            text="Feedback not recorded: details must be an object.",
                        )
                    ]
                )

            suggested_skill = arguments.get("suggested_skill")
            skill_name = arguments.get("skill_name")
            repo = arguments.get("repo")
            try:
                entry_id = self._store.insert(
                    feedback=feedback,
                    better_instruction=better_instruction,
                    model=model,
                    feedback_type=feedback_type,
                    suggested_skill=str(suggested_skill).strip()
                    if suggested_skill
                    else None,
                    client=client_bucket(),
                    skill_name=str(skill_name).strip() if skill_name else None,
                    repo=str(repo).strip() if repo else None,
                    details=details,
                )
            except Exception:
                logger.exception("Failed to record feedback")
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text="Feedback could not be saved; continuing without blocking.",
                        )
                    ]
                )

            return ToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Feedback recorded (id={entry_id}).",
                    )
                ]
            )


class FeedbackProvider(Provider):
    """Registers the built-in ``record_feedback`` MCP tool."""

    def __init__(self, store: FeedbackStore) -> None:
        super().__init__()
        self._store = store
        self._tool = RecordFeedbackTool.create(store)

    async def _list_tools(self):
        return [self._tool]

    async def _get_tool(self, name, version=None):
        if name == "record_feedback":
            return self._tool
        return None
