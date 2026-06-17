"""Agent feedback storage, MCP tool, and HTTP read-model serializers.

Feedback is persisted to SQLite by default (``DROPMCP_DATABASE_URL`` unset) or
Postgres when a ``postgresql://`` URL is provided. Agents write via the
``record_feedback`` MCP tool; the catalog UI reads and triages over HTTP.
"""

from __future__ import annotations

import logging
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
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from dropmcp.telemetry import client_bucket, track

logger = logging.getLogger(__name__)

FEEDBACK_STATUSES = ("new", "triaged", "actioned")


@dataclass(frozen=True)
class FeedbackEntry:
    id: str
    created_at: str
    confession: str
    better_instruction: str
    suggested_skill: str | None
    model: str
    client: str | None
    skill_name: str | None
    repo: str | None
    status: str
    resolution_url: str | None


def feedback_to_dict(entry: FeedbackEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "created_at": entry.created_at,
        "confession": entry.confession,
        "better_instruction": entry.better_instruction,
        "suggested_skill": entry.suggested_skill,
        "model": entry.model,
        "client": entry.client,
        "skill_name": entry.skill_name,
        "repo": entry.repo,
        "status": entry.status,
        "resolution_url": entry.resolution_url,
    }


def _row_to_entry(row) -> FeedbackEntry:
    created = row.created_at
    if isinstance(created, datetime):
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        created_at = created.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    else:
        created_at = str(created)
    return FeedbackEntry(
        id=row.id,
        created_at=created_at,
        confession=row.confession,
        better_instruction=row.better_instruction,
        suggested_skill=row.suggested_skill,
        model=row.model,
        client=row.client,
        skill_name=row.skill_name,
        repo=row.repo,
        status=row.status,
        resolution_url=row.resolution_url,
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
            Column("confession", Text, nullable=False),
            Column("better_instruction", Text, nullable=False),
            Column("suggested_skill", Text),
            Column("model", String(128), nullable=False),
            Column("client", String(64)),
            Column("skill_name", String(256)),
            Column("repo", String(256)),
            Column("status", String(16), nullable=False, default="new"),
            Column("resolution_url", Text),
        )
        self._metadata.create_all(self._engine)

    def insert(
        self,
        *,
        confession: str,
        better_instruction: str,
        model: str,
        suggested_skill: str | None = None,
        client: str | None = None,
        skill_name: str | None = None,
        repo: str | None = None,
    ) -> str:
        entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                insert(self._table).values(
                    id=entry_id,
                    created_at=now,
                    confession=confession,
                    better_instruction=better_instruction,
                    suggested_skill=suggested_skill,
                    model=model,
                    client=client,
                    skill_name=skill_name,
                    repo=repo,
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
        status: str | None = None,
    ) -> list[FeedbackEntry]:
        stmt = select(self._table).order_by(self._table.c.created_at.desc())
        if model:
            stmt = stmt.where(self._table.c.model == model)
        if client:
            stmt = stmt.where(self._table.c.client == client)
        if skill_name:
            stmt = stmt.where(self._table.c.skill_name == skill_name)
        if status:
            stmt = stmt.where(self._table.c.status == status)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                self._table.c.confession.ilike(pattern)
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
    "Record structured agent feedback when the user corrects your output. "
    "Do not include verbatim user prompts, code, secrets, PII, or customer data. "
    "Keep confession and better_instruction brief and paraphrased."
)

_RECORD_FEEDBACK_PARAMETERS = {
    "type": "object",
    "properties": {
        "confession": {
            "type": "string",
            "description": "What went wrong, in one sentence.",
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
            "description": "Related skill or prompt name, if any.",
        },
        "repo": {
            "type": "string",
            "description": "Optional high-level repo context (no full paths).",
        },
    },
    "required": ["confession", "better_instruction", "model"],
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
            confession = str(arguments.get("confession", "")).strip()
            better_instruction = str(arguments.get("better_instruction", "")).strip()
            model = str(arguments.get("model", "")).strip() or "unknown"
            if not confession or not better_instruction:
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=(
                                "Feedback not recorded: confession and "
                                "better_instruction are required."
                            ),
                        )
                    ]
                )

            suggested_skill = arguments.get("suggested_skill")
            skill_name = arguments.get("skill_name")
            repo = arguments.get("repo")
            try:
                entry_id = self._store.insert(
                    confession=confession,
                    better_instruction=better_instruction,
                    model=model,
                    suggested_skill=str(suggested_skill).strip()
                    if suggested_skill
                    else None,
                    client=client_bucket(),
                    skill_name=str(skill_name).strip() if skill_name else None,
                    repo=str(repo).strip() if repo else None,
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
        self._store = store
        self._tool = RecordFeedbackTool.create(store)

    async def _list_tools(self):
        return [self._tool]

    async def _get_tool(self, name, version=None):
        if name == "record_feedback":
            return self._tool
        return None
