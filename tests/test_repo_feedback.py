"""Tests for repository feedback storage, MCP tool, and HTTP serializers."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from dropmcp.repo_feedback import (
    REPO_FEEDBACK_CATEGORIES,
    RepoFeedbackProvider,
    RepoFeedbackStore,
    make_repo_feedback_fingerprint,
    repo_feedback_to_dict,
)


@pytest.fixture
def store(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    return RepoFeedbackStore(url)


def _insert(
    store: RepoFeedbackStore,
    *,
    category: str = "flaky_test",
    repo: str = "agoda-com/dropmcp",
    summary: str = "Flaky test FeedbackSpec fails intermittently.",
    impact: str = "Could not trust local verification.",
    model: str = "gpt-5.3-codex",
):
    return store.insert(
        category=category,
        repo=repo,
        summary=summary,
        impact=impact,
        model=model,
        client="cursor",
        details={"tests": ["FeedbackSpec"]},
    )


def test_insert_and_list_round_trip(store):
    result = _insert(store)
    assert result.entry.id
    assert result.deduplicated is False

    items = store.list()
    assert len(items) == 1
    item = items[0]
    assert item.id == result.entry.id
    assert item.category == "flaky_test"
    assert item.repo == "agoda-com/dropmcp"
    assert item.summary.startswith("Flaky test")
    assert item.status == "new"
    assert item.occurrence_count == 1
    assert item.details == {"tests": ["FeedbackSpec"]}


def test_invalid_category_raises(store):
    with pytest.raises(ValueError, match="invalid category"):
        _insert(store, category="bad")


def test_fingerprint_normalizes_numbers_case_and_whitespace():
    first = make_repo_feedback_fingerprint(
        "Agoda-Com/DropMCP",
        "flaky_test",
        "Flaky test FeedbackSpec fails 3/10 runs.",
    )
    second = make_repo_feedback_fingerprint(
        "  agoda-com/dropmcp  ",
        "flaky_test",
        "flaky TEST FeedbackSpec fails 4/10   runs.",
    )
    assert first == second


def test_dedupe_bumps_existing_open_row(store):
    first = _insert(
        store,
        summary="Flaky test FeedbackSpec fails 3/10 runs.",
    )
    second = _insert(
        store,
        summary="flaky TEST FeedbackSpec fails 4/10 runs.",
        impact="Had to rerun tests to verify.",
    )

    assert second.deduplicated is True
    assert second.entry.id == first.entry.id
    assert second.entry.occurrence_count == 2
    assert second.entry.last_seen_at >= first.entry.last_seen_at
    assert len(store.list()) == 1


def test_closed_rows_do_not_dedupe(store):
    first = _insert(store)
    patched = store.patch(first.entry.id, status="actioned")
    assert patched is not None
    assert patched.status == "actioned"

    second = _insert(store)
    assert second.deduplicated is False
    assert second.entry.id != first.entry.id
    assert second.entry.details is not None
    assert second.entry.details["previous_entry_id"] == first.entry.id
    assert len(store.list()) == 2


def test_list_filters_and_default_ordering(store):
    low = _insert(
        store,
        category="docs_gap",
        repo="agoda-com/other",
        summary="Missing setup docs for local services.",
        impact="Had to infer local service setup.",
    )
    high = _insert(store, repo="agoda-com/dropmcp")
    _insert(store, repo="agoda-com/dropmcp")

    items = store.list()
    assert items[0].id == high.entry.id
    assert items[0].occurrence_count == 2
    assert items[1].id == low.entry.id

    assert len(store.list(repo="agoda-com/dropmcp")) == 1
    assert len(store.list(category="docs_gap")) == 1
    assert len(store.list(status="new")) == 2
    assert len(store.list(search="local service")) == 1
    assert len(store.list(model="gpt-5.3-codex")) == 2
    assert len(store.list(client="cursor")) == 2


def test_list_recent_sort(store):
    first = _insert(store, summary="Slow build takes a long time.")
    second = _insert(store, summary="Missing docs for setup.")

    recent = store.list(sort="recent")
    assert recent[0].id == second.entry.id
    assert recent[1].id == first.entry.id


def test_patch_status_and_resolution(store):
    entry_id = _insert(store).entry.id
    updated = store.patch(
        entry_id,
        status="triaged",
        resolution_url="https://github.com/agoda-com/dropmcp/pull/99",
    )
    assert updated is not None
    assert updated.status == "triaged"
    assert updated.resolution_url == "https://github.com/agoda-com/dropmcp/pull/99"

    updated = store.patch(entry_id, status="wontfix")
    assert updated is not None
    assert updated.status == "wontfix"


def test_patch_invalid_status_raises(store):
    entry_id = _insert(store).entry.id
    with pytest.raises(ValueError, match="invalid status"):
        store.patch(entry_id, status="bogus")


def test_patch_missing_returns_none(store):
    assert store.patch("missing-id", status="triaged") is None


def test_repo_feedback_to_dict_iso_dates(store):
    entry = _insert(store).entry
    data = repo_feedback_to_dict(entry)
    assert data["created_at"].endswith("Z")
    assert data["last_seen_at"].endswith("Z")
    assert data["id"] == entry.id
    assert data["occurrence_count"] == 1


@pytest.mark.asyncio
async def test_record_repo_feedback_tool_writes_row(store):
    provider = RepoFeedbackProvider(store)
    tool = await provider._get_tool("record_repo_feedback")
    assert tool is not None

    result = await tool.run(
        {
            "category": "tests_require_ci",
            "repo": "agoda-com/dropmcp",
            "summary": "Integration tests only run in CI.",
            "impact": "Could not verify the change locally.",
            "model": "gpt-5.3-codex",
            "details": {"commands": ["pytest tests/integration"]},
        }
    )

    assert "recorded" in result.content[0].text.lower()
    item = store.list()[0]
    assert item.category == "tests_require_ci"
    assert item.details == {"commands": ["pytest tests/integration"]}


@pytest.mark.asyncio
async def test_record_repo_feedback_tool_dedupe_message(store):
    provider = RepoFeedbackProvider(store)
    tool = await provider._get_tool("record_repo_feedback")
    assert tool is not None

    arguments = {
        "category": "flaky_test",
        "repo": "agoda-com/dropmcp",
        "summary": "Flaky test FeedbackSpec fails 3/10 runs.",
        "impact": "Had to rerun tests.",
        "model": "gpt-5.3-codex",
    }
    await tool.run(arguments)
    result = await tool.run(
        {
            **arguments,
            "summary": "flaky TEST FeedbackSpec fails 4/10 runs.",
        }
    )

    assert "already tracked" in result.content[0].text.lower()
    assert "occurrences=2" in result.content[0].text


@pytest.mark.asyncio
async def test_record_repo_feedback_tool_validation(store):
    provider = RepoFeedbackProvider(store)
    tool = await provider._get_tool("record_repo_feedback")
    assert tool is not None

    missing = await tool.run({"category": "flaky_test", "summary": "x"})
    assert "not recorded" in missing.content[0].text.lower()

    bad_category = await tool.run(
        {
            "category": "bad",
            "repo": "agoda-com/dropmcp",
            "summary": "x",
            "impact": "y",
            "model": "m",
        }
    )
    assert "category must be one of" in bad_category.content[0].text

    bad_details = await tool.run(
        {
            "category": "flaky_test",
            "repo": "agoda-com/dropmcp",
            "summary": "x",
            "impact": "y",
            "model": "m",
            "details": "not-object",
        }
    )
    assert "details must be an object" in bad_details.content[0].text
    assert store.list() == []


def test_repo_feedback_provider_initializes_transforms(store):
    provider = RepoFeedbackProvider(store)
    assert provider._transforms == []


@pytest.mark.asyncio
async def test_record_repo_feedback_in_aggregated_tool_list(tmp_path):
    from dropmcp.config import Settings
    from dropmcp.server import build_server

    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()

    settings = Settings.resolve(
        skills=skills,
        prompts=prompts,
        feedback_enabled=False,
        repo_feedback_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'db'}",
    )
    mcp = build_server(settings)
    tools = await mcp._list_tools()
    names = {t.name for t in tools}
    assert "record_repo_feedback" in names


@pytest.mark.asyncio
async def test_record_repo_feedback_disabled_by_default(tmp_path):
    from dropmcp.config import Settings
    from dropmcp.server import build_server

    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()

    settings = Settings.resolve(
        skills=skills,
        prompts=prompts,
        feedback_enabled=False,
        database_url=f"sqlite:///{tmp_path / 'db'}",
    )
    assert settings.repo_feedback_enabled is False

    mcp = build_server(settings)
    tools = await mcp._list_tools()
    names = {t.name for t in tools}
    assert "record_repo_feedback" not in names


def test_repo_feedback_enabled_from_env(monkeypatch, tmp_path):
    from dropmcp.config import Settings

    monkeypatch.setenv("DROPMCP_REPO_FEEDBACK", "true")
    settings = Settings.resolve(skills=tmp_path / "skills")
    assert settings.repo_feedback_enabled is True


def test_repo_feedback_store_create_all_only_for_sqlite(tmp_path):
    with patch("dropmcp.repo_feedback.MetaData.create_all") as create_all:
        RepoFeedbackStore(f"sqlite:///{tmp_path / 'test.db'}")
        create_all.assert_called_once()

    with (
        patch("dropmcp.repo_feedback.create_engine", return_value=MagicMock()),
        patch("dropmcp.repo_feedback.MetaData.create_all") as create_all,
    ):
        RepoFeedbackStore("postgresql://user:pass@host/db")
        create_all.assert_not_called()


def test_repo_feedback_store_ensures_sqlite_columns_for_existing_db(tmp_path):
    db_path = tmp_path / "old.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE repo_feedback (
                id VARCHAR(36) PRIMARY KEY,
                created_at DATETIME NOT NULL,
                category VARCHAR(32) NOT NULL,
                repo VARCHAR(256) NOT NULL,
                summary TEXT NOT NULL,
                impact TEXT NOT NULL,
                model VARCHAR(128) NOT NULL,
                client VARCHAR(64),
                status VARCHAR(16) NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO repo_feedback (
                id, created_at, category, repo, summary, impact, model, status
            ) VALUES (
                'old', '2026-06-17 10:00:00', 'other', 'repo', 'Legacy row.',
                'Default it.', 'm', 'new'
            )
            """
        )

    store = RepoFeedbackStore(f"sqlite:///{db_path}")
    item = store.list()[0]
    assert item.id == "old"
    assert item.last_seen_at == "2026-06-17T10:00:00Z"
    assert item.suggested_fix is None
    assert item.details is None
    assert item.occurrence_count == 1

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(repo_feedback)")}
    assert {
        "last_seen_at",
        "suggested_fix",
        "details",
        "fingerprint",
        "occurrence_count",
        "resolution_url",
    } <= columns


@pytest.mark.asyncio
async def test_repo_feedback_http_routes(tmp_path):
    from starlette.testclient import TestClient

    from dropmcp.config import Settings
    from dropmcp.server import build_server

    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()
    db_url = f"sqlite:///{tmp_path / 'db'}"

    store = RepoFeedbackStore(db_url)
    entry_id = _insert(store, category=REPO_FEEDBACK_CATEGORIES[0]).entry.id

    settings = Settings.resolve(
        skills=skills,
        prompts=prompts,
        ui_enabled=True,
        feedback_enabled=False,
        repo_feedback_enabled=True,
        database_url=db_url,
    )
    mcp = build_server(settings)

    with TestClient(mcp.http_app()) as client:
        catalog = client.get("/catalog")
        assert catalog.status_code == 200
        assert catalog.json()["repo_feedback_enabled"] is True

        listed = client.get("/api/repo-feedback?category=tests_require_ci")
        assert listed.status_code == 200
        assert listed.json()["items"][0]["id"] == entry_id

        fetched = client.get(f"/api/repo-feedback/{entry_id}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == entry_id

        patched = client.patch(
            f"/api/repo-feedback/{entry_id}",
            json={
                "status": "wontfix",
                "resolution_url": "https://github.com/agoda-com/dropmcp/issues/34",
            },
        )
        assert patched.status_code == 200
        assert patched.json()["status"] == "wontfix"

        invalid = client.patch(f"/api/repo-feedback/{entry_id}", json={"status": "bad"})
        assert invalid.status_code == 400

        missing = client.get("/api/repo-feedback/missing")
        assert missing.status_code == 404
