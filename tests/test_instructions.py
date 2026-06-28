"""Tests for instruction_summary aggregation and placeholder substitution."""

from __future__ import annotations

from pathlib import Path

from dropmcp.instructions import (
    build_server_instructions,
    SKILLS_PLACEHOLDER,
    PROMPTS_PLACEHOLDER,
    _collect,
    _extract_summaries,
    _parse_frontmatter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_skill(skills_root: Path, name: str, frontmatter: str) -> Path:
    d = skills_root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\nbody", encoding="utf-8")
    return d


def _write_prompt(prompts_root: Path, name: str, frontmatter: str) -> Path:
    d = prompts_root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "PROMPT.md").write_text(f"---\n{frontmatter}\n---\nbody", encoding="utf-8")
    return d


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------


def test_parse_frontmatter_returns_dict(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: foo\ncategory: bar\n---\nbody", encoding="utf-8")
    result = _parse_frontmatter(p)
    assert result["name"] == "foo"


def test_parse_frontmatter_missing_returns_empty(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("no frontmatter", encoding="utf-8")
    result = _parse_frontmatter(p)
    assert result == {}


def test_parse_frontmatter_bad_yaml_returns_empty(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\nkey: val: bad:\n---\nbody", encoding="utf-8")
    # Should not raise; returns {}
    result = _parse_frontmatter(p)
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# _extract_summaries
# ---------------------------------------------------------------------------


def test_extract_summaries_string():
    assert _extract_summaries({"instruction_summary": "Do X"}) == ["Do X"]


def test_extract_summaries_list():
    meta = {"instruction_summary": ["Do X", "Do Y"]}
    assert _extract_summaries(meta) == ["Do X", "Do Y"]


def test_extract_summaries_missing_key():
    assert _extract_summaries({}) == []


def test_extract_summaries_empty_string():
    assert _extract_summaries({"instruction_summary": ""}) == []


def test_extract_summaries_strips_whitespace():
    assert _extract_summaries({"instruction_summary": "  trimmed  "}) == ["trimmed"]


# ---------------------------------------------------------------------------
# _collect
# ---------------------------------------------------------------------------


def test_collect_skills(tmp_path):
    skills = tmp_path / "skills"
    _write_skill(skills, "foo", "name: foo\ninstruction_summary: Foo does X\n")
    _write_skill(skills, "bar", "name: bar\ninstruction_summary: Bar does Y\n")

    pairs = _collect(skills, "SKILL.md")
    summaries = [s for _, s in pairs]
    assert "Foo does X" in summaries
    assert "Bar does Y" in summaries


def test_collect_missing_summary_omitted(tmp_path):
    skills = tmp_path / "skills"
    _write_skill(skills, "foo", "name: foo\ncategory: c\n")

    pairs = _collect(skills, "SKILL.md")
    assert pairs == []


def test_collect_multiple_summaries_per_skill(tmp_path):
    skills = tmp_path / "skills"
    _write_skill(skills, "foo", "name: foo\ninstruction_summary:\n  - A\n  - B\n")

    pairs = _collect(skills, "SKILL.md")
    summaries = [s for _, s in pairs]
    assert summaries == ["A", "B"]


def test_collect_nonexistent_dir_returns_empty(tmp_path):
    assert _collect(tmp_path / "nope", "SKILL.md") == []


# ---------------------------------------------------------------------------
# build_server_instructions
# ---------------------------------------------------------------------------


def test_build_instructions_substitutes_skills_placeholder(tmp_path):
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    _write_skill(skills, "s", "name: s\ninstruction_summary: Does something\n")

    tpl = tmp_path / "INSTRUCTIONS.md"
    tpl.write_text(f"# Instructions\n\n{SKILLS_PLACEHOLDER}\n", encoding="utf-8")

    result = build_server_instructions(tpl, skills, prompts)
    assert result is not None
    assert "Does something" in result
    assert SKILLS_PLACEHOLDER not in result


def test_build_instructions_substitutes_prompts_placeholder(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    prompts = tmp_path / "prompts"
    _write_prompt(prompts, "p", "name: p\ninstruction_summary: Greets user\n")

    tpl = tmp_path / "INSTRUCTIONS.md"
    tpl.write_text(f"# Instructions\n\n{PROMPTS_PLACEHOLDER}\n", encoding="utf-8")

    result = build_server_instructions(tpl, skills, prompts)
    assert result is not None
    assert "Greets user" in result
    assert PROMPTS_PLACEHOLDER not in result


def test_build_instructions_no_placeholder_passes_through(tmp_path):
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()

    tpl = tmp_path / "INSTRUCTIONS.md"
    tpl.write_text("Static instructions only.", encoding="utf-8")

    result = build_server_instructions(tpl, skills, prompts)
    assert result == "Static instructions only."


def test_build_instructions_missing_template_returns_none(tmp_path):
    result = build_server_instructions(
        tmp_path / "missing.md",
        tmp_path / "skills",
        tmp_path / "prompts",
    )
    assert result is None


def test_build_instructions_empty_dirs_uses_fallback_message(tmp_path):
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()

    tpl = tmp_path / "INSTRUCTIONS.md"
    tpl.write_text(f"{SKILLS_PLACEHOLDER}\n{PROMPTS_PLACEHOLDER}", encoding="utf-8")

    result = build_server_instructions(tpl, skills, prompts)
    assert result is not None
    assert "no skills" in result.lower() or "no prompts" in result.lower()


def test_build_instructions_both_placeholders(tmp_path):
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    _write_skill(skills, "sk", "name: sk\ninstruction_summary: Skill summary\n")
    _write_prompt(prompts, "pr", "name: pr\ninstruction_summary: Prompt summary\n")

    tpl = tmp_path / "INSTRUCTIONS.md"
    tpl.write_text(
        f"## Skills\n{SKILLS_PLACEHOLDER}\n\n## Prompts\n{PROMPTS_PLACEHOLDER}",
        encoding="utf-8",
    )

    result = build_server_instructions(tpl, skills, prompts)
    assert "Skill summary" in result
    assert "Prompt summary" in result


def test_build_instructions_feedback_enabled_adds_agent_work_guidance(tmp_path):
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()

    tpl = tmp_path / "INSTRUCTIONS.md"
    tpl.write_text("Static instructions only.", encoding="utf-8")

    result = build_server_instructions(tpl, skills, prompts, feedback_enabled=True)
    assert result is not None
    assert "feedback_type" in result
    assert "agent_work" in result
    assert "details.artifacts" in result
