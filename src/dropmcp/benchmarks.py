from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import fmean
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 60
SERIES_LENGTH = 12
CACHE_TTL_SECONDS = 300
FAILURE_TTL_SECONDS = 30
UNAVAILABLE_MESSAGE = (
    "Benchmark results are temporarily unavailable. Try again in a minute."
)


@dataclass(frozen=True)
class BenchmarkResult:
    test_name: str
    worker_model: str
    passed: bool
    score: float
    threshold: float
    triggered_at: int
    pipeline_id: str
    commit_sha: str


@runtime_checkable
class BenchmarkResultsStore(Protocol):
    def get_latest_benchmark_results(
        self, project: str, lookback_days: int
    ) -> list[BenchmarkResult]: ...


class InMemoryBenchmarkResultsStore:
    def __init__(self, results: list[BenchmarkResult] | None = None) -> None:
        self._results = list(results or [])

    def get_latest_benchmark_results(
        self, project: str, lookback_days: int
    ) -> list[BenchmarkResult]:
        return list(self._results)


def skill_name(test_name: str) -> str:
    segments = test_name.split("/")
    if segments[0] == "prompts" and len(segments) > 1:
        return f"prompts/{segments[1]}"
    return segments[0]


def _recency(result: BenchmarkResult) -> tuple[int, str]:
    return (result.triggered_at, result.pipeline_id)


def _latest(runs: Sequence[BenchmarkResult]) -> BenchmarkResult:
    return max(runs, key=_recency)


def _aggregate(results: Sequence[BenchmarkResult]) -> dict:
    passed = sum(1 for result in results if result.passed)
    if passed == len(results):
        status = "pass"
    elif passed == 0:
        status = "fail"
    else:
        status = "partial"
    return {
        "average_score": round(fmean(result.score for result in results), 1),
        "average_threshold": round(fmean(result.threshold for result in results), 1),
        "passed": passed,
        "total": len(results),
        "status": status,
    }


def _summary(groups: Sequence[Sequence[BenchmarkResult]]) -> dict:
    return {
        **_aggregate([_latest(runs) for runs in groups]),
        "history": _aggregate([run for runs in groups for run in runs]),
    }


def _cell(groups: Sequence[Sequence[BenchmarkResult]]) -> dict:
    newest = max((_latest(runs) for runs in groups), key=_recency)
    return {
        **_summary(groups),
        "triggered_at": newest.triggered_at,
        "pipeline_id": newest.pipeline_id,
        "commit_sha": newest.commit_sha,
    }


def _run(runs: Sequence[BenchmarkResult]) -> dict:
    latest = _latest(runs)
    ordered = sorted(runs, key=_recency)
    return {
        "passed": latest.passed,
        "score": latest.score,
        "threshold": latest.threshold,
        "triggered_at": latest.triggered_at,
        "pipeline_id": latest.pipeline_id,
        "commit_sha": latest.commit_sha,
        "history": _aggregate(runs),
        "series": [run.score for run in ordered[-SERIES_LENGTH:]],
    }


def build_matrix(results: Sequence[BenchmarkResult]) -> dict:
    runs: dict[tuple[str, str], list[BenchmarkResult]] = {}
    for result in results:
        runs.setdefault((result.test_name, result.worker_model), []).append(result)

    models = sorted({model for _, model in runs})

    grouped: dict[str, dict[str, dict[str, list[BenchmarkResult]]]] = {}
    for (test_name, model), model_runs in runs.items():
        tests = grouped.setdefault(skill_name(test_name), {})
        tests.setdefault(test_name, {})[model] = model_runs

    skills = []
    for name in sorted(grouped):
        tests = grouped[name]
        cells = {}
        for model in models:
            model_groups = [
                by_model[model] for by_model in tests.values() if model in by_model
            ]
            if model_groups:
                cells[model] = _cell(model_groups)
        skills.append(
            {
                "name": name,
                "test_count": len(tests),
                "overall": _summary(
                    [
                        model_runs
                        for by_model in tests.values()
                        for model_runs in by_model.values()
                    ]
                ),
                "cells": cells,
                "tests": [
                    {
                        "name": test_name,
                        "results": {
                            model: _run(model_runs)
                            for model, model_runs in sorted(by_model.items())
                        },
                    }
                    for test_name, by_model in sorted(tests.items())
                ],
            }
        )

    summary = {
        model: _summary(
            [model_runs for (_, m), model_runs in runs.items() if m == model]
        )
        for model in models
    }
    return {
        "models": models,
        "test_count": len({test_name for test_name, _ in runs}),
        "summary": summary,
        "skills": skills,
    }


@dataclass(frozen=True)
class _Snapshot:
    matrix: dict
    error: str | None
    fetched_at: datetime
    expires_at: float


class BenchmarkService:
    def __init__(
        self,
        store: BenchmarkResultsStore,
        project: str,
        *,
        lookback_days: int = LOOKBACK_DAYS,
        ttl_seconds: float = CACHE_TTL_SECONDS,
        failure_ttl_seconds: float = FAILURE_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._store = store
        self._project = project
        self._lookback_days = lookback_days
        self._ttl_seconds = ttl_seconds
        self._failure_ttl_seconds = failure_ttl_seconds
        self._clock = clock
        self._lock = asyncio.Lock()
        self._snapshot: _Snapshot | None = None

    def _fresh(self) -> _Snapshot | None:
        snapshot = self._snapshot
        if snapshot is not None and self._clock() < snapshot.expires_at:
            return snapshot
        return None

    async def _refresh(self) -> _Snapshot:
        fetched_at = datetime.now(timezone.utc)
        try:
            results = await asyncio.to_thread(
                self._store.get_latest_benchmark_results,
                self._project,
                self._lookback_days,
            )
        except Exception:
            logger.warning("Failed to load benchmark results", exc_info=True)
            return _Snapshot(
                matrix=build_matrix([]),
                error=UNAVAILABLE_MESSAGE,
                fetched_at=fetched_at,
                expires_at=self._clock() + self._failure_ttl_seconds,
            )
        return _Snapshot(
            matrix=build_matrix(results),
            error=None,
            fetched_at=fetched_at,
            expires_at=self._clock() + self._ttl_seconds,
        )

    async def _load(self) -> _Snapshot:
        snapshot = self._fresh()
        if snapshot is not None:
            return snapshot
        async with self._lock:
            snapshot = self._fresh()
            if snapshot is None:
                snapshot = await self._refresh()
                self._snapshot = snapshot
            return snapshot

    async def payload(self) -> dict:
        snapshot = await self._load()
        return {
            "project": self._project,
            "lookback_days": self._lookback_days,
            "generated_at": snapshot.fetched_at.isoformat(),
            "error": snapshot.error,
            **snapshot.matrix,
        }
