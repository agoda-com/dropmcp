"""Runtime configuration for a dropmcp server.

A single `Settings` object holds everything the server needs. Values are
resolved in priority order: explicit keyword arguments, then environment
variables (`DROPMCP_*`), then sensible defaults. This keeps the one-liner
(`dropmcp.run(skills="skills", prompts="prompts")`) ergonomic while letting
hosted deployments override anything via the environment.

dropmcp serves over streamable-HTTP only — it exists to *share* skills with
multiple remote clients, so there is no local stdio transport to configure.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dropmcp.benchmarks import BenchmarkResultsStore
    from dropmcp.eval_results import EvalResultsStore
    from dropmcp.memory.lint import LintRule
    from dropmcp.memory.store import MemoryStore
    from dropmcp.memory.vectors import MemoryEmbedder

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}

DEFAULT_NAME = "dropmcp"
DEFAULT_SKILLS_DIR = "skills"
DEFAULT_PROMPTS_DIR = "prompts"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
INSTRUCTIONS_FILENAME = "INSTRUCTIONS.md"
DEFAULT_INSTRUCTIONS_RESOURCE = "INSTRUCTIONS.default.md"
DEFAULT_ICON_RESOURCE = "static/icon.svg"
DEFAULT_CATALOG_DEFAULTS_RESOURCE = "static/catalog-defaults"
DEFAULT_DATABASE_FILENAME = "dropmcp.db"
DEFAULT_USER_HEADER = "X-User-Email"
COMMIT_SHA_FILENAME = "COMMIT_SHA"
DEFAULT_MEMORY_CANDIDATE_CAP = 500


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


def _packaged_catalog_defaults() -> Path:
    return Path(resources.files("dropmcp") / DEFAULT_CATALOG_DEFAULTS_RESOURCE)


def _resolve_commit_sha(
    explicit: str | None,
    skills_dir: Path,
) -> str | None:
    chosen = _first(explicit, _env("DROPMCP_EVAL_RESULTS_COMMIT_SHA"))
    if chosen is not None:
        return chosen

    for candidate in (
        Path("/app") / COMMIT_SHA_FILENAME,
        Path.cwd() / COMMIT_SHA_FILENAME,
        skills_dir.parent / COMMIT_SHA_FILENAME,
    ):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()

    return None


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


def _default_database_url(skills_dir: Path) -> str:
    """SQLite file next to the content folders.

    An existing ``dropmcp.db`` wins — cwd first, then the skills parent — so a
    server keeps reading the same store regardless of where it is launched from.
    When none exists, a new file is created in the cwd.
    """
    for base in (Path.cwd(), skills_dir.parent):
        db_path = base / DEFAULT_DATABASE_FILENAME
        if db_path.is_file():
            return f"sqlite:///{db_path.resolve()}"
    return f"sqlite:///{(Path.cwd() / DEFAULT_DATABASE_FILENAME).resolve()}"


def _resolve_database_url(
    explicit: str | None,
    skills_dir: Path,
) -> str:
    chosen = _first(explicit, _env("DROPMCP_DATABASE_URL"))
    if chosen is not None:
        return chosen
    return _default_database_url(skills_dir)


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


def _resolve_memory_vocabulary(
    explicit: str | Path | dict[str, Any] | None,
) -> Path | dict[str, Any] | None:
    chosen = _first(explicit, _env("DROPMCP_MEMORY_VOCABULARY"))
    if chosen is None or isinstance(chosen, dict):
        return chosen
    return Path(chosen)


@dataclass(frozen=True)
class Settings:
    skills_dir: Path
    prompts_dir: Path
    catalog_defaults_dir: Path
    instructions_path: Path
    name: str
    website_url: str | None
    icon: Path
    host: str
    port: int
    ui_enabled: bool
    feedback_enabled: bool
    repo_feedback_enabled: bool
    user_subscriptions_enabled: bool
    user_header: str
    reload: bool
    database_url: str
    eval_results_project: str | None
    eval_results_commit_sha: str | None
    eval_results_store: EvalResultsStore | None
    benchmarks_enabled: bool
    benchmark_results_store: BenchmarkResultsStore | None
    memory_enabled: bool
    memory_embedder: MemoryEmbedder | None
    memory_vocabulary: Path | dict[str, Any] | None
    memory_lint_rules: tuple[LintRule, ...]
    memory_store: MemoryStore | None
    memory_candidate_cap: int

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
        host: str | None = None,
        port: int | None = None,
        ui_enabled: bool | None = None,
        feedback_enabled: bool | None = None,
        repo_feedback_enabled: bool | None = None,
        user_subscriptions_enabled: bool | None = None,
        user_header: str | None = None,
        reload: bool | None = None,
        database_url: str | None = None,
        eval_results_project: str | None = None,
        eval_results_commit_sha: str | None = None,
        eval_results_store: EvalResultsStore | None = None,
        benchmarks_enabled: bool | None = None,
        benchmark_results_store: BenchmarkResultsStore | None = None,
        memory_enabled: bool | None = None,
        memory_embedder: MemoryEmbedder | None = None,
        memory_vocabulary: str | Path | dict[str, Any] | None = None,
        memory_lint_rules: Sequence[LintRule] | None = None,
        memory_store: MemoryStore | None = None,
        memory_candidate_cap: int | None = None,
    ) -> "Settings":
        skills_dir = Path(
            _first(skills, _env("DROPMCP_SKILLS"), DEFAULT_SKILLS_DIR)
        )
        prompts_dir = Path(
            _first(prompts, _env("DROPMCP_PROMPTS"), DEFAULT_PROMPTS_DIR)
        )

        catalog_defaults_raw = _first(catalog_defaults, _env("DROPMCP_CATALOG_DEFAULTS"))
        catalog_defaults_dir = (
            Path(catalog_defaults_raw)
            if catalog_defaults_raw is not None
            else _packaged_catalog_defaults()
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
            host=_first(host, _env("DROPMCP_HOST"), DEFAULT_HOST),
            port=int(port_raw),
            ui_enabled=_first(ui_enabled, _env_bool("DROPMCP_UI"), True),
            feedback_enabled=_first(
                feedback_enabled, _env_bool("DROPMCP_FEEDBACK"), True
            ),
            repo_feedback_enabled=_first(
                repo_feedback_enabled, _env_bool("DROPMCP_REPO_FEEDBACK"), False
            ),
            user_subscriptions_enabled=_first(
                user_subscriptions_enabled,
                _env_bool("DROPMCP_USER_SUBSCRIPTIONS"),
                False,
            ),
            user_header=_first(
                user_header, _env("DROPMCP_USER_HEADER"), DEFAULT_USER_HEADER
            ),
            reload=_first(reload, _env_bool("DROPMCP_RELOAD"), False),
            database_url=_resolve_database_url(database_url, skills_dir),
            eval_results_project=_first(
                eval_results_project, _env("DROPMCP_EVAL_RESULTS_PROJECT")
            ),
            eval_results_commit_sha=_resolve_commit_sha(
                eval_results_commit_sha, skills_dir
            ),
            eval_results_store=eval_results_store,
            benchmarks_enabled=_first(
                benchmarks_enabled, _env_bool("DROPMCP_BENCHMARKS"), False
            ),
            benchmark_results_store=benchmark_results_store,
            memory_enabled=_first(
                memory_enabled, _env_bool("DROPMCP_MEMORY"), False
            ),
            memory_embedder=memory_embedder,
            memory_vocabulary=_resolve_memory_vocabulary(memory_vocabulary),
            memory_lint_rules=tuple(memory_lint_rules or ()),
            memory_store=memory_store,
            memory_candidate_cap=int(
                _first(
                    memory_candidate_cap,
                    _env("DROPMCP_MEMORY_CANDIDATE_CAP"),
                    DEFAULT_MEMORY_CANDIDATE_CAP,
                )
            ),
        )
