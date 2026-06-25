"""Tests for the filesystem-backed skills provider."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from dropmcp.skills import (
    FilteredSkillsProvider,
    _parse_description,
    _build_skill_tool,
)
from fastmcp.server.providers.skills._common import SkillInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_skill(skills_root: Path, name: str, frontmatter: str, body: str = "") -> Path:
    """Create a minimal skill directory and return the directory path."""
    skill_dir = skills_root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\n{frontmatter}\n---\n{body}"
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


def _make_skill_info(path: Path, name: str) -> SkillInfo:
    """Build a minimal SkillInfo pointing at a SKILL.md."""
    main = "SKILL.md"
    # Build a minimal SkillInfo (description extracted from frontmatter later)
    return SkillInfo(
        name=name,
        path=path,
        main_file=main,
        description="",  # will be overridden by _parse_description
        files=[],
    )


# ---------------------------------------------------------------------------
# _parse_description
# ---------------------------------------------------------------------------


def test_parse_description_simple_yaml(tmp_path):
    _write_skill(tmp_path, "s", "name: s\ncategory: c\ndescription: Hello world\n")
    info = _make_skill_info(tmp_path / "s", "s")
    assert _parse_description(info) == "Hello world"


def test_parse_description_multiline_folded(tmp_path):
    frontmatter = textwrap.dedent("""\
        name: s
        category: c
        description: >-
          A long description
          that spans two lines.
    """)
    _write_skill(tmp_path, "s", frontmatter)
    info = _make_skill_info(tmp_path / "s", "s")
    desc = _parse_description(info)
    assert "long description" in desc


def test_parse_description_colon_in_value_falls_back_to_regex(tmp_path):
    """Descriptions with bare colons confuse yaml.safe_load; regex fallback fires."""
    frontmatter = "name: s\ncategory: c\ndescription: Use when: foo, bar\n"
    _write_skill(tmp_path, "s", frontmatter)
    info = _make_skill_info(tmp_path / "s", "s")
    desc = _parse_description(info)
    assert "Use when: foo, bar" in desc


def test_parse_description_no_frontmatter_returns_info_default(tmp_path):
    skill_dir = tmp_path / "s"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# No frontmatter here", encoding="utf-8")
    info = SkillInfo(
        name="s",
        path=skill_dir,
        main_file="SKILL.md",
        description="fallback",
        files=[],
    )
    assert _parse_description(info) == "fallback"


# ---------------------------------------------------------------------------
# _build_skill_tool
# ---------------------------------------------------------------------------


def test_build_skill_tool_name_and_description(tmp_path):
    _write_skill(tmp_path, "my-skill", "name: my-skill\ncategory: test\ndescription: Does something\n")
    info = _make_skill_info(tmp_path / "my-skill", "my-skill")
    tool = _build_skill_tool(info)
    assert tool.name == "my-skill"
    assert tool.description == "Does something"


def test_build_skill_tool_no_required_parameters(tmp_path):
    _write_skill(tmp_path, "s", "name: s\ncategory: c\ndescription: d\n")
    info = _make_skill_info(tmp_path / "s", "s")
    tool = _build_skill_tool(info)
    # Skills take no parameters
    assert tool.parameters == {"type": "object", "properties": {}}


# ---------------------------------------------------------------------------
# FilteredSkillsProvider._is_visible
# ---------------------------------------------------------------------------


def test_is_visible_hides_skill_md():
    assert not FilteredSkillsProvider._is_visible("skill://foo/SKILL.md")


def test_is_visible_hides_manifest():
    assert not FilteredSkillsProvider._is_visible("skill://foo/_manifest")


def test_is_visible_hides_catalog():
    assert not FilteredSkillsProvider._is_visible("skill://foo/catalog/hero.png")


def test_is_visible_shows_supporting_file():
    assert FilteredSkillsProvider._is_visible("skill://foo/reference.md")


def test_is_visible_shows_nested_supporting_file():
    assert FilteredSkillsProvider._is_visible("skill://foo/scripts/run.sh")


# ---------------------------------------------------------------------------
# FilteredSkillsProvider._list_tools (integration with filesystem)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tools_discovers_skills(tmp_path):
    _write_skill(tmp_path, "alpha", "name: alpha\ncategory: test\ndescription: Alpha skill\n")
    _write_skill(tmp_path, "beta", "name: beta\ncategory: test\ndescription: Beta skill\n")

    provider = FilteredSkillsProvider(roots=tmp_path, supporting_files="resources")
    tools = await provider._list_tools()

    names = {t.name for t in tools}
    assert "alpha" in names
    assert "beta" in names


@pytest.mark.asyncio
async def test_list_tools_ignores_dirs_without_skill_md(tmp_path):
    _write_skill(tmp_path, "valid", "name: valid\ncategory: test\ndescription: d\n")
    (tmp_path / "no-skill").mkdir()  # no SKILL.md

    provider = FilteredSkillsProvider(roots=tmp_path, supporting_files="resources")
    tools = await provider._list_tools()
    assert len(tools) == 1
    assert tools[0].name == "valid"


@pytest.mark.asyncio
async def test_list_tools_empty_directory(tmp_path):
    provider = FilteredSkillsProvider(roots=tmp_path, supporting_files="resources")
    tools = await provider._list_tools()
    assert tools == []


@pytest.mark.asyncio
async def test_list_tools_skips_bad_skill_without_crashing(tmp_path):
    # Valid skill
    _write_skill(tmp_path, "good", "name: good\ncategory: test\ndescription: d\n")
    # Skill with no name key — YAML will load but SkillInfo might still work;
    # write deliberately broken SKILL.md that can't be parsed at all
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    (bad_dir / "SKILL.md").write_text("not: yaml: at: all: ::::", encoding="utf-8")

    provider = FilteredSkillsProvider(roots=tmp_path, supporting_files="resources")
    # Should not raise; bad skill is skipped
    tools = await provider._list_tools()
    names = {t.name for t in tools}
    assert "good" in names


# ---------------------------------------------------------------------------
# SkillTool.run — returns content + resource links
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_tool_run_returns_text_content(tmp_path):
    skill_dir = _write_skill(tmp_path, "s", "name: s\ncategory: c\ndescription: d\n", "Body text here")
    info = _make_skill_info(skill_dir, "s")
    tool = _build_skill_tool(info)
    result = await tool.run({})
    from mcp.types import TextContent
    texts = [c for c in result.content if isinstance(c, TextContent)]
    assert any("Body text here" in t.text for t in texts)


@pytest.mark.asyncio
async def test_skill_tool_run_returns_resource_links_for_supporting_files(tmp_path):
    skill_dir = _write_skill(tmp_path, "s", "name: s\ncategory: c\ndescription: d\n")
    (skill_dir / "reference.md").write_text("# Reference", encoding="utf-8")

    from fastmcp.server.providers.skills._common import SkillFileInfo
    info = SkillInfo(
        name="s",
        path=skill_dir,
        main_file="SKILL.md",
        description="d",
        files=[
            SkillFileInfo(path="SKILL.md", size=10, hash="abc"),
            SkillFileInfo(path="reference.md", size=50, hash="def"),
        ],
    )
    tool = _build_skill_tool(info)
    result = await tool.run({})

    from mcp.types import ResourceLink
    links = [c for c in result.content if isinstance(c, ResourceLink)]
    uris = [str(link.uri) for link in links]
    assert any("reference.md" in u for u in uris)


@pytest.mark.asyncio
async def test_skill_tool_run_excludes_catalog_files(tmp_path):
    skill_dir = _write_skill(tmp_path, "s", "name: s\ncategory: c\ndescription: d\n")

    from fastmcp.server.providers.skills._common import SkillFileInfo
    info = SkillInfo(
        name="s",
        path=skill_dir,
        main_file="SKILL.md",
        description="d",
        files=[
            SkillFileInfo(path="SKILL.md", size=10, hash="abc"),
            SkillFileInfo(path="catalog/hero.png", size=100, hash="xyz"),
        ],
    )
    tool = _build_skill_tool(info)
    result = await tool.run({})

    from mcp.types import ResourceLink
    links = [c for c in result.content if isinstance(c, ResourceLink)]
    uris = [str(link.uri) for link in links]
    assert not any("catalog" in u for u in uris)


@pytest.mark.asyncio
async def test_skill_tool_run_excludes_font_files(tmp_path):
    skill_dir = _write_skill(tmp_path, "s", "name: s\ncategory: c\ndescription: d\n")

    from fastmcp.server.providers.skills._common import SkillFileInfo
    info = SkillInfo(
        name="s",
        path=skill_dir,
        main_file="SKILL.md",
        description="d",
        files=[
            SkillFileInfo(path="SKILL.md", size=10, hash="abc"),
            SkillFileInfo(path="resources/AgodaSans-Regular.ttf", size=100, hash="f1"),
            SkillFileInfo(path="resources/AgodaSans-Bold.WOFF2", size=80, hash="f2"),
            SkillFileInfo(path="reference.md", size=50, hash="def"),
        ],
    )
    tool = _build_skill_tool(info)
    result = await tool.run({})

    from mcp.types import ResourceLink
    links = [c for c in result.content if isinstance(c, ResourceLink)]
    uris = [str(link.uri) for link in links]
    assert any("reference.md" in u for u in uris)
    assert not any(u.endswith(".ttf") or ".woff2" in u.lower() for u in uris)
