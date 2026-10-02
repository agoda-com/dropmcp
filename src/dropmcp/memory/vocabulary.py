"""The controlled vocabulary behind the memory ``context`` object and ``kind``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


def resolve_vocabulary(raw: Any) -> Vocabulary:
    if raw is None:
        return DEFAULT_VOCABULARY
    if isinstance(raw, Vocabulary):
        return raw
    if isinstance(raw, dict):
        values = {
            field: tuple(
                str(item).strip().lower() for item in raw[field] if str(item).strip()
            )
            if field in raw
            else getattr(DEFAULT_VOCABULARY, field)
            for field in _FIELDS
        }
        return Vocabulary(**values)
    # TODO(S9): load a YAML/JSON vocabulary file from a path.
    raise NotImplementedError("Loading a memory vocabulary file is not supported yet.")


def normalise_stack(tags: Any, vocabulary: Vocabulary) -> tuple[str, ...]:
    if tags is None:
        return ()
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, (list, tuple)):
        raise ValueError("context.stack must be a list of tags.")
    normalised: list[str] = []
    for tag in tags:
        if not isinstance(tag, str):
            raise ValueError("context.stack must be a list of tags.")
        value = tag.strip().lower()
        if value and value not in normalised:
            normalised.append(value)
    # TODO(S9): log tags that are not in vocabulary.stack so the list can grow.
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
