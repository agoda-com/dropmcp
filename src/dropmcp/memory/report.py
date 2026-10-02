"""The ``memory_report`` tool and report persistence."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastmcp.tools.base import Tool, ToolResult
from mcp.types import TextContent
from pydantic import PrivateAttr
from sqlalchemy import insert, select

from dropmcp.config import Settings
from dropmcp.identity import resolve_user_email
from dropmcp.memory import lint
from dropmcp.memory.context import MemoryContext
from dropmcp.memory.keys import is_valid_key
from dropmcp.memory.store import MemoryStore, memory_report_table, report_to_dict
from dropmcp.memory.vocabulary import Vocabulary, context_schema
from dropmcp.repo_feedback import _normalize_fingerprint_part
from dropmcp.telemetry import client_bucket, track

logger = logging.getLogger(__name__)

TOOL_NAME = "memory_report"
REPORT_PROBLEMS = ("stale", "invalid", "wrong_scope", "sensitive")

_DESCRIPTION = (
    "Report a recalled memory that turned out stale, invalid, scoped too broadly, "
    "or holding something that should not be stored. Quote its key; if the key "
    "is gone, describe what the memory said. A sensitive report hides the memory "
    "immediately. Describe a sensitive memory by kind without repeating it."
)


def _parameters(vocabulary: Vocabulary) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The memory key, such as MEM-7K3F9Q, if you have it.",
            },
            "memory": {
                "type": "string",
                "description": "What the memory claimed. Required without a key.",
            },
            "problem": {
                "type": "string",
                "enum": list(REPORT_PROBLEMS),
                "description": "What is wrong with the memory.",
            },
            "reason": {
                "type": "string",
                "description": "Why it is wrong.",
            },
            "correction": {
                "type": "string",
                "description": "Optional: what is true now.",
            },
            "context": context_schema(vocabulary),
            "model": {
                "type": "string",
                "description": "The model you are running as.",
            },
        },
        "required": ["problem", "model"],
    }


def _result(text: str) -> ToolResult:
    return ToolResult(content=[TextContent(type="text", text=text)])


def _optional_text(arguments: dict[str, Any], name: str) -> str | None:
    value = arguments.get(name)
    if value is None:
        return None
    return str(value).strip() or None


def make_report_fingerprint(
    memory_id: str | None,
    context: MemoryContext,
    problem: str,
    described_memory: str | None,
) -> str:
    if memory_id is not None:
        parts = [memory_id, problem]
    else:
        parts = [
            _normalize_fingerprint_part(context.repo),
            problem,
            _normalize_fingerprint_part(described_memory or ""),
        ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def insert_report(
    store: MemoryStore,
    *,
    memory_id: str | None,
    reported_key: str | None,
    described_memory: str | None,
    candidate_keys: list[str],
    problem: str,
    reason: str | None,
    correction: str | None,
    context: MemoryContext,
    model: str,
    created_by: str | None,
    client: str | None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    report_id = str(uuid.uuid4())
    with store.engine.begin() as conn:
        conn.execute(
            insert(memory_report_table).values(
                id=report_id,
                created_at=now,
                last_seen_at=now,
                created_by=created_by,
                client=client,
                model=model,
                memory_id=memory_id,
                reported_key=reported_key,
                described_memory=described_memory,
                candidate_keys=candidate_keys,
                problem=problem,
                reason=reason,
                correction=correction,
                context=context.to_json(),
                fingerprint=make_report_fingerprint(
                    memory_id, context, problem, described_memory
                ),
                occurrence_count=1,
                status="open",
            )
        )
        row = conn.execute(
            select(memory_report_table).where(memory_report_table.c.id == report_id)
        ).fetchone()
    return report_to_dict(row)


class MemoryReportTool(Tool):
    """MCP tool that files a report against a memory."""

    _store: MemoryStore = PrivateAttr()
    _settings: Settings = PrivateAttr()
    _vocabulary: Vocabulary = PrivateAttr()

    @classmethod
    def create(
        cls, store: MemoryStore, settings: Settings, vocabulary: Vocabulary
    ) -> "MemoryReportTool":
        tool = cls(
            name=TOOL_NAME,
            description=_DESCRIPTION,
            parameters=_parameters(vocabulary),
        )
        tool._store = store
        tool._settings = settings
        tool._vocabulary = vocabulary
        return tool

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        with track("skill", TOOL_NAME):
            try:
                return _result(self._report(arguments))
            except Exception:
                logger.exception("Failed to record memory report")
                return _result(
                    "Memory report could not be saved; continuing without blocking."
                )

    def _report(self, arguments: dict[str, Any]) -> str:
        key = _optional_text(arguments, "key")
        described_memory = _optional_text(arguments, "memory")
        problem = str(arguments.get("problem") or "").strip().lower()
        reason = _optional_text(arguments, "reason")
        correction = _optional_text(arguments, "correction")
        model = str(arguments.get("model") or "").strip() or "unknown"

        if problem not in REPORT_PROBLEMS:
            return (
                "Memory report not recorded: problem must be one of "
                f"{', '.join(REPORT_PROBLEMS)}."
            )
        if key is None and described_memory is None:
            return (
                "Memory report not recorded: pass the memory key, or describe "
                "what the memory said in `memory`."
            )
        try:
            context = MemoryContext.from_arguments(
                arguments.get("context"), self._vocabulary
            )
        except ValueError as exc:
            return f"Memory report not recorded: {exc}"
        reasons = lint.check_report(
            described_memory, reason, correction, self._settings.memory_lint_rules
        )
        if reasons:
            return "Memory report not recorded: " + " ".join(reasons)

        memory = (
            self._store.get_memory_by_key(key)
            if key is not None and is_valid_key(key)
            else None
        )
        if memory is not None and problem == "sensitive":
            self._store.hide_memory(memory["id"])
        # TODO(S7): dedupe; candidate keys for unkeyed reports.
        report = insert_report(
            self._store,
            memory_id=memory["id"] if memory is not None else None,
            reported_key=key,
            described_memory=described_memory,
            candidate_keys=[],
            problem=problem,
            reason=reason,
            correction=correction,
            context=context,
            model=model,
            created_by=resolve_user_email(self._settings.user_header),
            client=client_bucket(),
        )
        return f"Reported ({report['id']})."
