"""Tests for pluggable E2E eval-results store and telemetry HTTP routes."""

from __future__ import annotations

import pytest

from dropmcp.eval_results import (
    EvalResult,
    InMemoryEvalResultsStore,
    format_date,
    format_duration,
    result_view_model,
)
from dropmcp.server import build_server


def _sample_result(
    *,
    test_name: str = "my-skill/basic",
    passed: bool = True,
    commit_sha: str = "abc123def",
    worker_model: str = "claude-sonnet-4",
) -> EvalResult:
    return EvalResult(
        test_name=test_name,
        passed=passed,
        score=95.0 if passed else 0.0,
        threshold=80.0,
        duration_ms=4500,
        reasoning="Looks good." if passed else "Failed checks.",
        error=None,
        worker_model=worker_model,
        triggered_at=1_714_200_000_000,
        pipeline_id="12345",
        commit_sha=commit_sha,
    )


def test_format_duration():
    assert format_duration(500) == "500ms"
    assert format_duration(4500) == "4.5s"
    assert format_duration(120_000) == "2.0m"


def test_format_date_zero():
    assert format_date(0) == "—"


def test_result_view_model():
    vm = result_view_model(_sample_result())
    assert vm["display_score"] == "95.0%"
    assert vm["display_threshold"] == "/80.0%"
    assert vm["display_duration"] == "4.5s"
    assert vm["short_sha"] == "abc123d"


def test_in_memory_store_filters_by_skill_and_commit():
    store = InMemoryEvalResultsStore(
        [
            _sample_result(test_name="my-skill/basic", commit_sha="sha1"),
            _sample_result(test_name="my-skill/advanced", commit_sha="sha1"),
            _sample_result(test_name="other-skill/basic", commit_sha="sha1"),
            _sample_result(test_name="my-skill/basic", commit_sha="sha2"),
        ]
    )

    results = store.get_results_for_skill("proj", "my-skill", "sha1")
    assert len(results) == 2
    assert {r.test_name for r in results} == {
        "my-skill/basic",
        "my-skill/advanced",
    }


def test_bundled_catalog_defaults_used_when_unset():
    from dropmcp.config import Settings

    settings = Settings.resolve(skills="skills", prompts="prompts")
    assert settings.catalog_defaults_dir.is_dir()
    assert (settings.catalog_defaults_dir / "default.svg").is_file()


def test_in_memory_store_all_latest():
    store = InMemoryEvalResultsStore(
        [
            _sample_result(test_name="a/one", commit_sha="sha1", worker_model="model-a"),
            _sample_result(test_name="a/one", commit_sha="sha1", worker_model="model-b"),
            _sample_result(test_name="b/two", commit_sha="sha1"),
        ]
    )
    all_results = store.get_all_latest_results("proj", "sha1")
    assert set(all_results) == {"a/one", "b/two"}
    assert len(all_results["a/one"]) == 2
    assert {r.worker_model for r in all_results["a/one"]} == {
        "model-a",
        "model-b",
    }


@pytest.mark.asyncio
async def test_telemetry_routes_with_in_memory_store(tmp_path):
    from starlette.testclient import TestClient

    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()

    store = InMemoryEvalResultsStore(
        [
            _sample_result(test_name="demo-skill/basic", commit_sha="deadbeef"),
            _sample_result(
                test_name="demo-skill/basic",
                passed=False,
                commit_sha="deadbeef",
            ),
        ]
    )

    from dropmcp.config import Settings

    settings = Settings.resolve(
        skills=skills,
        prompts=prompts,
        ui_enabled=True,
        feedback_enabled=False,
        eval_results_project="test/project",
        eval_results_commit_sha="deadbeef",
        eval_results_store=store,
    )
    mcp = build_server(settings)

    with TestClient(mcp.http_app()) as client:
        all_response = client.get("/api/telemetry")
        assert all_response.status_code == 200
        all_body = all_response.json()
        assert "demo-skill/basic" in all_body["results"]
        assert len(all_body["results"]["demo-skill/basic"]) == 2
        assert all_body["commit_sha"] == "deadbeef"

        skill_response = client.get("/api/telemetry/demo-skill")
        assert skill_response.status_code == 200
        skill_body = skill_response.json()
        assert len(skill_body["results"]) == 2
        assert skill_body["skill_name"] == "demo-skill"

        health = client.get("/health")
        assert health.json()["commit_sha"] == "deadbeef"
