"""Discover catalog metadata and asset paths from skills/ and prompts/ layouts.

Skills: skills/{skill-name}/SKILL.md with optional catalog/ assets.
Prompts: prompts/{prompt-name}/PROMPT.md with optional catalog/ assets.
"""

from __future__ import annotations

import logging
import mimetypes
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

_RESOURCE_EXCLUDED_EXTENSIONS = (".ttf", ".otf", ".woff", ".woff2")


def _main_file_for_type(item_type: str) -> str:
    return SKILL_FILE if item_type.lower() == "skill" else PROMPT_FILE


def is_agent_facing_resource(relpath: str, main_file: str) -> bool:
    """Whether a relative path is an agent-facing supporting file.

    Shared by the catalog HTTP API and MCP skill tool resource links.
    """
    if relpath == main_file:
        return False
    if relpath.startswith("catalog/"):
        return False
    if relpath.lower().endswith(_RESOURCE_EXCLUDED_EXTENSIONS):
        return False
    if any(part.startswith(".") for part in relpath.split("/")):
        return False
    return True


@dataclass(frozen=True)
class ResourceFile:
    path: str
    mime_type: str


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
    group: str | None
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
                group_raw = meta.get("group")
                group = str(group_raw).strip() if group_raw else None
                description = str(meta.get("description", ""))
                item_dir = skill_dir.resolve()
                catalog_dir = (item_dir / CATALOG_DIR).resolve()
                has_hero, has_thumb, shots, examples = _inspect_catalog(catalog_dir)
                found.append(
                    CatalogEntry(
                        name=name,
                        type="skill",
                        category=category,
                        group=group,
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
                group_raw = meta.get("group")
                group = str(group_raw).strip() if group_raw else None
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
                        group=group,
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

    def read_main_markdown(self, item_type: str, name: str) -> str | None:
        entry = self.get_entry(item_type, name)
        if entry is None:
            return None
        main_file = _main_file_for_type(entry.type)
        main_path = entry.item_dir / main_file
        if not main_path.is_file():
            return None
        raw = main_path.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(raw)
        body = raw[match.end() :].strip() if match else raw.strip()
        return body or None

    def list_resource_files(self, item_type: str, name: str) -> list[ResourceFile]:
        entry = self.get_entry(item_type, name)
        if entry is None:
            return []
        main_file = _main_file_for_type(entry.type)
        item_dir = entry.item_dir.resolve()
        files: list[ResourceFile] = []
        for path in sorted(item_dir.rglob("*")):
            if not path.is_file():
                continue
            try:
                relpath = path.resolve().relative_to(item_dir).as_posix()
            except ValueError:
                continue
            if not is_agent_facing_resource(relpath, main_file):
                continue
            mime, _ = mimetypes.guess_type(relpath)
            files.append(
                ResourceFile(
                    path=relpath,
                    mime_type=mime or "application/octet-stream",
                )
            )
        return sorted(files, key=lambda rf: rf.path)

    def resolve_resource_path(
        self, item_type: str, name: str, relpath: str
    ) -> Path | None:
        entry = self.get_entry(item_type, name)
        if entry is None:
            return None
        allowed = {
            (entry.item_dir / rf.path).resolve()
            for rf in self.list_resource_files(item_type, name)
        }
        candidate = (entry.item_dir / relpath).resolve()
        if candidate not in allowed or not candidate.is_file():
            return None
        return candidate

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
