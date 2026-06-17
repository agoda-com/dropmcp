"""Discover catalog metadata and asset paths from skills/ and prompts/ layouts.

Skills: skills/{skill-name}/SKILL.md with optional catalog/ assets.
Prompts: prompts/{prompt-name}/PROMPT.md with optional catalog/ assets.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

SKILL_FILE = "SKILL.md"
PROMPT_FILE = "PROMPT.md"
CATALOG_DIR = "catalog"
SCREENSHOTS_DIR = "screenshots"
EXAMPLES_DIR = "examples"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}


def _find_image(directory: Path, stem: str) -> Path | None:
    for ext in sorted(IMAGE_EXTENSIONS):
        candidate = directory / f"{stem}{ext}"
        if candidate.is_file():
            return candidate
    return None


def _parse_frontmatter_meta(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(raw)
    if not match:
        raise ValueError(f"{path}: missing YAML frontmatter")
    return yaml.safe_load(match.group(1)) or {}


def _list_screenshot_filenames(screenshots_dir: Path) -> list[str]:
    if not screenshots_dir.is_dir():
        return []
    names: list[str] = []
    for p in screenshots_dir.iterdir():
        if (
            p.is_file()
            and not p.name.startswith(".")
            and p.suffix.lower() in IMAGE_EXTENSIONS
        ):
            names.append(p.name)
    return sorted(names)


def _list_example_filenames(examples_dir: Path) -> list[str]:
    if not examples_dir.is_dir():
        return []
    names: list[str] = []
    for p in examples_dir.iterdir():
        if p.is_file() and not p.name.startswith("."):
            names.append(p.name)
    return sorted(names)


def _safe_file_in_subdir(parent: Path, filename: str) -> Path | None:
    if not filename or filename in (".", ".."):
        return None
    if Path(filename).name != filename:
        return None
    base = parent.resolve()
    path = (parent / filename).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        return None
    return path if path.is_file() else None


def _inspect_catalog(catalog_dir: Path) -> tuple[bool, bool, list[str], list[str]]:
    if not catalog_dir.is_dir():
        return False, False, [], []
    hero = _find_image(catalog_dir, "hero")
    thumb = _find_image(catalog_dir, "thumbnail")
    screenshots = _list_screenshot_filenames(catalog_dir / SCREENSHOTS_DIR)
    examples = _list_example_filenames(catalog_dir / EXAMPLES_DIR)
    return hero is not None, thumb is not None, screenshots, examples


@dataclass
class CatalogEntry:
    name: str
    type: str
    category: str
    description: str
    arguments: list[dict]
    has_hero: bool
    has_thumbnail: bool
    screenshot_filenames: list[str]
    example_filenames: list[str]
    dir_path: Path
    item_dir: Path


class CatalogProvider:
    """Discovers catalog assets from skills and prompts directories."""

    def __init__(
        self,
        skills_dir: Path,
        prompts_dir: Path,
        defaults_dir: Path,
        *,
        reload: bool = False,
    ) -> None:
        self._skills_dir = Path(skills_dir).resolve()
        self._prompts_dir = Path(prompts_dir).resolve()
        self._defaults_dir = Path(defaults_dir).resolve()
        self._reload = reload
        self._entries: list[CatalogEntry] | None = None

    def _discover(self) -> list[CatalogEntry]:
        entries: list[CatalogEntry] = []
        entries.extend(self._discover_skills())
        entries.extend(self._discover_prompts())
        entries.sort(key=lambda e: (e.type, e.name))
        return entries

    def _discover_skills(self) -> list[CatalogEntry]:
        found: list[CatalogEntry] = []
        if not self._skills_dir.is_dir():
            return found

        for skill_dir in sorted(self._skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            main_file = skill_dir / SKILL_FILE
            if not main_file.is_file():
                continue
            try:
                meta = _parse_frontmatter_meta(main_file)
                name = str(meta["name"])
                category = str(meta.get("category", ""))
                description = str(meta.get("description", ""))
                item_dir = skill_dir.resolve()
                catalog_dir = (item_dir / CATALOG_DIR).resolve()
                has_hero, has_thumb, shots, examples = _inspect_catalog(catalog_dir)
                found.append(
                    CatalogEntry(
                        name=name,
                        type="skill",
                        category=category,
                        description=description,
                        arguments=[],
                        has_hero=has_hero,
                        has_thumbnail=has_thumb,
                        screenshot_filenames=shots,
                        example_filenames=examples,
                        dir_path=catalog_dir,
                        item_dir=item_dir,
                    )
                )
            except Exception as exc:
                log.warning("Skipping skill %s: %s", skill_dir, exc)
        return found

    def _discover_prompts(self) -> list[CatalogEntry]:
        found: list[CatalogEntry] = []
        if not self._prompts_dir.is_dir():
            return found

        for prompt_dir in sorted(self._prompts_dir.iterdir()):
            if not prompt_dir.is_dir():
                continue
            main_file = prompt_dir / PROMPT_FILE
            if not main_file.is_file():
                continue
            try:
                meta = _parse_frontmatter_meta(main_file)
                name = str(meta["name"])
                description = str(meta.get("description", ""))
                arguments = meta.get("arguments", [])
                if not isinstance(arguments, list):
                    arguments = []
                else:
                    arguments = [a for a in arguments if isinstance(a, dict)]
                item_dir = prompt_dir.resolve()
                catalog_dir = (item_dir / CATALOG_DIR).resolve()
                has_hero, has_thumb, shots, examples = _inspect_catalog(catalog_dir)
                found.append(
                    CatalogEntry(
                        name=name,
                        type="prompt",
                        category="prompts",
                        description=description,
                        arguments=arguments,
                        has_hero=has_hero,
                        has_thumbnail=has_thumb,
                        screenshot_filenames=shots,
                        example_filenames=examples,
                        dir_path=catalog_dir,
                        item_dir=item_dir,
                    )
                )
            except Exception as exc:
                log.warning("Skipping prompt %s: %s", prompt_dir, exc)
        return found

    def _ensure_discovered(self) -> None:
        if self._reload or self._entries is None:
            self._entries = self._discover()

    def get_entries(self) -> list[CatalogEntry]:
        self._ensure_discovered()
        return list(self._entries or [])

    def get_entry(self, item_type: str, name: str) -> CatalogEntry | None:
        self._ensure_discovered()
        t = item_type.lower()
        for e in self._entries or []:
            if e.type == t and e.name == name:
                return e
        return None

    def resolve_image_path(
        self,
        item_type: str,
        name: str,
        image_kind: str,
        filename: str | None = None,
    ) -> Path | None:
        entry = self.get_entry(item_type, name)
        if entry is None:
            return None
        catalog_dir = entry.dir_path
        kind = image_kind.lower()
        if kind == "hero":
            return _find_image(catalog_dir, "hero")
        if kind == "thumbnail":
            return _find_image(catalog_dir, "thumbnail")
        if kind == "screenshot":
            if not filename:
                return None
            shots = catalog_dir / SCREENSHOTS_DIR
            return _safe_file_in_subdir(shots, filename)
        return None

    def resolve_example_path(
        self, item_type: str, name: str, filename: str
    ) -> Path | None:
        entry = self.get_entry(item_type, name)
        if entry is None:
            return None
        catalog_dir = entry.dir_path
        examples = catalog_dir / EXAMPLES_DIR
        return _safe_file_in_subdir(examples, filename)

    def resolve_thumbnail_path(self, item_type: str, name: str) -> Path | None:
        """Resolve thumbnail with fallback: thumbnail.* -> hero.* -> defaults/{category}.* -> defaults/default.svg"""
        entry = self.get_entry(item_type, name)
        if entry is None:
            return None
        catalog_dir = entry.dir_path

        thumb = _find_image(catalog_dir, "thumbnail")
        if thumb is not None:
            return thumb

        hero = _find_image(catalog_dir, "hero")
        if hero is not None:
            return hero

        if self._defaults_dir.is_dir():
            fallback = _find_image(self._defaults_dir, entry.category)
            if fallback is not None:
                return fallback
            default_svg = self._defaults_dir / "default.svg"
            if default_svg.is_file():
                return default_svg

        return None
