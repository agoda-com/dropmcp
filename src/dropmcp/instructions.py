"""Aggregate per-skill / per-prompt `instruction_summary` frontmatter into the
server-level instructions string the MCP client sees.

Each skill or prompt can declare a short phrase (or list of phrases) in its
YAML frontmatter under `instruction_summary`. At server startup we collect
them all and substitute them into `INSTRUCTIONS.md` wherever the
`{{INSTRUCTION_SUMMARIES}}` (skills) and `{{PROMPT_SUMMARIES}}` (prompts)
placeholders appear, rendered as markdown bullet lists. The placeholders
let the rest of `INSTRUCTIONS.md` stay hand-written while the bullet lists
stay in lockstep with whatever is currently installed under `skills/` and
`prompts/`.

If a placeholder is absent the template is returned unchanged for that
section, so existing deployments that haven't adopted a placeholder still
work.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

SKILLS_PLACEHOLDER = "{{INSTRUCTION_SUMMARIES}}"
PROMPTS_PLACEHOLDER = "{{PROMPT_SUMMARIES}}"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        log.warning("Failed to parse frontmatter for %s: %s", path, exc)
        return {}


def _extract_summaries(meta: dict) -> list[str]:
    value = meta.get("instruction_summary")
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _collect(root: Path, main_file: str) -> list[tuple[str, str]]:
    """Return `(name, summary)` pairs for every entry under `root`.

    `name` is taken from the YAML frontmatter; if absent we fall back to the
    directory name so the bullet still has something the agent can call.
    """
    if not root.is_dir():
        return []
    pairs: list[tuple[str, str]] = []
    for sub in sorted(root.iterdir()):
        f = sub / main_file
        if not f.is_file():
            continue
        meta = _parse_frontmatter(f)
        name = str(meta.get("name") or sub.name).strip()
        for summary in _extract_summaries(meta):
            pairs.append((name, summary))
    return pairs


def _render_bullets(
    pairs: list[tuple[str, str]],
    empty_message: str,
) -> str:
    if not pairs:
        return empty_message
    return "\n".join(f"- `{name}` — {summary}" for name, summary in pairs)


def build_server_instructions(
    template_path: Path,
    skills_dir: Path,
    prompts_dir: Path,
) -> str | None:
    """Read `INSTRUCTIONS.md` and substitute the summaries placeholders.

    `{{INSTRUCTION_SUMMARIES}}` is replaced with a bullet list of skill
    `instruction_summary` values; `{{PROMPT_SUMMARIES}}` is replaced with the
    same for prompts. Returns None if the template file is missing so callers
    can pass `None` through to FastMCP (which treats it as "no instructions").
    """
    if not template_path.exists():
        return None
    template = template_path.read_text(encoding="utf-8").strip()

    if SKILLS_PLACEHOLDER in template:
        template = template.replace(
            SKILLS_PLACEHOLDER,
            _render_bullets(
                _collect(skills_dir, "SKILL.md"),
                "_(no skills have declared an instruction_summary yet)_",
            ),
        )

    if PROMPTS_PLACEHOLDER in template:
        template = template.replace(
            PROMPTS_PLACEHOLDER,
            _render_bullets(
                _collect(prompts_dir, "PROMPT.md"),
                "_(no prompts have declared an instruction_summary yet)_",
            ),
        )

    return template
