"""Runtime configuration for a dropmcp server.

A single `Settings` object holds everything the server needs. Values are
resolved in priority order: explicit keyword arguments, then environment
variables (`DROPMCP_*`), then sensible defaults. This keeps the one-liner
(`dropmcp.run(skills="skills", prompts="prompts")`) ergonomic while letting
hosted deployments override anything via the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}

DEFAULT_NAME = "dropmcp"
DEFAULT_SKILLS_DIR = "skills"
DEFAULT_PROMPTS_DIR = "prompts"
DEFAULT_TRANSPORT = "stdio"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
INSTRUCTIONS_FILENAME = "INSTRUCTIONS.md"
DEFAULT_INSTRUCTIONS_RESOURCE = "INSTRUCTIONS.default.md"
DEFAULT_ICON_RESOURCE = "static/icon.svg"


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value else None


def _env_bool(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    return None


def _first(*candidates):
    for candidate in candidates:
        if candidate is not None:
            return candidate
    return None


def _packaged_default_instructions() -> Path:
    return Path(resources.files("dropmcp") / DEFAULT_INSTRUCTIONS_RESOURCE)


def _packaged_default_icon() -> Path:
    return Path(resources.files("dropmcp") / DEFAULT_ICON_RESOURCE)


def _resolve_instructions_path(
    explicit: str | Path | None,
    skills_dir: Path,
) -> Path:
    """Pick the INSTRUCTIONS template: explicit -> env -> cwd -> packaged default.

    The cwd lookup means a user who drops an `INSTRUCTIONS.md` next to their
    `skills/` and `prompts/` folders gets it picked up automatically.
    """
    chosen = _first(explicit, _env("DROPMCP_INSTRUCTIONS"))
    if chosen is not None:
        return Path(chosen)

    for candidate in (Path.cwd() / INSTRUCTIONS_FILENAME, skills_dir.parent / INSTRUCTIONS_FILENAME):
        if candidate.is_file():
            return candidate

    return _packaged_default_instructions()


def _resolve_icon_path(
    explicit: str | Path | None,
    skills_dir: Path,
) -> Path:
    chosen = _first(explicit, _env("DROPMCP_ICON"))
    if chosen is not None:
        return Path(chosen)

    for candidate in (Path.cwd() / "icon.svg", skills_dir.parent / "icon.svg"):
        if candidate.is_file():
            return candidate

    return _packaged_default_icon()


@dataclass(frozen=True)
class Settings:
    skills_dir: Path
    prompts_dir: Path
    catalog_defaults_dir: Path | None
    instructions_path: Path
    name: str
    website_url: str | None
    icon: Path
    transport: str
    host: str
    port: int
    ui_enabled: bool
    reload: bool

    @classmethod
    def resolve(
        cls,
        *,
        skills: str | Path | None = None,
        prompts: str | Path | None = None,
        catalog_defaults: str | Path | None = None,
        instructions: str | Path | None = None,
        name: str | None = None,
        website_url: str | None = None,
        icon: str | Path | None = None,
        transport: str | None = None,
        host: str | None = None,
        port: int | None = None,
        ui_enabled: bool | None = None,
        reload: bool | None = None,
    ) -> "Settings":
        skills_dir = Path(
            _first(skills, _env("DROPMCP_SKILLS"), DEFAULT_SKILLS_DIR)
        )
        prompts_dir = Path(
            _first(prompts, _env("DROPMCP_PROMPTS"), DEFAULT_PROMPTS_DIR)
        )

        catalog_defaults_raw = _first(catalog_defaults, _env("DROPMCP_CATALOG_DEFAULTS"))
        catalog_defaults_dir = (
            Path(catalog_defaults_raw) if catalog_defaults_raw is not None else None
        )

        port_raw = _first(port, _env("DROPMCP_PORT"), DEFAULT_PORT)

        return cls(
            skills_dir=skills_dir,
            prompts_dir=prompts_dir,
            catalog_defaults_dir=catalog_defaults_dir,
            instructions_path=_resolve_instructions_path(instructions, skills_dir),
            name=_first(name, _env("DROPMCP_NAME"), DEFAULT_NAME),
            website_url=_first(website_url, _env("DROPMCP_WEBSITE_URL")),
            icon=_resolve_icon_path(icon, skills_dir),
            transport=_first(transport, _env("DROPMCP_TRANSPORT"), DEFAULT_TRANSPORT),
            host=_first(host, _env("DROPMCP_HOST"), DEFAULT_HOST),
            port=int(port_raw),
            ui_enabled=_first(ui_enabled, _env_bool("DROPMCP_UI"), True),
            reload=_first(reload, _env_bool("DROPMCP_RELOAD"), False),
        )
