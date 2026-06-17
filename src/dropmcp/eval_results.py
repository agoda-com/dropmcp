"""Pluggable E2E eval-results store for the catalog telemetry panel.

dropmcp is a generic library — StarRocks and other deployment-specific backends
live behind ``EvalResultsStore``. Pass a store to ``create_server()`` or set
``DROPMCP_EVAL_RESULTS_PROJECT`` (with the optional ``starrocks`` extra) to
enable the ``/api/telemetry`` routes automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class EvalResult:
    """A single skill/prompt E2E evaluation result."""

    test_name: str
    passed: bool
    score: float
    threshold: float
    duration_ms: int
    reasoning: str
    error: str | None
    worker_model: str
    triggered_at: int
    pipeline_id: str
    commit_sha: str


@runtime_checkable
class EvalResultsStore(Protocol):
    """Backend for per-skill and all-skill eval results at a given commit."""

    def get_results_for_skill(
        self, project: str, skill_name: str, commit_sha: str
    ) -> list[EvalResult]: ...

    def get_all_latest_results(
        self, project: str, commit_sha: str
    ) -> dict[str, EvalResult]: ...


def format_duration(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    if ms < 60000:
        return f"{ms / 1000:.1f}s"
    return f"{ms / 60000:.1f}m"


def format_date(epoch_ms: int) -> str:
    if not epoch_ms:
        return "—"
    try:
        dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
        return dt.strftime("%b %-d, %-I:%M %p UTC")
    except (ValueError, TypeError, OSError):
        return str(epoch_ms)


def result_view_model(result: EvalResult) -> dict:
    return {
        "passed": result.passed,
        "score": result.score,
        "threshold": result.threshold,
        "display_score": f"{result.score}%",
        "display_threshold": f"/{result.threshold}%",
        "display_duration": format_duration(result.duration_ms),
        "display_date": format_date(result.triggered_at),
        "reasoning": result.reasoning,
        "error": result.error,
        "worker_model": result.worker_model,
        "pipeline_id": result.pipeline_id,
        "short_sha": (result.commit_sha or "")[:7],
    }


class InMemoryEvalResultsStore:
    """Simple in-memory store for tests and local demos."""

    def __init__(self, results: list[EvalResult] | None = None) -> None:
        self._results = list(results or [])

    def get_results_for_skill(
        self, project: str, skill_name: str, commit_sha: str
    ) -> list[EvalResult]:
        prefix = f"{skill_name}/"
        return [
            r
            for r in self._results
            if r.commit_sha == commit_sha and r.test_name.startswith(prefix)
        ]

    def get_all_latest_results(
        self, project: str, commit_sha: str
    ) -> dict[str, EvalResult]:
        out: dict[str, EvalResult] = {}
        for r in self._results:
            if r.commit_sha == commit_sha:
                out[r.test_name] = r
        return out


def resolve_starrocks_store() -> EvalResultsStore | None:
    """Return a StarRocks-backed store when the optional extra is installed."""
    try:
        from dropmcp.eval_results_starrocks import StarRocksEvalResultsStore
    except ImportError:
        return None
    return StarRocksEvalResultsStore()
