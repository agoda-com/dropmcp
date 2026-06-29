"""Tests for catalog discovery (skills, prompts, images, fallbacks)."""

from __future__ import annotations

import pytest
from pathlib import Path

from dropmcp.catalog import CatalogProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_skill(
    skills_root: Path,
    dir_name: str,
    *,
    name: str | None = None,
    category: str = "test",
    group: str | None = None,
    description: str = "A skill",
) -> Path:
    skill_dir = skills_root / dir_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    effective_name = name or dir_name
    group_line = f"group: {group}\n" if group else ""
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {effective_name}\ncategory: {category}\n{group_line}description: {description}\n---\nbody",
        encoding="utf-8",
    )
    return skill_dir


def _write_prompt(
    prompts_root: Path,
    dir_name: str,
    *,
    name: str | None = None,
    description: str = "A prompt",
    args: list[dict] | None = None,
) -> Path:
    prompt_dir = prompts_root / dir_name
    prompt_dir.mkdir(parents=True, exist_ok=True)
    effective_name = name or dir_name
    arg_yaml = ""
    if args:
        import yaml

        arg_yaml = "arguments:\n" + yaml.dump(args, default_flow_style=False).rstrip()
    (prompt_dir / "PROMPT.md").write_text(
        f"---\nname: {effective_name}\ndescription: {description}\n{arg_yaml}\n---\nbody",
        encoding="utf-8",
    )
    return prompt_dir


def _make_provider(tmp_path: Path) -> tuple[CatalogProvider, Path, Path]:
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()
    provider = CatalogProvider(skills_dir=skills, prompts_dir=prompts, defaults_dir=tmp_path / "defaults")
    return provider, skills, prompts


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_discover_skill(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    _write_skill(skills, "my-skill", name="my-skill", description="Does things")

    entries = provider.get_entries()
    assert len(entries) == 1
    e = entries[0]
    assert e.name == "my-skill"
    assert e.type == "skill"
    assert e.description == "Does things"


def test_discover_skill_group(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    _write_skill(skills, "my-skill", name="my-skill", group="platform")

    entry = provider.get_entry("skill", "my-skill")
    assert entry is not None
    assert entry.group == "platform"


def test_discover_prompt(tmp_path):
    provider, _, prompts = _make_provider(tmp_path)
    _write_prompt(prompts, "greet", name="greet", description="Greets someone")

    entries = provider.get_entries()
    assert len(entries) == 1
    e = entries[0]
    assert e.name == "greet"
    assert e.type == "prompt"


def test_discover_mixed(tmp_path):
    provider, skills, prompts = _make_provider(tmp_path)
    _write_skill(skills, "sk", name="sk")
    _write_prompt(prompts, "pr", name="pr")

    entries = provider.get_entries()
    assert len(entries) == 2
    types = {e.type for e in entries}
    assert types == {"skill", "prompt"}


def test_discover_empty_dirs(tmp_path):
    provider, _, _ = _make_provider(tmp_path)
    assert provider.get_entries() == []


def test_discover_ignores_dirs_without_main_file(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    (skills / "no-skill-md").mkdir()

    assert provider.get_entries() == []


def test_discover_skips_bad_entry_without_crashing(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    _write_skill(skills, "good", name="good")
    bad = skills / "bad"
    bad.mkdir()
    (bad / "SKILL.md").write_text("no frontmatter", encoding="utf-8")

    entries = provider.get_entries()
    assert len(entries) == 1
    assert entries[0].name == "good"


# ---------------------------------------------------------------------------
# get_entry
# ---------------------------------------------------------------------------


def test_get_entry_found(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    _write_skill(skills, "foo", name="foo")

    entry = provider.get_entry("skill", "foo")
    assert entry is not None
    assert entry.name == "foo"


def test_get_entry_not_found(tmp_path):
    provider, _, _ = _make_provider(tmp_path)
    assert provider.get_entry("skill", "missing") is None


def test_get_entry_type_case_insensitive(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    _write_skill(skills, "s", name="s")

    assert provider.get_entry("SKILL", "s") is not None


# ---------------------------------------------------------------------------
# Image detection
# ---------------------------------------------------------------------------


def test_has_hero_detected(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    skill_dir = _write_skill(skills, "s", name="s")
    catalog = skill_dir / "catalog"
    catalog.mkdir()
    (catalog / "hero.png").write_bytes(b"\x89PNG")

    provider._entries = None  # force re-discovery
    entry = provider.get_entry("skill", "s")
    assert entry is not None
    assert entry.has_hero is True


def test_has_thumbnail_detected(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    skill_dir = _write_skill(skills, "s", name="s")
    catalog = skill_dir / "catalog"
    catalog.mkdir()
    (catalog / "thumbnail.svg").write_text("<svg/>", encoding="utf-8")

    provider._entries = None
    entry = provider.get_entry("skill", "s")
    assert entry is not None
    assert entry.has_thumbnail is True


def test_no_catalog_dir_has_no_images(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    _write_skill(skills, "s", name="s")

    entry = provider.get_entry("skill", "s")
    assert entry is not None
    assert entry.has_hero is False
    assert entry.has_thumbnail is False


# ---------------------------------------------------------------------------
# resolve_thumbnail_path — fallback chain
# ---------------------------------------------------------------------------


def test_resolve_thumbnail_returns_thumbnail(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    skill_dir = _write_skill(skills, "s", name="s", category="mycat")
    catalog = skill_dir / "catalog"
    catalog.mkdir()
    thumb = catalog / "thumbnail.png"
    thumb.write_bytes(b"\x89PNG")

    provider._entries = None
    path = provider.resolve_thumbnail_path("skill", "s")
    assert path == thumb


def test_resolve_thumbnail_falls_back_to_hero(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    skill_dir = _write_skill(skills, "s", name="s")
    catalog = skill_dir / "catalog"
    catalog.mkdir()
    hero = catalog / "hero.jpg"
    hero.write_bytes(b"JPG")

    provider._entries = None
    path = provider.resolve_thumbnail_path("skill", "s")
    assert path == hero


def test_resolve_thumbnail_falls_back_to_category_default(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    _write_skill(skills, "s", name="s", category="mycat")
    defaults = tmp_path / "defaults"
    defaults.mkdir()
    default_img = defaults / "mycat.svg"
    default_img.write_text("<svg/>", encoding="utf-8")

    provider = CatalogProvider(
        skills_dir=skills,
        prompts_dir=tmp_path / "prompts",
        defaults_dir=defaults,
    )
    (tmp_path / "prompts").mkdir(exist_ok=True)
    path = provider.resolve_thumbnail_path("skill", "s")
    assert path == default_img


def test_resolve_thumbnail_falls_back_to_default_svg(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    _write_skill(skills, "s", name="s", category="unknown")
    defaults = tmp_path / "defaults"
    defaults.mkdir()
    fallback = defaults / "default.svg"
    fallback.write_text("<svg/>", encoding="utf-8")

    provider = CatalogProvider(
        skills_dir=skills,
        prompts_dir=tmp_path / "prompts",
        defaults_dir=defaults,
    )
    (tmp_path / "prompts").mkdir(exist_ok=True)
    path = provider.resolve_thumbnail_path("skill", "s")
    assert path == fallback


def test_resolve_thumbnail_missing_entry_returns_none(tmp_path):
    provider, _, _ = _make_provider(tmp_path)
    assert provider.resolve_thumbnail_path("skill", "ghost") is None


# ---------------------------------------------------------------------------
# Prompt arguments in catalog
# ---------------------------------------------------------------------------


def test_prompt_arguments_in_catalog(tmp_path):
    provider, _, prompts = _make_provider(tmp_path)
    _write_prompt(
        prompts,
        "greet",
        name="greet",
        args=[{"name": "who", "description": "Target", "required": True}],
    )

    entry = provider.get_entry("prompt", "greet")
    assert entry is not None
    assert len(entry.arguments) == 1
    assert entry.arguments[0]["name"] == "who"


# ---------------------------------------------------------------------------
# Screenshot / example listing
# ---------------------------------------------------------------------------


def test_screenshot_filenames_listed(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    skill_dir = _write_skill(skills, "s", name="s")
    shots = skill_dir / "catalog" / "screenshots"
    shots.mkdir(parents=True)
    (shots / "step1.png").write_bytes(b"\x89PNG")
    (shots / "step2.png").write_bytes(b"\x89PNG")

    provider._entries = None
    entry = provider.get_entry("skill", "s")
    assert entry is not None
    assert len(entry.screenshot_filenames) == 2


def test_example_filenames_listed(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    skill_dir = _write_skill(skills, "s", name="s")
    examples = skill_dir / "catalog" / "examples"
    examples.mkdir(parents=True)
    (examples / "basic.md").write_text("# Basic", encoding="utf-8")

    provider._entries = None
    entry = provider.get_entry("skill", "s")
    assert entry is not None
# ---------------------------------------------------------------------------
# Skill content + resources
# ---------------------------------------------------------------------------


def test_read_main_markdown_strips_frontmatter(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    skill_dir = _write_skill(skills, "s", name="s")
    (skill_dir / "SKILL.md").write_text(
        "---\nname: s\ncategory: test\ndescription: d\n---\n# Body\n",
        encoding="utf-8",
    )

    body = provider.read_main_markdown("skill", "s")
    assert body == "# Body"


def test_list_resource_files_excludes_main_catalog_fonts_dotfiles(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    skill_dir = _write_skill(skills, "s", name="s")
    scripts = skill_dir / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text("print('hi')", encoding="utf-8")
    (skill_dir / ".hidden").write_text("secret", encoding="utf-8")
    (skill_dir / "font.woff2").write_bytes(b"font")
    (skill_dir / "evil.html").write_text("<script>alert(1)</script>", encoding="utf-8")
    (skill_dir / "icon.svg").write_text('<svg><script>alert(1)</script></svg>', encoding="utf-8")
    catalog = skill_dir / "catalog"
    catalog.mkdir()
    (catalog / "hero.png").write_bytes(b"\x89PNG")
    (skill_dir / "notes.md").write_text("# Notes", encoding="utf-8")

    paths = [rf.path for rf in provider.list_resource_files("skill", "s")]
    assert paths == ["notes.md", "scripts/run.py"]


def test_resolve_resource_path_allowlist(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    skill_dir = _write_skill(skills, "s", name="s")
    scripts = skill_dir / "scripts"
    scripts.mkdir()
    nested = scripts / "run.py"
    nested.write_text("print('hi')", encoding="utf-8")
    catalog = skill_dir / "catalog"
    catalog.mkdir()
    (catalog / "hero.png").write_bytes(b"\x89PNG")

    assert provider.resolve_resource_path("skill", "s", "scripts/run.py") == nested.resolve()
    assert provider.resolve_resource_path("skill", "s", "../outside") is None
    assert provider.resolve_resource_path("skill", "s", "catalog/hero.png") is None


def test_resolve_resource_path_rejects_symlink_escape(tmp_path):
    provider, skills, _ = _make_provider(tmp_path)
    skill_dir = _write_skill(skills, "s", name="s")
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")
    link = skill_dir / "escape.txt"
    link.symlink_to(outside)

    assert provider.resolve_resource_path("skill", "s", "escape.txt") is None


@pytest.mark.asyncio
async def test_catalog_detail_includes_content_and_resource_route(tmp_path):
    from starlette.testclient import TestClient

    from dropmcp.config import Settings
    from dropmcp.server import build_server

    provider, skills, prompts = _make_provider(tmp_path)
    skill_dir = _write_skill(skills, "demo", name="demo", description="Demo skill")
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\ncategory: test\ndescription: Demo skill\n---\n## Instructions\n",
        encoding="utf-8",
    )
    scripts = skill_dir / "scripts"
    scripts.mkdir()
    helper = scripts / "helper.py"
    helper.write_text("def help():\n    pass\n", encoding="utf-8")

    settings = Settings.resolve(
        skills=skills,
        prompts=prompts,
        ui_enabled=True,
        feedback_enabled=False,
    )
    mcp = build_server(settings)

    with TestClient(mcp.http_app()) as client:
        detail = client.get("/catalog/skill/demo")
        assert detail.status_code == 200
        body = detail.json()
        assert body["content_markdown"] == "## Instructions"
        assert len(body["resources"]) == 1
        assert body["resources"][0]["path"] == "scripts/helper.py"

        index = client.get("/catalog")
        assert "content_markdown" not in index.json()["items"][0]

        resource = client.get("/catalog/skill/demo/resource/scripts/helper.py")
        assert resource.status_code == 200
        assert resource.headers["content-type"].startswith("text/plain")
        assert resource.headers["x-content-type-options"] == "nosniff"
        assert "def help" in resource.text

        missing = client.get("/catalog/skill/demo/resource/../../SKILL.md")
        assert missing.status_code == 404

        spaced = skill_dir / "my notes.py"
        spaced.write_text("x = 1\n", encoding="utf-8")
        detail2 = client.get("/catalog/skill/demo")
        resource_url = next(
            r["url"] for r in detail2.json()["resources"] if r["path"] == "my notes.py"
        )
        assert "%20" in resource_url
        spaced_resource = client.get(resource_url)
        assert spaced_resource.status_code == 200
        assert spaced_resource.text == "x = 1\n"


@pytest.mark.asyncio
async def test_identity_route_uses_configured_header(tmp_path):
    from starlette.testclient import TestClient

    from dropmcp.config import Settings
    from dropmcp.server import build_server

    _, skills, prompts = _make_provider(tmp_path)
    settings = Settings.resolve(
        skills=skills,
        prompts=prompts,
        ui_enabled=True,
        feedback_enabled=False,
        user_header="X-Forwarded-User",
    )
    mcp = build_server(settings)

    with TestClient(mcp.http_app()) as client:
        anonymous = client.get("/api/me")
        assert anonymous.status_code == 200
        assert anonymous.json() == {"email": None, "authenticated": False}

        headers = {"X-Forwarded-User": "dev@example.com"}
        authenticated = client.get("/api/me", headers=headers)
        assert authenticated.status_code == 200
        assert authenticated.json() == {
            "email": "dev@example.com",
            "authenticated": True,
        }

        catalog = client.get("/catalog", headers=headers)
        assert catalog.status_code == 200
        body = catalog.json()
        assert body["user"] == "dev@example.com"
        assert body["me"] == {
            "email": "dev@example.com",
            "authenticated": True,
        }
