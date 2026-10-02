"""The standard ``context`` object shared by every memory tool."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from typing import Any

from dropmcp.memory.vocabulary import Vocabulary, check_context_text, normalise_stack

SCOPE_FIELDS = ("repo", "system", "language", "domain")
TEXT_FIELDS = ("repo", "system", "language", "domain", "task", "path")
_LOWERCASE_FIELDS = ("repo", "system", "language", "domain", "task")


@dataclass(frozen=True)
class MemoryContext:
    repo: str = ""
    system: str = ""
    language: str = ""
    domain: str = ""
    stack: tuple[str, ...] = ()
    task: str = ""
    path: str = ""

    @classmethod
    def from_arguments(cls, raw: Any, vocabulary: Vocabulary) -> "MemoryContext":
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise ValueError("context must be an object.")
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(
                f"context has unknown fields: {', '.join(unknown)}. "
                f"Allowed: {', '.join(field.name for field in fields(cls))}."
            )

        values: dict[str, Any] = {}
        for name in TEXT_FIELDS:
            value = raw.get(name)
            if value is None:
                continue
            if not isinstance(value, str):
                raise ValueError(f"context.{name} must be a string.")
            value = value.strip()
            check_context_text(f"context.{name}", value)
            values[name] = value.lower() if name in _LOWERCASE_FIELDS else value

        domain = values.get("domain")
        if domain and vocabulary.domains and domain not in vocabulary.domains:
            raise ValueError(
                f"context.domain '{domain}' is not known. "
                f"Use one of: {', '.join(vocabulary.domains)}."
            )
        language = values.get("language")
        if language and language not in vocabulary.languages:
            raise ValueError(
                f"context.language '{language}' is not known. "
                f"Use one of: {', '.join(vocabulary.languages)}."
            )
        task = values.get("task")
        if task and task not in vocabulary.tasks:
            raise ValueError(
                f"context.task '{task}' is not known. "
                f"Use one of: {', '.join(vocabulary.tasks)}."
            )
        values["stack"] = normalise_stack(raw.get("stack"), vocabulary)
        return cls(**values)

    def to_json(self) -> str:
        return json.dumps(self._non_empty(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, text: str | None) -> "MemoryContext":
        if not text:
            return cls()
        data = json.loads(text)
        values: dict[str, Any] = {
            name: str(data[name]) for name in TEXT_FIELDS if data.get(name)
        }
        values["stack"] = tuple(str(tag) for tag in data.get("stack") or ())
        return cls(**values)

    def render_line(self) -> str:
        parts = [
            f"{name}={','.join(value) if name == 'stack' else value}"
            for name, value in self._non_empty().items()
        ]
        return " ".join(parts) if parts else "general"

    def _non_empty(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if value:
                data[field.name] = list(value) if field.name == "stack" else value
        return data
