"""The ``memory_remember`` tool."""

from __future__ import annotations

import logging
from typing import Any

from fastmcp.tools.base import Tool, ToolResult
from mcp.types import TextContent
from pydantic import PrivateAttr

from dropmcp.config import Settings
from dropmcp.identity import resolve_user_email
from dropmcp.memory import lint
from dropmcp.memory.context import MemoryContext
from dropmcp.memory.keys import is_valid_key
from dropmcp.memory.store import MemoryStore, make_memory_fingerprint
from dropmcp.memory.vectors import (
    MemoryEmbedder,
    cosine,
    embed_text,
    pack,
    safe_embed,
    unpack,
)
from dropmcp.memory.vocabulary import Vocabulary, context_schema
from dropmcp.telemetry import client_bucket, track

logger = logging.getLogger(__name__)

TOOL_NAME = "memory_remember"
MAX_TITLE_CHARS = 200
MAX_BODY_CHARS = 1500
_NEAR_DUPLICATES_SHOWN = 3

_DESCRIPTION = (
    "Remember one short, reusable fact about how a repo, system, tool or stack "
    "behaves, after you confirmed it and it cost time to find. Set the narrowest "
    "context that is true. Never store secrets, personal or customer data, "
    "verbatim code or prompts, or anything about a person."
)


def _parameters(vocabulary: Vocabulary) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "context": context_schema(vocabulary),
            "kind": {
                "type": "string",
                "enum": list(vocabulary.kinds),
                "description": "What sort of memory this is.",
            },
            "title": {
                "type": "string",
                "maxLength": MAX_TITLE_CHARS,
                "description": "One stable sentence stating the fact.",
            },
            "body": {
                "type": "string",
                "maxLength": MAX_BODY_CHARS,
                "description": "The fact and what to do about it.",
            },
            "evidence": {
                "type": "string",
                "description": "Optional: how it was learned (command, PR, repo path).",
            },
            "supersedes": {
                "type": "string",
                "description": "Optional: key of a memory this one replaces.",
            },
            "same_as": {
                "type": "string",
                "description": "Optional: key of a memory this one confirms.",
            },
            "distinct": {
                "type": "boolean",
                "description": "Optional: you saw the near-duplicates and this is new.",
            },
            "model": {
                "type": "string",
                "description": "The model you are running as.",
            },
        },
        "required": ["context", "kind", "title", "body", "model"],
    }


def _result(text: str) -> ToolResult:
    return ToolResult(content=[TextContent(type="text", text=text)])


def _optional_text(arguments: dict[str, Any], name: str) -> str | None:
    value = arguments.get(name)
    if value is None:
        return None
    return str(value).strip() or None


class MemoryRememberTool(Tool):
    """MCP tool that stores a memory."""

    _store: MemoryStore = PrivateAttr()
    _settings: Settings = PrivateAttr()
    _vocabulary: Vocabulary = PrivateAttr()

    @classmethod
    def create(
        cls, store: MemoryStore, settings: Settings, vocabulary: Vocabulary
    ) -> "MemoryRememberTool":
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
                return _result(self._remember(arguments))
            except Exception:
                logger.exception("Failed to store memory")
                return _result(
                    "Memory could not be saved; continuing without blocking."
                )

    def _remember(self, arguments: dict[str, Any]) -> str:
        title = str(arguments.get("title") or "").strip()
        body = str(arguments.get("body") or "").strip()
        kind = str(arguments.get("kind") or "").strip().lower()
        model = str(arguments.get("model") or "").strip()
        evidence = _optional_text(arguments, "evidence")

        problems: list[str] = []
        if "context" not in arguments:
            problems.append("context is required; use {} for a general memory.")
        if not title:
            problems.append("title is required.")
        elif len(title) > MAX_TITLE_CHARS:
            problems.append(f"title must be at most {MAX_TITLE_CHARS} characters.")
        if not body:
            problems.append("body is required.")
        elif len(body) > MAX_BODY_CHARS:
            problems.append(f"body must be at most {MAX_BODY_CHARS} characters.")
        if kind not in self._vocabulary.kinds:
            problems.append(f"kind must be one of {', '.join(self._vocabulary.kinds)}.")
        if not model:
            problems.append("model is required.")
        try:
            context = MemoryContext.from_arguments(
                arguments.get("context"), self._vocabulary
            )
        except ValueError as exc:
            problems.append(str(exc))
        if problems:
            return "Memory not stored: " + " ".join(problems)

        reasons = lint.check_memory(
            title, body, evidence, self._settings.memory_lint_rules
        )
        if reasons:
            return "Memory not stored: " + " ".join(reasons)

        fingerprint = make_memory_fingerprint(context, title)
        existing = self._store.find_active_by_fingerprint(fingerprint)
        if existing is not None:
            return _already_known(self._store.confirm_memory(existing["id"]))

        same_as_key = _optional_text(arguments, "same_as")
        if same_as_key is not None:
            same_as = self._resolve_key(same_as_key)
            if same_as is None:
                return _unknown_key("same_as", same_as_key)
            self._store.resolve_near_duplicate(fingerprint, "same_as")
            return _already_known(self._store.confirm_memory(same_as["id"]))

        supersedes_key = _optional_text(arguments, "supersedes")
        superseded = None
        if supersedes_key is not None:
            superseded = self._resolve_key(supersedes_key)
            if superseded is None:
                return _unknown_key("supersedes", supersedes_key)

        embedder = self._settings.memory_embedder
        vectors = safe_embed(embedder, [embed_text(title, body, context)])
        distinct = arguments.get("distinct") is True
        if vectors and superseded is None and not distinct:
            similar = self._near_duplicates(context, embedder, vectors[0])
            if similar:
                top_similarity, top_key, _ = similar[0]
                self._store.log_near_duplicate(
                    fingerprint=fingerprint,
                    top_key=top_key,
                    top_similarity=top_similarity,
                    threshold=embedder.near_duplicate_threshold,
                    embedding_model=embedder.model,
                )
                return _near_duplicate_prompt(similar)

        memory = dict(
            context=context,
            kind=kind,
            title=title,
            body=body,
            evidence=evidence,
            fingerprint=fingerprint,
            model=model,
            server=self._settings.name,
            created_by=resolve_user_email(self._settings.user_header),
            client=client_bucket(),
            embedding=pack(vectors[0]) if vectors else None,
            embedding_model=embedder.model if vectors else None,
            embedding_dim=embedder.dimension if vectors else None,
        )
        if superseded is not None:
            stored = self._store.insert_superseding_memory(superseded["id"], **memory)
            self._store.resolve_near_duplicate(fingerprint, "supersedes")
            return f"Remembered [{stored['key']}]; it supersedes [{superseded['key']}]."
        stored = self._store.insert_memory(**memory)
        if distinct:
            self._store.resolve_near_duplicate(fingerprint, "distinct")
        return f"Remembered [{stored['key']}]."

    def _resolve_key(self, key: str) -> dict[str, Any] | None:
        if not is_valid_key(key):
            return None
        return self._store.get_memory_by_key(key)

    def _near_duplicates(
        self, context: MemoryContext, embedder: MemoryEmbedder, vector: list[float]
    ) -> list[tuple[float, str, str]]:
        candidates = self._store.near_duplicate_candidates(
            context, embedder.model, self._settings.memory_candidate_cap
        )
        scored = [
            (cosine(vector, unpack(row["embedding"])), row["key"], row["title"])
            for row in candidates
        ]
        similar = [
            item for item in scored if item[0] >= embedder.near_duplicate_threshold
        ]
        similar.sort(key=lambda item: item[0], reverse=True)
        return similar[:_NEAR_DUPLICATES_SHOWN]


def _already_known(memory: dict[str, Any]) -> str:
    return (
        f"Already known [{memory['key']}] "
        f"(confirmations: {memory['occurrence_count']})."
    )


def _unknown_key(option: str, key: str) -> str:
    return f"Memory not stored: {option} key {key} does not match any memory."


def _near_duplicate_prompt(similar: list[tuple[float, str, str]]) -> str:
    lines = [
        f"[{key}] {title} (similarity {similarity:.2f})"
        for similarity, key, title in similar
    ]
    return (
        "Memory not stored: it looks like these existing memories:\n"
        + "\n".join(lines)
        + "\nCall memory_remember again with one of: same_as=<key> if it is the "
        "same fact, supersedes=<key> if it replaces that memory, or distinct=true "
        "if it is a different fact."
    )
