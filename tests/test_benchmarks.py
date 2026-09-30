from __future__ import annotations

import asyncio

import pytest
from starlette.testclient import TestClient

from dropmcp.benchmarks import (
    UNAVAILABLE_MESSAGE,
    BenchmarkResult,
    BenchmarkResultsStore,
    BenchmarkService,
    InMemoryBenchmarkResultsStore,
    build_matrix,
    skill_name,
)
from dropmcp.config import Settings
from dropmcp.server import build_server

IDENTITY = {"X-User-Email": "dev@example.com"}


def _result(
    *,
    test_name: str = "alpha/basic",
    worker_model: str = "model-a",
    passed: bool = True,
    score: float = 90.0,
    threshold: float = 80.0,
    triggered_at: int = 1_714_200_000_000,
    pipeline_id: str = "100",
    commit_sha: str = "abc123def",
) -> BenchmarkResult:
    return BenchmarkResult(
        test_name=test_name,
        worker_model=worker_model,
        passed=passed,
        score=score,
        threshold=threshold,
        triggered_at=triggered_at,
        pipeline_id=pipeline_id,
        commit_sha=commit_sha,
    )


class RecordingStore:
    def __init__(self, results=None, error: Exception | None = None) -> None:
        self.results = list(results or [])
        self.error = error
        self.calls: list[tuple[str, int]] = []

    def get_latest_benchmark_results(self, project, lookback_days):
        self.calls.append((project, lookback_days))
        if self.error is not None:
            raise self.error
        return list(self.results)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _settings(tmp_path, **overrides) -> Settings:
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir(exist_ok=True)
    prompts.mkdir(exist_ok=True)
    options = {
        "skills": skills,
        "prompts": prompts,
        "ui_enabled": True,
        "feedback_enabled": False,
        "eval_results_project": "org/repo",
        "benchmarks_enabled": True,
    }
    options.update(overrides)
    return Settings.resolve(**options)


def test_skill_name_groups_prompts_separately():
    assert skill_name("alpha/basic") == "alpha"
    assert skill_name("alpha/nested/deep") == "alpha"
    assert skill_name("prompts/greet/basic") == "prompts/greet"
    assert skill_name("standalone") == "standalone"


def test_build_matrix_empty():
    assert build_matrix([]) == {
        "models": [],
        "test_count": 0,
        "summary": {},
        "skills": [],
    }


def test_build_matrix_history_covers_every_run_while_cells_stay_latest():
    matrix = build_matrix(
        [
            _result(score=40, passed=False, triggered_at=1, pipeline_id="1"),
            _result(score=60, passed=False, triggered_at=2, pipeline_id="2"),
            _result(score=95, passed=True, triggered_at=3, pipeline_id="3"),
        ]
    )

    cell = matrix["skills"][0]["cells"]["model-a"]
    assert cell["average_score"] == 95
    assert cell["status"] == "pass"
    assert cell["history"] == {
        "average_score": 65.0,
        "average_threshold": 80.0,
        "passed": 1,
        "total": 3,
        "status": "partial",
    }


def test_build_matrix_test_result_carries_history_and_score_series():
    matrix = build_matrix(
        [
            _result(score=score, triggered_at=index, pipeline_id=str(index))
            for index, score in enumerate([50, 70, 90], start=1)
        ]
    )

    result = matrix["skills"][0]["tests"][0]["results"]["model-a"]
    assert result["score"] == 90
    assert result["history"]["average_score"] == 70.0
    assert result["history"]["total"] == 3
    assert result["series"] == [50, 70, 90]


def test_build_matrix_series_keeps_only_the_newest_runs_oldest_first():
    matrix = build_matrix(
        [
            _result(score=float(index), triggered_at=index, pipeline_id=str(index))
            for index in range(1, 21)
        ]
    )

    series = matrix["skills"][0]["tests"][0]["results"]["model-a"]["series"]
    assert series == [float(index) for index in range(9, 21)]


def test_build_matrix_summarises_each_model_across_all_of_its_tests():
    matrix = build_matrix(
        [
            _result(test_name="alpha/one", worker_model="model-a", score=90),
            _result(
                test_name="beta/one",
                worker_model="model-a",
                score=60,
                passed=False,
            ),
            _result(test_name="alpha/one", worker_model="model-b", score=100),
            _result(test_name="alpha/one", worker_model="model-b", score=0,
                    passed=False, triggered_at=1, pipeline_id="1"),
        ]
    )

    assert matrix["test_count"] == 2
    model_a = matrix["summary"]["model-a"]
    assert (model_a["average_score"], model_a["passed"], model_a["total"]) == (75, 1, 2)
    assert model_a["status"] == "partial"
    model_b = matrix["summary"]["model-b"]
    assert model_b["total"] == 1
    assert model_b["average_score"] == 100
    assert model_b["history"]["average_score"] == 50.0
    assert model_b["history"]["total"] == 2


def test_build_matrix_summarises_each_skill_across_models():
    matrix = build_matrix(
        [
            _result(test_name="alpha/one", worker_model="model-a", score=90),
            _result(test_name="alpha/one", worker_model="model-b", score=50,
                    passed=False),
            _result(test_name="alpha/two", worker_model="model-a", score=70),
        ]
    )

    overall = matrix["skills"][0]["overall"]
    assert overall["total"] == 3
    assert overall["passed"] == 2
    assert overall["average_score"] == 70
    assert overall["status"] == "partial"


def test_build_matrix_keeps_latest_run_per_test_and_model():
    matrix = build_matrix(
        [
            _result(passed=False, score=10, triggered_at=1, pipeline_id="1"),
            _result(passed=True, score=95, triggered_at=2, pipeline_id="2"),
        ]
    )

    cell = matrix["skills"][0]["cells"]["model-a"]
    assert cell["total"] == 1
    assert cell["passed"] == 1
    assert cell["status"] == "pass"
    assert cell["average_score"] == 95
    assert cell["pipeline_id"] == "2"


def test_build_matrix_breaks_timestamp_ties_by_pipeline_id():
    matrix = build_matrix(
        [
            _result(score=10, triggered_at=5, pipeline_id="102"),
            _result(score=20, triggered_at=5, pipeline_id="101"),
        ]
    )

    assert matrix["skills"][0]["cells"]["model-a"]["pipeline_id"] == "102"
    assert matrix["skills"][0]["cells"]["model-a"]["average_score"] == 10


def test_build_matrix_groups_tests_under_skills_and_prompts():
    matrix = build_matrix(
        [
            _result(test_name="beta/one"),
            _result(test_name="alpha/two"),
            _result(test_name="alpha/one"),
            _result(test_name="prompts/greet/basic"),
        ]
    )

    assert [skill["name"] for skill in matrix["skills"]] == [
        "alpha",
        "beta",
        "prompts/greet",
    ]
    alpha = matrix["skills"][0]
    assert alpha["test_count"] == 2
    assert [test["name"] for test in alpha["tests"]] == ["alpha/one", "alpha/two"]


def test_build_matrix_cell_status_reflects_pass_ratio():
    matrix = build_matrix(
        [
            _result(test_name="mixed/one", passed=True),
            _result(test_name="mixed/two", passed=False),
            _result(test_name="failing/one", passed=False),
            _result(test_name="failing/two", passed=False),
            _result(test_name="passing/one", passed=True),
        ]
    )

    status = {
        skill["name"]: skill["cells"]["model-a"]["status"]
        for skill in matrix["skills"]
    }
    assert status == {"failing": "fail", "mixed": "partial", "passing": "pass"}


def test_build_matrix_averages_score_and_threshold_across_tests():
    matrix = build_matrix(
        [
            _result(test_name="alpha/one", score=91.0, threshold=80.0),
            _result(test_name="alpha/two", score=86.0, threshold=70.0),
        ]
    )

    cell = matrix["skills"][0]["cells"]["model-a"]
    assert cell["average_score"] == 88.5
    assert cell["average_threshold"] == 75.0


def test_build_matrix_omits_models_that_did_not_run_a_skill():
    matrix = build_matrix(
        [
            _result(test_name="alpha/one", worker_model="model-a"),
            _result(test_name="beta/one", worker_model="model-b"),
        ]
    )

    assert matrix["models"] == ["model-a", "model-b"]
    alpha, beta = matrix["skills"]
    assert set(alpha["cells"]) == {"model-a"}
    assert set(alpha["tests"][0]["results"]) == {"model-a"}
    assert set(beta["cells"]) == {"model-b"}


def test_in_memory_store_satisfies_protocol():
    assert isinstance(InMemoryBenchmarkResultsStore(), BenchmarkResultsStore)


@pytest.mark.asyncio
async def test_service_passes_project_and_lookback_to_store():
    store = RecordingStore([_result()])
    service = BenchmarkService(store, "org/repo", lookback_days=14)

    payload = await service.payload()

    assert store.calls == [("org/repo", 14)]
    assert payload["project"] == "org/repo"
    assert payload["lookback_days"] == 14
    assert payload["error"] is None
    assert payload["models"] == ["model-a"]
    assert payload["skills"][0]["name"] == "alpha"
    assert payload["generated_at"]


@pytest.mark.asyncio
async def test_service_caches_until_ttl_expires():
    clock = Clock()
    store = RecordingStore([_result()])
    service = BenchmarkService(store, "org/repo", ttl_seconds=300, clock=clock)

    await service.payload()
    clock.now = 299
    await service.payload()
    assert len(store.calls) == 1

    clock.now = 301
    await service.payload()
    assert len(store.calls) == 2


@pytest.mark.asyncio
async def test_service_loads_once_for_concurrent_requests():
    store = RecordingStore([_result()])
    service = BenchmarkService(store, "org/repo", clock=Clock())

    await asyncio.gather(*(service.payload() for _ in range(5)))

    assert len(store.calls) == 1


@pytest.mark.asyncio
async def test_service_reports_failure_then_retries_after_short_ttl():
    clock = Clock()
    store = RecordingStore(error=RuntimeError("boom"))
    service = BenchmarkService(
        store, "org/repo", ttl_seconds=300, failure_ttl_seconds=30, clock=clock
    )

    failed = await service.payload()
    assert failed["error"] == UNAVAILABLE_MESSAGE
    assert failed["models"] == []
    assert failed["skills"] == []
    assert failed["summary"] == {}
    assert failed["test_count"] == 0
    assert "boom" not in str(failed)

    clock.now = 29
    await service.payload()
    assert len(store.calls) == 1

    store.error = None
    store.results = [_result()]
    clock.now = 31
    recovered = await service.payload()
    assert len(store.calls) == 2
    assert recovered["error"] is None
    assert recovered["skills"][0]["name"] == "alpha"


def test_endpoint_requires_identity(tmp_path):
    store = RecordingStore([_result()])
    mcp = build_server(_settings(tmp_path, benchmark_results_store=store))

    with TestClient(mcp.http_app()) as client:
        response = client.get("/api/benchmarks")

    assert response.status_code == 401
    assert response.json() == {"error": "identity header required"}
    assert response.headers["cache-control"] == "no-store"
    assert store.calls == []


def test_endpoint_serves_matrix_with_hardened_headers(tmp_path):
    store = RecordingStore([_result(), _result(worker_model="model-b")])
    mcp = build_server(_settings(tmp_path, benchmark_results_store=store))

    with TestClient(mcp.http_app()) as client:
        response = client.get("/api/benchmarks", headers=IDENTITY)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    body = response.json()
    assert body["project"] == "org/repo"
    assert body["models"] == ["model-a", "model-b"]
    assert body["error"] is None


def test_endpoint_ignores_project_override(tmp_path):
    store = RecordingStore([_result()])
    mcp = build_server(_settings(tmp_path, benchmark_results_store=store))

    with TestClient(mcp.http_app()) as client:
        response = client.get(
            "/api/benchmarks?project=other/team-repo", headers=IDENTITY
        )

    assert response.json()["project"] == "org/repo"
    assert store.calls == [("org/repo", 60)]


def test_endpoint_exposes_only_scores_never_reasoning_or_errors(tmp_path):
    store = RecordingStore([_result()])
    mcp = build_server(_settings(tmp_path, benchmark_results_store=store))

    with TestClient(mcp.http_app()) as client:
        body = client.get("/api/benchmarks", headers=IDENTITY).json()

    skill = body["skills"][0]
    aggregate = {
        "average_score",
        "average_threshold",
        "passed",
        "total",
        "status",
    }
    assert set(body) == {
        "project",
        "lookback_days",
        "generated_at",
        "error",
        "models",
        "test_count",
        "summary",
        "skills",
    }
    assert set(skill) == {"name", "test_count", "overall", "cells", "tests"}
    assert set(body["summary"]["model-a"]) == aggregate | {"history"}
    assert set(body["summary"]["model-a"]["history"]) == aggregate
    assert set(skill["overall"]) == aggregate | {"history"}
    assert set(skill["cells"]["model-a"]) == aggregate | {
        "history",
        "triggered_at",
        "pipeline_id",
        "commit_sha",
    }
    assert set(skill["tests"][0]["results"]["model-a"]) == {
        "passed",
        "score",
        "threshold",
        "triggered_at",
        "pipeline_id",
        "commit_sha",
        "history",
        "series",
    }
    assert set(skill["tests"][0]["results"]["model-a"]["history"]) == aggregate


def test_endpoint_reports_outage_without_leaking_cause(tmp_path):
    store = RecordingStore(error=RuntimeError("host=internal.example password=x"))
    mcp = build_server(_settings(tmp_path, benchmark_results_store=store))

    with TestClient(mcp.http_app()) as client:
        response = client.get("/api/benchmarks", headers=IDENTITY)

    assert response.status_code == 200
    assert response.json()["error"] == UNAVAILABLE_MESSAGE
    assert "internal.example" not in response.text


def test_endpoint_absent_when_disabled(tmp_path):
    mcp = build_server(_settings(tmp_path, benchmarks_enabled=False))

    with TestClient(mcp.http_app()) as client:
        response = client.get("/api/benchmarks", headers=IDENTITY)
        catalog = client.get("/catalog").json()

    assert response.headers["content-type"].startswith("text/html")
    assert catalog["benchmarks_enabled"] is False


def test_catalog_reports_benchmarks_enabled(tmp_path):
    mcp = build_server(
        _settings(tmp_path, benchmark_results_store=RecordingStore())
    )

    with TestClient(mcp.http_app()) as client:
        catalog = client.get("/catalog").json()

    assert catalog["benchmarks_enabled"] is True


def test_enabled_without_project_fails_at_startup(tmp_path):
    with pytest.raises(ValueError, match="eval_results_project"):
        build_server(
            _settings(
                tmp_path,
                eval_results_project=None,
                benchmark_results_store=RecordingStore(),
            )
        )


def test_enabled_without_store_fails_at_startup(tmp_path):
    with pytest.raises(ValueError, match="benchmark_results_store"):
        build_server(_settings(tmp_path))


def test_eval_results_store_is_not_accepted_as_benchmark_store(tmp_path):
    class EvalOnly:
        def get_results_for_skill(self, project, skill_name, commit_sha):
            return []

        def get_all_latest_results(self, project, commit_sha):
            return {}

    with pytest.raises(ValueError, match="benchmark_results_store"):
        build_server(_settings(tmp_path, benchmark_results_store=EvalOnly()))


def test_eval_results_env_queries_do_not_enable_benchmarks(tmp_path, monkeypatch):
    monkeypatch.setenv("DROPMCP_EVAL_RESULTS_SKILL_QUERY", "SELECT 1")
    monkeypatch.setenv("DROPMCP_EVAL_RESULTS_ALL_QUERY", "SELECT 1")

    with pytest.raises(ValueError, match="benchmark_results_store"):
        build_server(_settings(tmp_path))


def test_benchmarks_setting_resolution(monkeypatch, tmp_path):
    def resolve(**overrides) -> bool:
        return Settings.resolve(
            skills=tmp_path, prompts=tmp_path, **overrides
        ).benchmarks_enabled

    monkeypatch.delenv("DROPMCP_BENCHMARKS", raising=False)
    assert resolve() is False

    monkeypatch.setenv("DROPMCP_BENCHMARKS", "true")
    assert resolve() is True
    assert resolve(benchmarks_enabled=False) is False
