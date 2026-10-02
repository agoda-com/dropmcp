"""Harness for shared memory tests: a real server driven over streamable HTTP."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.engine import Engine

from dropmcp.config import Settings
from dropmcp.memory.schema_check import memory_sql
from dropmcp.server import build_server

USER_EMAIL = "agent@example.com"
POSTGRES_URL_ENV = "DROPMCP_TEST_POSTGRES_URL"


@dataclass
class MemoryClient:
    client: Client
    app: Any
    settings: Settings
    engine: Engine
    instructions: str | None

    async def remember(self, **args: Any) -> str:
        return await self._text("memory_remember", args)

    async def recall(self, **args: Any) -> str:
        return await self._text("memory_recall", args)

    async def report(self, **args: Any) -> str:
        return await self._text("memory_report", args)

    async def list_tools(self) -> list[str]:
        return [tool.name for tool in await self.client.list_tools()]

    async def raw_call(self, name: str, args: dict[str, Any]):
        return await self.client.call_tool_mcp(name, args)

    def sql(self, statement: Any, **params: Any) -> list[dict[str, Any]]:
        """Run raw SQL text or a SQLAlchemy statement; return rows as dicts."""
        if isinstance(statement, str):
            statement = text(statement)
        with self.engine.begin() as conn:
            result = conn.execute(statement, params)
            if not result.returns_rows:
                return []
            return [dict(row._mapping) for row in result]

    async def _text(self, name: str, args: dict[str, Any]) -> str:
        args.setdefault("model", "test-model")
        result = await self.raw_call(name, args)
        return result.content[0].text


@pytest.fixture(params=["sqlite", "postgres"])
def backend(request) -> str:
    if request.param == "postgres" and not os.environ.get(POSTGRES_URL_ENV):
        pytest.skip(f"set {POSTGRES_URL_ENV} to run Postgres memory tests")
    return request.param


@pytest.fixture(scope="session")
def postgres_admin() -> Iterator[Engine]:
    engine = create_engine(os.environ[POSTGRES_URL_ENV], future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def database_url(request, backend, tmp_path) -> Iterator[str]:
    """A fresh database per test: a SQLite file, or a Postgres schema built
    from the shipped reference SQL and selected through ``search_path``."""
    if backend == "sqlite":
        yield f"sqlite:///{tmp_path / 'memory.db'}"
        return
    admin: Engine = request.getfixturevalue("postgres_admin")
    schema = f"mem_{uuid.uuid4().hex}"
    with admin.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        conn.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
        conn.exec_driver_sql(memory_sql())
    # application_name tags this test's connections so teardown can close the
    # ones the server's store engine leaves in its pool.
    url = make_url(os.environ[POSTGRES_URL_ENV]).update_query_dict(
        {"options": f"-csearch_path={schema}", "application_name": schema}
    )
    try:
        yield url.render_as_string(hide_password=False)
    finally:
        with admin.begin() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE application_name = :schema"
                ),
                {"schema": schema},
            )
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.fixture
def memory_server(tmp_path, database_url):
    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir(exist_ok=True)
    prompts.mkdir(exist_ok=True)

    @asynccontextmanager
    async def factory(*, user_email: str | None = USER_EMAIL, **overrides: Any):
        """Serve memory over MCP; ``overrides`` go to ``Settings.resolve``.

        ``user_email=None`` calls the tools without the user header.
        """
        kwargs: dict[str, Any] = {
            "skills": skills,
            "prompts": prompts,
            "memory_enabled": True,
            "feedback_enabled": False,
            "ui_enabled": False,
            "database_url": database_url,
            **overrides,
        }
        settings = Settings.resolve(**kwargs)
        app = build_server(settings).http_app(stateless_http=True)

        def client_factory(headers=None, auth=None, follow_redirects=True, timeout=None):
            client_kwargs: dict[str, Any] = {
                "transport": httpx.ASGITransport(app=app),
                "base_url": "http://testserver",
                "headers": headers,
                "follow_redirects": follow_redirects,
            }
            if auth is not None:
                client_kwargs["auth"] = auth
            if timeout is not None:
                client_kwargs["timeout"] = timeout
            return httpx.AsyncClient(**client_kwargs)

        transport = StreamableHttpTransport(
            "http://testserver/mcp",
            headers={settings.user_header: user_email} if user_email else {},
            httpx_client_factory=client_factory,
        )
        engine = create_engine(settings.database_url, future=True)
        try:
            async with app.router.lifespan_context(app):
                async with Client(transport) as client:
                    yield MemoryClient(
                        client=client,
                        app=app,
                        settings=settings,
                        engine=engine,
                        instructions=client.initialize_result.instructions,
                    )
        finally:
            engine.dispose()

    return factory
