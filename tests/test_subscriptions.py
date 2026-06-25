"""Tests for per-user skill/prompt subscriptions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dropmcp.subscriptions import (
    ITEM_TYPES,
    UserSubscriptionStore,
    item_visible_over_mcp,
    mcp_filtering_active,
    subscription_to_dict,
)


@pytest.fixture
def store(tmp_path):
    url = f"sqlite:///{tmp_path / 'subs.db'}"
    return UserSubscriptionStore(url)


def test_add_list_remove(store):
    store.add("user@example.com", "skill", "my-skill")
    items = store.list_for_user("user@example.com")
    assert len(items) == 1
    assert items[0].item_name == "my-skill"
    assert store.is_subscribed("user@example.com", "skill", "my-skill")

    store.remove("user@example.com", "skill", "my-skill")
    assert store.list_for_user("user@example.com") == []


def test_add_is_idempotent(store):
    store.add("user@example.com", "skill", "a")
    store.add("user@example.com", "skill", "a")
    assert len(store.list_for_user("user@example.com")) == 1


def test_add_many_and_remove_many(store):
    members = [("skill", "a"), ("prompt", "b")]
    store.add_many("user@example.com", members)
    keys = store.subscribed_keys("user@example.com")
    assert keys == {("skill", "a"), ("prompt", "b")}

    store.remove_many("user@example.com", members)
    assert store.subscribed_keys("user@example.com") == set()


def test_subscription_to_dict(store):
    store.add("user@example.com", "skill", "x")
    entry = store.list_for_user("user@example.com")[0]
    d = subscription_to_dict(entry)
    assert d["item_type"] == "skill"
    assert d["item_name"] == "x"
    assert d["created_at"]


def test_item_types_constant():
    assert ITEM_TYPES == frozenset({"skill", "prompt"})


def test_mcp_filtering_active_requires_flag_and_user():
    from dropmcp.config import Settings

    settings = Settings.resolve(
        skills="skills",
        prompts="prompts",
        user_subscriptions_enabled=True,
    )
    assert mcp_filtering_active(settings, "user@example.com") is True
    assert mcp_filtering_active(settings, None) is False

    settings_off = Settings.resolve(
        skills="skills",
        prompts="prompts",
        user_subscriptions_enabled=False,
    )
    assert mcp_filtering_active(settings_off, "user@example.com") is False


def test_item_visible_pure_opt_in(store):
    from dropmcp.config import Settings

    settings = Settings.resolve(
        skills="skills",
        prompts="prompts",
        user_subscriptions_enabled=True,
    )
    assert (
        item_visible_over_mcp(
            settings, store, "user@example.com", "skill", "missing"
        )
        is False
    )
    store.add("user@example.com", "skill", "mine")
    assert (
        item_visible_over_mcp(settings, store, "user@example.com", "skill", "mine")
        is True
    )


def test_item_visible_no_filter_when_anonymous(store):
    from dropmcp.config import Settings

    settings = Settings.resolve(
        skills="skills",
        prompts="prompts",
        user_subscriptions_enabled=True,
    )
    assert (
        item_visible_over_mcp(settings, store, None, "skill", "anything") is True
    )


def test_subscription_store_create_all_only_for_sqlite(tmp_path):
    with patch("dropmcp.subscriptions.MetaData.create_all") as create_all:
        UserSubscriptionStore(f"sqlite:///{tmp_path / 'test.db'}")
        create_all.assert_called_once()

    with (
        patch("dropmcp.subscriptions.create_engine", return_value=MagicMock()),
        patch("dropmcp.subscriptions.MetaData.create_all") as create_all,
    ):
        UserSubscriptionStore("postgresql://user:pass@host/db")
        create_all.assert_not_called()


@pytest.mark.asyncio
async def test_subscription_http_routes(tmp_path):
    from starlette.testclient import TestClient

    from dropmcp.config import Settings
    from dropmcp.server import build_server

    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()
    (skills / "alpha").mkdir()
    (skills / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ncategory: c\ngroup: team-a\ndescription: A\n---\n",
        encoding="utf-8",
    )
    (skills / "beta").mkdir()
    (skills / "beta" / "SKILL.md").write_text(
        "---\nname: beta\ncategory: c\ngroup: team-a\ndescription: B\n---\n",
        encoding="utf-8",
    )

    settings = Settings.resolve(
        skills=skills,
        prompts=prompts,
        ui_enabled=True,
        feedback_enabled=False,
        user_subscriptions_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'db'}",
    )
    mcp = build_server(settings)
    headers = {"X-User-Email": "dev@example.com"}

    with TestClient(mcp.http_app()) as client:
        unauthorized = client.get("/api/subscriptions")
        assert unauthorized.status_code == 401

        catalog = client.get("/catalog", headers=headers)
        body = catalog.json()
        assert body["subscriptions_enabled"] is True
        assert body["user"] == "dev@example.com"
        assert all(item["subscribed"] is False for item in body["items"])

        add = client.post(
            "/api/subscriptions",
            headers=headers,
            json={"item_type": "skill", "item_name": "alpha"},
        )
        assert add.status_code == 200

        listed = client.get("/api/subscriptions", headers=headers)
        assert len(listed.json()["items"]) == 1

        group_add = client.post(
            "/api/subscriptions/group/team-a",
            headers=headers,
        )
        assert group_add.status_code == 200
        assert group_add.json()["count"] == 2

        delete = client.delete(
            "/api/subscriptions/skill/alpha",
            headers=headers,
        )
        assert delete.status_code == 200

        group_remove = client.delete(
            "/api/subscriptions/group/team-a",
            headers=headers,
        )
        assert group_remove.status_code == 200


@pytest.mark.asyncio
async def test_skills_provider_filters_by_subscription(tmp_path, monkeypatch):
    from dropmcp.config import Settings
    from dropmcp.skills import FilteredSkillsProvider

    skills = tmp_path / "skills"
    skills.mkdir()
    for name in ("visible", "hidden"):
        (skills / name).mkdir()
        (skills / name / "SKILL.md").write_text(
            f"---\nname: {name}\ncategory: c\ndescription: {name}\n---\n",
            encoding="utf-8",
        )

    settings = Settings.resolve(
        skills=skills,
        prompts=tmp_path / "prompts",
        user_subscriptions_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'db'}",
    )
    store = UserSubscriptionStore(settings.database_url)
    provider = FilteredSkillsProvider(
        roots=skills,
        subscription_store=store,
        subscription_settings=settings,
    )

    monkeypatch.setattr(
        "dropmcp.skills.resolve_mcp_user", lambda _settings: "dev@example.com"
    )
    tools = await provider._list_tools()
    assert tools == []

    store.add("dev@example.com", "skill", "visible")
    tools = await provider._list_tools()
    assert [t.name for t in tools] == ["visible"]

    monkeypatch.setattr("dropmcp.skills.resolve_mcp_user", lambda _settings: None)
    tools = await provider._list_tools()
    assert {t.name for t in tools} == {"visible", "hidden"}

