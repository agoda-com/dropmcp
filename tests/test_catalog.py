"""Tests for catalog discovery (skills, prompts, images, fallbacks)."""

from __future__ import annotations

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
    description: str = "A skill",
) -> Path:
    skill_dir = skills_root / dir_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    effective_name = name or dir_name
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {effective_name}\ncategory: {category}\ndescription: {description}\n---\nbody",
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
    assert "basic.md" in entry.example_filenames
