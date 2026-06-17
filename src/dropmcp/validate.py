"""Validate SKILL.md and PROMPT.md content before the MCP server loads it.

The catalog UI is more forgiving than the MCP server: malformed YAML
frontmatter can render in the UI while the providers silently skip the item.
This module runs the same structural checks the providers expect, plus
extras they do not enforce (e.g. prompt body placeholders must match
declared argument names).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TextIO

import yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"\{\{\s*([^}\s]+)\s*\}\}")


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(raw)
    if not match:
        raise ValueError(
            "missing or malformed YAML frontmatter "
            "(expected `---` delimited block at the top of the file)"
        )
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError("frontmatter is not a YAML mapping")
    return meta, raw[match.end():]


def _check_required_string(meta: dict, key: str) -> list[str]:
    if key not in meta:
        return [f"missing required field '{key}'"]
    value = meta[key]
    if not isinstance(value, str) or not value.strip():
        return [f"field '{key}' must be a non-empty string"]
    return []


def validate_skill(path: Path) -> list[str]:
    """Return validation errors for a single SKILL.md (empty list means OK)."""
    try:
        meta, _ = _parse_frontmatter(path)
    except ValueError as exc:
        return [str(exc)]

    errors: list[str] = []
    for key in ("name", "category", "description"):
        errors.extend(_check_required_string(meta, key))
    return errors


def validate_prompt(path: Path) -> list[str]:
    """Return validation errors for a single PROMPT.md (empty list means OK)."""
    try:
        meta, body = _parse_frontmatter(path)
    except ValueError as exc:
        return [str(exc)]

    errors: list[str] = []
    for key in ("name", "description"):
        errors.extend(_check_required_string(meta, key))

    args = meta.get("arguments", [])
    if not isinstance(args, list):
        return errors + ["'arguments' must be a list"]

    arg_names: list[str] = []
    for index, arg in enumerate(args):
        if not isinstance(arg, dict):
            errors.append(f"arguments[{index}] must be a mapping")
            continue

        name = arg.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"arguments[{index}] missing 'name'")
            continue
        arg_names.append(name)

        if not name.isidentifier():
            errors.append(
                f"arguments[{index}].name '{name}' is not a valid Python identifier — "
                "the MCP server cannot register prompts whose argument names contain "
                "spaces or special characters"
            )

        if not arg.get("description"):
            errors.append(f"arguments[{index}] '{name}' missing 'description'")

    placeholders = set(PLACEHOLDER_RE.findall(body))
    declared = set(arg_names)
    for placeholder in sorted(placeholders - declared):
        errors.append(
            f"body uses placeholder '{{{{{placeholder}}}}}' but no matching argument is declared"
        )
    for unused in sorted(declared - placeholders):
        errors.append(
            f"argument '{unused}' is declared but never referenced as '{{{{{unused}}}}}' in the body"
        )

    return errors


def _display_path(path: Path, display_root: Path) -> Path:
    resolved = path.resolve()
    try:
        return resolved.relative_to(display_root)
    except ValueError:
        return resolved


def _iter_md_files(root: Path, filename: str) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p / filename for p in root.iterdir() if (p / filename).is_file())


def validate_content(
    skills_dir: Path,
    prompts_dir: Path,
) -> list[tuple[Path, list[str]]]:
    """Validate every SKILL.md and PROMPT.md under the given directories.

    Returns a list of ``(path, errors)`` for files that failed. An empty
    list means everything passed.
    """
    failures: list[tuple[Path, list[str]]] = []

    for skill_md in _iter_md_files(skills_dir, "SKILL.md"):
        errors = validate_skill(skill_md)
        if errors:
            failures.append((skill_md, errors))

    for prompt_md in _iter_md_files(prompts_dir, "PROMPT.md"):
        errors = validate_prompt(prompt_md)
        if errors:
            failures.append((prompt_md, errors))

    return failures


def run_validation(
    skills_dir: Path | str,
    prompts_dir: Path | str,
    *,
    root: Path | None = None,
    stream: TextIO | None = None,
) -> int:
    """Validate content, print per-file results, and return an exit code."""
    skills = Path(skills_dir).resolve()
    prompts = Path(prompts_dir).resolve()
    display_root = (root or Path.cwd()).resolve()
    out = stream or sys.stdout

    failures: list[Path] = []
    checked = 0

    for skill_md in _iter_md_files(skills, "SKILL.md"):
        checked += 1
        rel = _display_path(skill_md, display_root)
        errors = validate_skill(skill_md)
        if errors:
            failures.append(skill_md)
            print(f"FAIL {rel}", file=out)
            for err in errors:
                print(f"  - {err}", file=out)
        else:
            print(f"OK   {rel}", file=out)

    for prompt_md in _iter_md_files(prompts, "PROMPT.md"):
        checked += 1
        rel = _display_path(prompt_md, display_root)
        errors = validate_prompt(prompt_md)
        if errors:
            failures.append(prompt_md)
            print(f"FAIL {rel}", file=out)
            for err in errors:
                print(f"  - {err}", file=out)
        else:
            print(f"OK   {rel}", file=out)

    if failures:
        print(f"\n{len(failures)} file(s) failed validation", file=out)
        return 1

    if checked == 0:
        print(
            f"\nNo SKILL.md or PROMPT.md files found under {skills} or {prompts}",
            file=out,
        )
        return 0

    print("\nAll skills and prompts validated successfully", file=out)
    return 0
