"""Tests for SKILL.md and PROMPT.md content validation."""

from __future__ import annotations

import io
from pathlib import Path

from dropmcp.validate import (
    validate_skill,
    validate_prompt,
    validate_content,
    run_validation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skill(tmp_path: Path, dir_name: str, content: str) -> Path:
    d = tmp_path / dir_name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "SKILL.md"
    p.write_text(content, encoding="utf-8")
    return p


def _prompt(tmp_path: Path, dir_name: str, content: str) -> Path:
    d = tmp_path / dir_name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "PROMPT.md"
    p.write_text(content, encoding="utf-8")
    return p


VALID_SKILL = "---\nname: foo\ncategory: test\ndescription: Does things\n---\nbody"
VALID_PROMPT = (
    "---\n"
    "name: greet\n"
    "description: Greets someone\n"
    "arguments:\n"
    "  - name: who\n"
    "    description: Target\n"
    "    required: true\n"
    "---\n"
    "Hello {{who}}!\n"
)


# ---------------------------------------------------------------------------
# validate_skill
# ---------------------------------------------------------------------------


def test_validate_skill_valid(tmp_path):
    p = _skill(tmp_path, "s", VALID_SKILL)
    assert validate_skill(p) == []


def test_validate_skill_missing_frontmatter(tmp_path):
    p = _skill(tmp_path, "s", "# No frontmatter")
    errors = validate_skill(p)
    assert any("frontmatter" in e.lower() for e in errors)


def test_validate_skill_missing_name(tmp_path):
    p = _skill(tmp_path, "s", "---\ncategory: c\ndescription: d\n---\nbody")
    errors = validate_skill(p)
    assert any("name" in e for e in errors)


def test_validate_skill_missing_category(tmp_path):
    p = _skill(tmp_path, "s", "---\nname: n\ndescription: d\n---\nbody")
    errors = validate_skill(p)
    assert any("category" in e for e in errors)


def test_validate_skill_missing_description(tmp_path):
    p = _skill(tmp_path, "s", "---\nname: n\ncategory: c\n---\nbody")
    errors = validate_skill(p)
    assert any("description" in e for e in errors)


def test_validate_skill_empty_name(tmp_path):
    p = _skill(tmp_path, "s", "---\nname: \ncategory: c\ndescription: d\n---\nbody")
    errors = validate_skill(p)
    assert any("name" in e for e in errors)


def test_validate_skill_bad_yaml(tmp_path):
    p = _skill(tmp_path, "s", "---\nkey: val: bad:\n---\nbody")
    errors = validate_skill(p)
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# validate_prompt
# ---------------------------------------------------------------------------


def test_validate_prompt_valid(tmp_path):
    p = _prompt(tmp_path, "p", VALID_PROMPT)
    assert validate_prompt(p) == []


def test_validate_prompt_missing_frontmatter(tmp_path):
    p = _prompt(tmp_path, "p", "No frontmatter")
    errors = validate_prompt(p)
    assert any("frontmatter" in e.lower() for e in errors)


def test_validate_prompt_missing_name(tmp_path):
    p = _prompt(tmp_path, "p", "---\ndescription: d\n---\nbody")
    errors = validate_prompt(p)
    assert any("name" in e for e in errors)


def test_validate_prompt_missing_description(tmp_path):
    p = _prompt(tmp_path, "p", "---\nname: n\n---\nbody")
    errors = validate_prompt(p)
    assert any("description" in e for e in errors)


def test_validate_prompt_undeclared_placeholder(tmp_path):
    p = _prompt(
        tmp_path,
        "p",
        "---\nname: n\ndescription: d\narguments: []\n---\nHello {{who}}!",
    )
    errors = validate_prompt(p)
    assert any("who" in e for e in errors)


def test_validate_prompt_unused_argument(tmp_path):
    content = (
        "---\n"
        "name: n\n"
        "description: d\n"
        "arguments:\n"
        "  - name: who\n"
        "    description: Target\n"
        "    required: true\n"
        "---\n"
        "Hello world!\n"
    )
    p = _prompt(tmp_path, "p", content)
    errors = validate_prompt(p)
    assert any("who" in e for e in errors)


def test_validate_prompt_invalid_arg_name(tmp_path):
    content = (
        "---\n"
        "name: n\n"
        "description: d\n"
        "arguments:\n"
        "  - name: my arg\n"
        "    description: Has spaces\n"
        "    required: true\n"
        "---\n"
        "{{my arg}}\n"
    )
    p = _prompt(tmp_path, "p", content)
    errors = validate_prompt(p)
    assert any("identifier" in e for e in errors)


def test_validate_prompt_arg_missing_description(tmp_path):
    content = (
        "---\n"
        "name: n\n"
        "description: d\n"
        "arguments:\n"
        "  - name: who\n"
        "    required: true\n"
        "---\n"
        "Hello {{who}}!\n"
    )
    p = _prompt(tmp_path, "p", content)
    errors = validate_prompt(p)
    assert any("description" in e for e in errors)


def test_validate_prompt_arguments_not_a_list(tmp_path):
    content = "---\nname: n\ndescription: d\narguments: not-a-list\n---\nbody"
    p = _prompt(tmp_path, "p", content)
    errors = validate_prompt(p)
    assert any("list" in e for e in errors)


def test_validate_prompt_no_arguments_field_valid(tmp_path):
    p = _prompt(tmp_path, "p", "---\nname: n\ndescription: d\n---\nplain body")
    errors = validate_prompt(p)
    assert errors == []


# ---------------------------------------------------------------------------
# validate_content
# ---------------------------------------------------------------------------


def test_validate_content_all_pass(tmp_path):
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    _skill(skills, "s", VALID_SKILL)
    _prompt(prompts, "p", VALID_PROMPT)

    failures = validate_content(skills, prompts)
    assert failures == []


def test_validate_content_returns_failures(tmp_path):
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    _skill(skills, "bad", "no frontmatter")
    prompts.mkdir()

    failures = validate_content(skills, prompts)
    assert len(failures) == 1
    path, errors = failures[0]
    assert path.name == "SKILL.md"
    assert len(errors) > 0


def test_validate_content_empty_dirs(tmp_path):
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()

    assert validate_content(skills, prompts) == []


# ---------------------------------------------------------------------------
# run_validation (exit code + output)
# ---------------------------------------------------------------------------


def test_run_validation_exit_0_on_success(tmp_path):
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    _skill(skills, "s", VALID_SKILL)
    prompts.mkdir()

    out = io.StringIO()
    code = run_validation(skills, prompts, stream=out)
    assert code == 0
    assert "OK" in out.getvalue()


def test_run_validation_exit_1_on_failure(tmp_path):
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    _skill(skills, "bad", "no frontmatter")
    prompts.mkdir()

    out = io.StringIO()
    code = run_validation(skills, prompts, stream=out)
    assert code == 1
    assert "FAIL" in out.getvalue()


def test_run_validation_exit_0_no_files(tmp_path):
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()

    out = io.StringIO()
    code = run_validation(skills, prompts, stream=out)
    assert code == 0
