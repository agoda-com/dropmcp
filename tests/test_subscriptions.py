"""Tests for per-user skill/prompt subscriptions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dropmcp.subscriptions import (
    ITEM_TYPES,
    UserSubscriptionStore,
    group_subscription_to_dict,
    item_visible_over_mcp,
    mcp_filtering_active,
    subscription_to_dict,
)


@pytest.fixture
def store(tmp_path):
    url = f"sqlite:///{tmp_path / 'subs.db'}"
    return UserSubscriptionStore(url)


def test_add_list_remove_direct_subscription(store):
    store.add_item("user@example.com", "skill", "my-skill")
    items = store.list_for_user("user@example.com")
    assert len(items) == 1
    assert items[0].item_name == "my-skill"
    assert store.is_visible("user@example.com", "skill", "my-skill")

    store.remove_item("user@example.com", "skill", "my-skill")
    assert store.list_for_user("user@example.com") == []
    assert not store.is_visible("user@example.com", "skill", "my-skill")


def test_add_item_is_idempotent(store):
    store.add_item("user@example.com", "skill", "a")
    store.add_item("user@example.com", "skill", "a")
    assert len(store.list_for_user("user@example.com")) == 1


def test_group_subscription_includes_members(store):
    store.add_group("user@example.com", "team-a")
    assert store.is_visible("user@example.com", "skill", "alpha", group="team-a")
    assert store.is_visible("user@example.com", "skill", "beta", group="team-a")
    assert not store.is_visible("user@example.com", "skill", "gamma", group="other")


def test_new_group_skill_visible_without_extra_rows(store):
    store.add_group("user@example.com", "team-a")
    assert store.is_visible("user@example.com", "skill", "new-skill", group="team-a")


def test_opt_out_within_subscribed_group(store):
    store.add_group("user@example.com", "team-a")
    store.remove_item("user@example.com", "skill", "alpha", group="team-a")
    assert not store.is_visible("user@example.com", "skill", "alpha", group="team-a")
    assert store.is_visible("user@example.com", "skill", "beta", group="team-a")


def test_re_opt_in_clears_group_exclusion(store):
    store.add_group("user@example.com", "team-a")
    store.remove_item("user@example.com", "skill", "alpha", group="team-a")
    store.add_item("user@example.com", "skill", "alpha")
    assert store.is_visible("user@example.com", "skill", "alpha", group="team-a")


def test_remove_group_stops_visibility(store):
    store.add_group("user@example.com", "team-a")
    store.remove_group("user@example.com", "team-a")
    assert not store.is_visible("user@example.com", "skill", "alpha", group="team-a")


def test_add_groups_and_list_groups(store):
    added = store.add_groups("user@example.com", ["team-a", "team-b"])
    assert added == 2
    assert store.subscribed_groups("user@example.com") == {"team-a", "team-b"}
    group = store.list_groups_for_user("user@example.com")[0]
    assert group_subscription_to_dict(group)["group_name"] == "team-a"


def test_record_user_seen(store):
    assert store.record_user_seen("user@example.com") is True
    seen = store.get_seen_user("user@example.com")
    assert seen is not None
    assert seen.user_email == "user@example.com"
    assert store.record_user_seen("user@example.com") is False


def test_onboard_user_if_new_subscribes_all_groups(store):
    from dropmcp.subscriptions import onboard_user_if_new

    assert onboard_user_if_new(store, "user@example.com", ["team-a", "team-b"]) is True
    assert store.subscribed_groups("user@example.com") == {"team-a", "team-b"}
    assert onboard_user_if_new(store, "user@example.com", ["team-c"]) is False
    assert store.subscribed_groups("user@example.com") == {"team-a", "team-b"}


def test_subscription_to_dict(store):
    store.add_item("user@example.com", "skill", "x")
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
    store.add_item("user@example.com", "skill", "mine")
    assert (
        item_visible_over_mcp(settings, store, "user@example.com", "skill", "mine")
        is True
    )


def test_item_visible_via_group(store):
    from dropmcp.config import Settings

    settings = Settings.resolve(
        skills="skills",
        prompts="prompts",
        user_subscriptions_enabled=True,
    )
    store.add_group("user@example.com", "team-a")
    assert item_visible_over_mcp(
        settings,
        store,
        "user@example.com",
        "skill",
        "alpha",
        group="team-a",
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
        assert body["available_groups"] == ["team-a"]
        assert body["subscribed_groups"] == ["team-a"]
        assert all(item["subscribed"] is True for item in body["items"])

        add = client.post(
            "/api/subscriptions",
            headers=headers,
            json={"item_type": "skill", "item_name": "alpha"},
        )
        assert add.status_code == 200

        listed = client.get("/api/subscriptions", headers=headers)
        payload = listed.json()
        assert len(payload["items"]) == 1
        assert len(payload["groups"]) == 1
        assert payload["groups"][0]["group_name"] == "team-a"

        group_add = client.post(
            "/api/subscriptions/group/team-a",
            headers=headers,
        )
        assert group_add.status_code == 200
        assert group_add.json()["count"] == 2
        assert client.get("/catalog", headers=headers).json()["subscribed_groups"] == [
            "team-a"
        ]

        delete = client.delete(
            "/api/subscriptions/skill/alpha",
            headers=headers,
        )
        assert delete.status_code == 200
        catalog_after_opt_out = client.get("/catalog", headers=headers).json()
        alpha = next(i for i in catalog_after_opt_out["items"] if i["name"] == "alpha")
        beta = next(i for i in catalog_after_opt_out["items"] if i["name"] == "beta")
        assert alpha["subscribed"] is False
        assert beta["subscribed"] is True

        group_remove = client.delete(
            "/api/subscriptions/group/team-a",
            headers=headers,
        )
        assert group_remove.status_code == 200


@pytest.mark.asyncio
async def test_subscribe_all_groups_route(tmp_path):
    from starlette.testclient import TestClient

    from dropmcp.config import Settings
    from dropmcp.server import build_server

    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()
    for name, group in (("alpha", "team-a"), ("beta", "team-b")):
        (skills / name).mkdir()
        (skills / name / "SKILL.md").write_text(
            f"---\nname: {name}\ncategory: c\ngroup: {group}\ndescription: X\n---\n",
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
        body = client.get("/catalog", headers=headers).json()
        assert set(body["subscribed_groups"]) == {"team-a", "team-b"}
        assert all(item["subscribed"] for item in body["items"])

        resp = client.post("/api/subscriptions/groups", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_mcp_first_sight_subscribes_all_groups(tmp_path, monkeypatch):
    from dropmcp.config import Settings
    from dropmcp.skills import FilteredSkillsProvider
    from dropmcp.subscriptions import SubscriptionCoordinator

    skills = tmp_path / "skills"
    skills.mkdir()
    for name in ("alpha", "beta"):
        (skills / name).mkdir()
        (skills / name / "SKILL.md").write_text(
            f"---\nname: {name}\ncategory: c\ngroup: team-a\ndescription: {name}\n---\n",
            encoding="utf-8",
        )

    settings = Settings.resolve(
        skills=skills,
        prompts=tmp_path / "prompts",
        user_subscriptions_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'db'}",
    )
    store = UserSubscriptionStore(settings.database_url)
    coordinator = SubscriptionCoordinator(
        store,
        settings,
        lambda: ["team-a"],
    )
    provider = FilteredSkillsProvider(
        roots=skills,
        subscription_store=store,
        subscription_settings=settings,
        subscription_coordinator=coordinator,
    )

    monkeypatch.setattr(
        "dropmcp.subscriptions.resolve_user_email",
        lambda _header: "dev@example.com",
    )
    tools = await provider._list_tools()
    assert {t.name for t in tools} == {"alpha", "beta"}
    assert store.subscribed_groups("dev@example.com") == {"team-a"}


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

    store.add_item("dev@example.com", "skill", "visible")
    tools = await provider._list_tools()
    assert [t.name for t in tools] == ["visible"]

    monkeypatch.setattr("dropmcp.skills.resolve_mcp_user", lambda _settings: None)
    tools = await provider._list_tools()
    assert {t.name for t in tools} == {"visible", "hidden"}


@pytest.mark.asyncio
async def test_skills_provider_group_subscription_includes_new_skill(
    tmp_path, monkeypatch
):
    from dropmcp.config import Settings
    from dropmcp.skills import FilteredSkillsProvider

    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "alpha").mkdir()
    (skills / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ncategory: c\ngroup: team-a\ndescription: A\n---\n",
        encoding="utf-8",
    )

    settings = Settings.resolve(
        skills=skills,
        prompts=tmp_path / "prompts",
        user_subscriptions_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'db'}",
    )
    store = UserSubscriptionStore(settings.database_url)
    store.add_group("dev@example.com", "team-a")

    provider = FilteredSkillsProvider(
        roots=skills,
        subscription_store=store,
        subscription_settings=settings,
    )
    monkeypatch.setattr(
        "dropmcp.skills.resolve_mcp_user", lambda _settings: "dev@example.com"
    )

    tools = await provider._list_tools()
    assert [t.name for t in tools] == ["alpha"]

    (skills / "beta").mkdir()
    (skills / "beta" / "SKILL.md").write_text(
        "---\nname: beta\ncategory: c\ngroup: team-a\ndescription: B\n---\n",
        encoding="utf-8",
    )
    provider = FilteredSkillsProvider(
        roots=skills,
        subscription_store=store,
        subscription_settings=settings,
        reload=True,
    )
    tools = await provider._list_tools()
    assert {t.name for t in tools} == {"alpha", "beta"}
