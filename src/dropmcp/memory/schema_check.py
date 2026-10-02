"""The reference Postgres DDL for memory, and the startup check against it."""

from __future__ import annotations

from importlib import resources

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from dropmcp.memory.store import metadata

# Columns the reference SQL adds that the SQLAlchemy tables don't map.
_DDL_ONLY_COLUMNS = {"memory": ("search_text",)}


def memory_sql() -> str:
    path = resources.files("dropmcp.memory") / "sql" / "memory.sql"
    return path.read_text(encoding="utf-8")


def check_memory_schema(engine: Engine) -> None:
    """Raise ``RuntimeError`` naming every missing memory table and column.

    SQLite is skipped because the store creates its own schema there.
    """
    if engine.dialect.name == "sqlite":
        return
    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    missing_tables: list[str] = []
    missing_columns: list[str] = []
    for table in metadata.tables.values():
        if table.name not in present:
            missing_tables.append(table.name)
            continue
        live = {column["name"] for column in inspector.get_columns(table.name)}
        expected = [column.name for column in table.columns]
        expected.extend(_DDL_ONLY_COLUMNS.get(table.name, ()))
        missing_columns.extend(
            f"{table.name}.{name}" for name in expected if name not in live
        )
    if not missing_tables and not missing_columns:
        return
    problems = []
    if missing_tables:
        problems.append("missing tables: " + ", ".join(missing_tables))
    if missing_columns:
        problems.append("missing columns: " + ", ".join(missing_columns))
    raise RuntimeError(
        "Shared memory schema is incomplete ("
        + "; ".join(problems)
        + "). Apply the reference SQL printed by `python -m dropmcp memory-sql`, "
        "then restart."
    )
