"""Per-user skill and prompt subscription storage and MCP filtering helpers."""

from __future__ import annotations

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
)
from sqlalchemy.engine import Engine

from dropmcp.identity import resolve_user_email

if TYPE_CHECKING:
    from dropmcp.config import Settings

ITEM_TYPES = frozenset({"skill", "prompt"})


@dataclass(frozen=True)
class Subscription:
    item_type: str
    item_name: str
    created_at: str


def subscription_to_dict(sub: Subscription) -> dict[str, str]:
    return {
        "item_type": sub.item_type,
        "item_name": sub.item_name,
        "created_at": sub.created_at,
    }


class UserSubscriptionStore:
    """Thin SQLAlchemy Core store for per-user skill/prompt opt-ins."""

    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url, future=True)
        self._metadata = MetaData()
        self._table = Table(
            "user_subscription",
            self._metadata,
            Column("user_email", String(320), primary_key=True),
            Column("item_type", String(16), primary_key=True),
            Column("item_name", String(256), primary_key=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        if database_url.startswith("sqlite"):
            self._metadata.create_all(self._engine)

    def list_for_user(self, user_email: str) -> list[Subscription]:
        stmt = (
            select(self._table)
            .where(self._table.c.user_email == user_email)
            .order_by(self._table.c.item_type, self._table.c.item_name)
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        return [_row_to_subscription(row) for row in rows]

    def subscribed_keys(self, user_email: str) -> set[tuple[str, str]]:
        return {(s.item_type, s.item_name) for s in self.list_for_user(user_email)}

    def is_subscribed(self, user_email: str, item_type: str, item_name: str) -> bool:
        stmt = select(self._table.c.user_email).where(
            self._table.c.user_email == user_email,
            self._table.c.item_type == item_type,
            self._table.c.item_name == item_name,
        )
        with self._engine.connect() as conn:
            return conn.execute(stmt).first() is not None

    def add(self, user_email: str, item_type: str, item_name: str) -> None:
        if self.is_subscribed(user_email, item_type, item_name):
            return
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                insert(self._table).values(
                    user_email=user_email,
                    item_type=item_type,
                    item_name=item_name,
                    created_at=now,
                )
            )

    def remove(self, user_email: str, item_type: str, item_name: str) -> None:
        stmt = delete(self._table).where(
            self._table.c.user_email == user_email,
            self._table.c.item_type == item_type,
            self._table.c.item_name == item_name,
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def add_many(
        self, user_email: str, members: list[tuple[str, str]]
    ) -> None:
        if not members:
            return
        existing = self.subscribed_keys(user_email)
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            for item_type, item_name in members:
                if (item_type, item_name) in existing:
                    continue
                conn.execute(
                    insert(self._table).values(
                        user_email=user_email,
                        item_type=item_type,
                        item_name=item_name,
                        created_at=now,
                    )
                )

    def remove_many(
        self, user_email: str, members: list[tuple[str, str]]
    ) -> None:
        if not members:
            return
        with self._engine.begin() as conn:
            for item_type, item_name in members:
                conn.execute(
                    delete(self._table).where(
                        self._table.c.user_email == user_email,
                        self._table.c.item_type == item_type,
                        self._table.c.item_name == item_name,
                    )
                )


def _row_to_subscription(row) -> Subscription:
    created = row.created_at
    if isinstance(created, datetime):
        created_at = created.astimezone(timezone.utc).isoformat()
    else:
        created_at = str(created)
    return Subscription(
        item_type=row.item_type,
        item_name=row.item_name,
        created_at=created_at,
    )


def mcp_filtering_active(settings: Settings, user_email: str | None) -> bool:
    return settings.user_subscriptions_enabled and user_email is not None


def item_visible_over_mcp(
    settings: Settings,
    store: UserSubscriptionStore | None,
    user_email: str | None,
    item_type: str,
    item_name: str,
) -> bool:
    """Return whether an item should be exposed over MCP for the current request."""
    if not mcp_filtering_active(settings, user_email):
        return True
    assert store is not None
    return store.is_subscribed(user_email, item_type, item_name)


def resolve_mcp_user(settings: Settings) -> str | None:
    if not settings.user_subscriptions_enabled:
        return None
    return resolve_user_email(settings.user_header)
