"""Postgres from the shipped reference SQL, the startup check and ``memory-sql``."""

from __future__ import annotations

import subprocess
import sys
from importlib import resources

import pytest
from sqlalchemy import create_engine

from dropmcp.memory.schema_check import check_memory_schema, memory_sql
from dropmcp.memory.store import MemoryStore

postgres_only = pytest.mark.parametrize("backend", ["postgres"], indirect=True)


def test_memory_sql_command_prints_the_packaged_file():
    packaged = (
        resources.files("dropmcp.memory") / "sql" / "memory.sql"
    ).read_text(encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "dropmcp", "memory-sql"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )

    assert result.stdout == packaged
    assert "CREATE TABLE IF NOT EXISTS memory (" in packaged


@postgres_only
def test_postgres_reference_sql_applies_twice(database_url):
    engine = create_engine(database_url, future=True)
    try:
        for _ in range(2):
            with engine.begin() as conn:
                conn.exec_driver_sql(memory_sql())
        check_memory_schema(engine)
    finally:
        engine.dispose()


@postgres_only
async def test_postgres_startup_check_names_missing_table_and_columns(
    memory_server, database_url
):
    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE memory_near_duplicate_log")
            conn.exec_driver_sql("ALTER TABLE memory DROP COLUMN search_text")
            conn.exec_driver_sql("ALTER TABLE memory_report DROP COLUMN correction")
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError) as raised:
        async with memory_server():
            pass

    message = str(raised.value)
    assert "missing tables: memory_near_duplicate_log;" in message
    assert "missing columns: memory.search_text, memory_report.correction" in message
    assert "python -m dropmcp memory-sql" in message


@postgres_only
async def test_postgres_startup_check_skipped_for_injected_store(
    memory_server, database_url
):
    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE memory_near_duplicate_log")
    finally:
        engine.dispose()

    async with memory_server(memory_store=MemoryStore(database_url)) as mem:
        assert "memory_recall" in await mem.list_tools()
