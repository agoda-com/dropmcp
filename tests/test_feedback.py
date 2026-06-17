"""Tests for agent feedback storage, MCP tool, and HTTP serializers."""

from __future__ import annotations

import pytest

from dropmcp.feedback import (
    FeedbackProvider,
    FeedbackStore,
    feedback_to_dict,
)


@pytest.fixture
def store(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    return FeedbackStore(url)


def test_insert_and_list(store):
    entry_id = store.insert(
        feedback="Used bespoke cache instead of CacheAside.",
        better_instruction="Prefer CacheAside<T> from Agoda.Caching.",
        model="claude-opus-4.8",
        suggested_skill="csharp-caching-cacheaside",
        client="cursor",
        skill_name="agent-feedback",
        repo="supply BFF",
    )
    assert entry_id

    items = store.list()
    assert len(items) == 1
    item = items[0]
    assert item.id == entry_id
    assert item.feedback.startswith("Used bespoke")
    assert item.status == "new"
    assert item.client == "cursor"
    assert item.skill_name == "agent-feedback"


def test_list_search_filter(store):
    store.insert(
        feedback="Missed null branch tests.",
        better_instruction="Ship tests for each branch.",
        model="gpt-5.3-codex",
        client="cursor",
    )
    store.insert(
        feedback="Wrong DI pattern.",
        better_instruction="Use Agoda.IoC attributes.",
        model="claude-opus-4.8",
        client="claude-cli",
    )

    assert len(store.list(search="null branch")) == 1
    assert len(store.list(model="gpt-5.3-codex")) == 1
    assert len(store.list(client="claude-cli")) == 1
    assert len(store.list(status="new")) == 2


def test_patch_status_and_resolution(store):
    entry_id = store.insert(
        feedback="Forgot tests.",
        better_instruction="Add tests with code changes.",
        model="unknown",
    )
    updated = store.patch(
        entry_id,
        status="triaged",
        resolution_url="https://example.com/skill/42",
    )
    assert updated is not None
    assert updated.status == "triaged"
    assert updated.resolution_url == "https://example.com/skill/42"

    updated = store.patch(entry_id, status="actioned")
    assert updated is not None
    assert updated.status == "actioned"


def test_patch_invalid_status_raises(store):
    entry_id = store.insert(
        feedback="x",
        better_instruction="y",
        model="m",
    )
    with pytest.raises(ValueError, match="invalid status"):
        store.patch(entry_id, status="bogus")


def test_patch_missing_returns_none(store):
    assert store.patch("missing-id", status="triaged") is None


def test_feedback_to_dict_iso_dates(store):
    entry_id = store.insert(
        feedback="a",
        better_instruction="b",
        model="m",
    )
    item = store.get(entry_id)
    assert item is not None
    data = feedback_to_dict(item)
    assert data["created_at"].endswith("Z")
    assert data["id"] == entry_id


@pytest.mark.asyncio
async def test_record_feedback_tool_writes_row(store):
    provider = FeedbackProvider(store)
    tool = await provider._get_tool("record_feedback")
    assert tool is not None

    result = await tool.run(
        {
            "feedback": "Skipped branch tests.",
            "better_instruction": "Cover each branch in the same change.",
            "model": "composer-2.5",
            "suggested_skill": "tests-cover-branches",
        }
    )
    assert "recorded" in result.content[0].text.lower()
    assert len(store.list()) == 1


@pytest.mark.asyncio
async def test_record_feedback_tool_missing_fields(store):
    provider = FeedbackProvider(store)
    tool = await provider._get_tool("record_feedback")
    result = await tool.run({"feedback": "only one field"})
    assert "not recorded" in result.content[0].text.lower()
    assert store.list() == []


def test_database_url_from_env(monkeypatch, tmp_path):
    db_path = tmp_path / "custom.db"
    monkeypatch.setenv("DROPMCP_DATABASE_URL", f"sqlite:///{db_path}")
    from dropmcp.config import Settings

    settings = Settings.resolve(skills=tmp_path / "skills")
    assert settings.database_url == f"sqlite:///{db_path}"
