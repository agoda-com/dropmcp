"""The controlled vocabulary behind the memory ``context`` object and ``kind``."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_logged_unknown_stack_tags: set[str] = set()


@dataclass(frozen=True)
class Vocabulary:
    languages: tuple[str, ...]
    stack: tuple[str, ...]
    domains: tuple[str, ...]
    kinds: tuple[str, ...]
    tasks: tuple[str, ...]


DEFAULT_VOCABULARY = Vocabulary(
    languages=(
        "csharp",
        "java",
        "kotlin",
        "scala",
        "typescript",
        "python",
        "go",
        "sql",
        "other",
    ),
    stack=(
        "react",
        "vite",
        "playwright",
        "pytest",
        "gradle",
        "maven",
        "sbt",
        "dotnet",
        "nunit",
        "xunit",
        "junit",
        "jest",
        "vitest",
        "nodejs",
        "spring",
        "ktor",
        "fastapi",
        "docker",
        "kubernetes",
        "terraform",
        "postgres",
        "mysql",
        "redis",
        "kafka",
        "graphql",
        "grpc",
        "gitlab-ci",
        "github-actions",
    ),
    domains=(),
    kinds=("gotcha", "convention", "decision", "howto", "setup", "pointer"),
    tasks=(
        "implement",
        "debug",
        "test",
        "review",
        "ci",
        "deploy",
        "migrate",
        "investigate",
    ),
)

_FIELDS = ("languages", "stack", "domains", "kinds", "tasks")


def _vocabulary_from_mapping(
    mapping: dict[str, Any], *, path: Path | None = None
) -> Vocabulary:
    values: dict[str, tuple[str, ...]] = {}
    for field in _FIELDS:
        if field not in mapping:
            values[field] = getattr(DEFAULT_VOCABULARY, field)
            continue
        raw_list = mapping[field]
        if not isinstance(raw_list, list):
            if path is not None:
                raise ValueError(
                    f"memory vocabulary at {path}: key '{field}' must be a list."
                )
            raise ValueError(f"memory vocabulary key '{field}' must be a list.")
        values[field] = tuple(
            str(item).strip().lower() for item in raw_list if str(item).strip()
        )
    return Vocabulary(**values)


def _load_vocabulary_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"memory vocabulary file not found: {path}")
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    elif suffix == ".json":
        data = json.loads(text)
    else:
        raise ValueError(
            f"unsupported memory vocabulary file extension '{suffix}'"
        )
    if not isinstance(data, dict):
        raise ValueError(f"memory vocabulary at {path} must be an object.")
    return data


def resolve_vocabulary(raw: Any) -> Vocabulary:
    if raw is None:
        return DEFAULT_VOCABULARY
    if isinstance(raw, Vocabulary):
        return raw
    if isinstance(raw, (str, Path)):
        path = Path(raw)
        return _vocabulary_from_mapping(_load_vocabulary_file(path), path=path)
    if isinstance(raw, dict):
        return _vocabulary_from_mapping(raw)
    raise TypeError(f"unsupported memory vocabulary type: {type(raw).__name__}")


def normalise_stack(tags: Any, vocabulary: Vocabulary) -> tuple[str, ...]:
    if tags is None:
        return ()
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, (list, tuple)):
        raise ValueError("context.stack must be a list of tags.")
    known_stack = set(vocabulary.stack)
    normalised: list[str] = []
    for tag in tags:
        if not isinstance(tag, str):
            raise ValueError("context.stack must be a list of tags.")
        value = tag.strip().lower()
        if value and value not in normalised:
            if value not in known_stack and value not in _logged_unknown_stack_tags:
                logger.info("Unknown memory stack tag: %s", value)
                _logged_unknown_stack_tags.add(value)
            normalised.append(value)
    return tuple(normalised)


def context_schema(vocabulary: Vocabulary) -> dict[str, Any]:
    domain: dict[str, Any] = {
        "type": "string",
        "description": "Business-domain key. Omit if unsure.",
    }
    if vocabulary.domains:
        domain["enum"] = list(vocabulary.domains)
    return {
        "type": "object",
        "description": (
            "Where the memory applies (on write) or where you are working (on read). "
            "Set the narrowest scope that is true."
        ),
        "properties": {
            "repo": {
                "type": "string",
                "description": (
                    "Repository as owner/name, from `git remote get-url origin`. "
                    "Omit for a memory that applies to any repo."
                ),
            },
            "system": {
                "type": "string",
                "description": "Component or service name. Omit if unsure.",
            },
            "language": {
                "type": "string",
                "enum": list(vocabulary.languages),
                "description": "Language of the code involved.",
            },
            "stack": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Stack tags, for example "
                    f"{', '.join(vocabulary.stack[:8])}. Unknown tags are accepted."
                ),
            },
            "domain": domain,
            "task": {
                "type": "string",
                "enum": list(vocabulary.tasks),
                "description": "What you are doing.",
            },
            "path": {
                "type": "string",
                "description": "Folder or file inside the repo, for monorepos.",
            },
        },
        "additionalProperties": False,
    }
