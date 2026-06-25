"""Per-user skill and prompt subscription storage and MCP filtering helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from dropmcp.identity import resolve_user_email, user_from_request

if TYPE_CHECKING:
    from dropmcp.config import Settings
    from starlette.requests import Request

ITEM_TYPES = frozenset({"skill", "prompt"})


@dataclass(frozen=True)
class Subscription:
    item_type: str
    item_name: str
    created_at: str


@dataclass(frozen=True)
class GroupSubscription:
    group_name: str
    created_at: str


@dataclass(frozen=True)
class SeenUser:
    user_email: str
    first_seen_at: str
    last_seen_at: str


def subscription_to_dict(sub: Subscription) -> dict[str, str]:
    return {
        "item_type": sub.item_type,
        "item_name": sub.item_name,
        "created_at": sub.created_at,
    }


def group_subscription_to_dict(sub: GroupSubscription) -> dict[str, str]:
    return {
        "group_name": sub.group_name,
        "created_at": sub.created_at,
    }


def _format_timestamp(value) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _row_to_subscription(row) -> Subscription:
    return Subscription(
        item_type=row.item_type,
        item_name=row.item_name,
        created_at=_format_timestamp(row.created_at),
    )


def _row_to_group_subscription(row) -> GroupSubscription:
    return GroupSubscription(
        group_name=row.group_name,
        created_at=_format_timestamp(row.created_at),
    )


class UserSubscriptionStore:
    """Per-user subscriptions: direct opt-ins, group opt-ins, and per-item opt-outs."""

    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url, future=True)
        self._metadata = MetaData()
        self._subscriptions = Table(
            "user_subscription",
            self._metadata,
            Column("user_email", String(320), primary_key=True),
            Column("item_type", String(16), primary_key=True),
            Column("item_name", String(256), primary_key=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self._group_subscriptions = Table(
            "user_group_subscription",
            self._metadata,
            Column("user_email", String(320), primary_key=True),
            Column("group_name", String(256), primary_key=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self._exclusions = Table(
            "user_subscription_exclusion",
            self._metadata,
            Column("user_email", String(320), primary_key=True),
            Column("item_type", String(16), primary_key=True),
            Column("item_name", String(256), primary_key=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self._seen_users = Table(
            "user_seen",
            self._metadata,
            Column("user_email", String(320), primary_key=True),
            Column("first_seen_at", DateTime(timezone=True), nullable=False),
            Column("last_seen_at", DateTime(timezone=True), nullable=False),
        )
        if database_url.startswith("sqlite"):
            self._metadata.create_all(self._engine)

    def record_user_seen(self, user_email: str) -> bool:
        """Log the user visit. Returns True when this is the first sighting."""
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(self._seen_users.c.user_email).where(
                    self._seen_users.c.user_email == user_email
                )
            ).first()
            if existing is not None:
                conn.execute(
                    update(self._seen_users)
                    .where(self._seen_users.c.user_email == user_email)
                    .values(last_seen_at=now)
                )
                return False
            conn.execute(
                insert(self._seen_users).values(
                    user_email=user_email,
                    first_seen_at=now,
                    last_seen_at=now,
                )
            )
            return True

    def get_seen_user(self, user_email: str) -> SeenUser | None:
        stmt = select(self._seen_users).where(
            self._seen_users.c.user_email == user_email
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).first()
        if row is None:
            return None
        return SeenUser(
            user_email=row.user_email,
            first_seen_at=_format_timestamp(row.first_seen_at),
            last_seen_at=_format_timestamp(row.last_seen_at),
        )

    def list_for_user(self, user_email: str) -> list[Subscription]:
        stmt = (
            select(self._subscriptions)
            .where(self._subscriptions.c.user_email == user_email)
            .order_by(self._subscriptions.c.item_type, self._subscriptions.c.item_name)
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        return [_row_to_subscription(row) for row in rows]

    def list_groups_for_user(self, user_email: str) -> list[GroupSubscription]:
        stmt = (
            select(self._group_subscriptions)
            .where(self._group_subscriptions.c.user_email == user_email)
            .order_by(self._group_subscriptions.c.group_name)
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        return [_row_to_group_subscription(row) for row in rows]

    def subscribed_groups(self, user_email: str) -> set[str]:
        return {g.group_name for g in self.list_groups_for_user(user_email)}

    def is_group_subscribed(self, user_email: str, group_name: str) -> bool:
        stmt = select(self._group_subscriptions.c.user_email).where(
            self._group_subscriptions.c.user_email == user_email,
            self._group_subscriptions.c.group_name == group_name,
        )
        with self._engine.connect() as conn:
            return conn.execute(stmt).first() is not None

    def is_directly_subscribed(
        self, user_email: str, item_type: str, item_name: str
    ) -> bool:
        stmt = select(self._subscriptions.c.user_email).where(
            self._subscriptions.c.user_email == user_email,
            self._subscriptions.c.item_type == item_type,
            self._subscriptions.c.item_name == item_name,
        )
        with self._engine.connect() as conn:
            return conn.execute(stmt).first() is not None

    def is_excluded(self, user_email: str, item_type: str, item_name: str) -> bool:
        stmt = select(self._exclusions.c.user_email).where(
            self._exclusions.c.user_email == user_email,
            self._exclusions.c.item_type == item_type,
            self._exclusions.c.item_name == item_name,
        )
        with self._engine.connect() as conn:
            return conn.execute(stmt).first() is not None

    def is_visible(
        self,
        user_email: str,
        item_type: str,
        item_name: str,
        *,
        group: str | None = None,
    ) -> bool:
        if self.is_excluded(user_email, item_type, item_name):
            return False
        if self.is_directly_subscribed(user_email, item_type, item_name):
            return True
        if group and self.is_group_subscribed(user_email, group):
            return True
        return False

    def add_item(self, user_email: str, item_type: str, item_name: str) -> None:
        self._remove_exclusion(user_email, item_type, item_name)
        if self.is_directly_subscribed(user_email, item_type, item_name):
            return
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                insert(self._subscriptions).values(
                    user_email=user_email,
                    item_type=item_type,
                    item_name=item_name,
                    created_at=now,
                )
            )

    def remove_item(
        self,
        user_email: str,
        item_type: str,
        item_name: str,
        *,
        group: str | None = None,
    ) -> None:
        if group and self.is_group_subscribed(user_email, group):
            self._add_exclusion(user_email, item_type, item_name)
            self._remove_subscription(user_email, item_type, item_name)
            return
        self._remove_subscription(user_email, item_type, item_name)

    def add_group(self, user_email: str, group_name: str) -> None:
        if self.is_group_subscribed(user_email, group_name):
            return
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                insert(self._group_subscriptions).values(
                    user_email=user_email,
                    group_name=group_name,
                    created_at=now,
                )
            )

    def remove_group(self, user_email: str, group_name: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                delete(self._group_subscriptions).where(
                    self._group_subscriptions.c.user_email == user_email,
                    self._group_subscriptions.c.group_name == group_name,
                )
            )

    def add_groups(self, user_email: str, group_names: list[str]) -> int:
        added = 0
        for group_name in group_names:
            if not self.is_group_subscribed(user_email, group_name):
                self.add_group(user_email, group_name)
                added += 1
        return added

    def clear_group_exclusions(
        self,
        user_email: str,
        members: list[tuple[str, str]],
    ) -> None:
        if not members:
            return
        with self._engine.begin() as conn:
            for item_type, item_name in members:
                conn.execute(
                    delete(self._exclusions).where(
                        self._exclusions.c.user_email == user_email,
                        self._exclusions.c.item_type == item_type,
                        self._exclusions.c.item_name == item_name,
                    )
                )

    def _add_exclusion(
        self, user_email: str, item_type: str, item_name: str
    ) -> None:
        if self.is_excluded(user_email, item_type, item_name):
            return
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                insert(self._exclusions).values(
                    user_email=user_email,
                    item_type=item_type,
                    item_name=item_name,
                    created_at=now,
                )
            )

    def _remove_exclusion(
        self, user_email: str, item_type: str, item_name: str
    ) -> None:
        stmt = delete(self._exclusions).where(
            self._exclusions.c.user_email == user_email,
            self._exclusions.c.item_type == item_type,
            self._exclusions.c.item_name == item_name,
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def _remove_subscription(
        self, user_email: str, item_type: str, item_name: str
    ) -> None:
        stmt = delete(self._subscriptions).where(
            self._subscriptions.c.user_email == user_email,
            self._subscriptions.c.item_type == item_type,
            self._subscriptions.c.item_name == item_name,
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)


def onboard_user_if_new(
    store: UserSubscriptionStore,
    user_email: str,
    available_groups: list[str],
) -> bool:
    """Log first sighting and subscribe the user to every catalog group."""
    is_new = store.record_user_seen(user_email)
    if is_new and available_groups:
        store.add_groups(user_email, available_groups)
    return is_new


class SubscriptionCoordinator:
    """Server-side user sighting and first-visit group onboarding."""

    def __init__(
        self,
        store: UserSubscriptionStore,
        settings: Settings,
        available_groups: Callable[[], list[str]],
    ) -> None:
        self._store = store
        self._settings = settings
        self._available_groups = available_groups

    def ensure_initialized(self, user_email: str) -> bool:
        return onboard_user_if_new(
            self._store, user_email, self._available_groups()
        )

    def mcp_user(self) -> str | None:
        user = resolve_mcp_user(self._settings)
        if user is not None:
            self.ensure_initialized(user)
        return user

    def http_user(self, request: Request) -> str | None:
        user = user_from_request(request, self._settings.user_header)
        if user is not None:
            self.ensure_initialized(user)
        return user


def mcp_filtering_active(settings: Settings, user_email: str | None) -> bool:
    return settings.user_subscriptions_enabled and user_email is not None


def item_visible_over_mcp(
    settings: Settings,
    store: UserSubscriptionStore | None,
    user_email: str | None,
    item_type: str,
    item_name: str,
    *,
    group: str | None = None,
) -> bool:
    """Return whether an item should be exposed over MCP for the current request."""
    if not mcp_filtering_active(settings, user_email):
        return True
    assert store is not None
    return store.is_visible(user_email, item_type, item_name, group=group)


def resolve_mcp_user(settings: Settings) -> str | None:
    if not settings.user_subscriptions_enabled:
        return None
    return resolve_user_email(settings.user_header)
