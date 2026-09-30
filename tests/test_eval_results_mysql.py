"""Caller-supplied MySQL queries. No deployment SQL or hosts ship in-tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from dropmcp.eval_results import resolve_mysql_store
from dropmcp.eval_results_mysql import MySQLEvalResultsStore

_MODULE = Path(__file__).resolve().parents[1] / "src" / "dropmcp" / "eval_results_mysql.py"

_SKILL_SQL = "SELECT skill WHERE project = %s AND name = %s AND sha = %s AND day >= %s"
_ALL_SQL = "SELECT all WHERE project = %s AND sha = %s AND day >= %s"


def test_module_has_no_deployment_defaults():
    source = _MODULE.read_text().lower()
    for marker in ("agodata", "agoda", "skillevaluation", "/var/agoda", "fleet", "starrocks"):
        assert marker not in source


def test_store_requires_queries():
    with pytest.raises(ValueError):
        MySQLEvalResultsStore(skill_query="  ", all_query=_ALL_SQL)


def test_store_executes_injected_queries():
    calls: list[tuple[str, tuple]] = []

    class FakeCursor:
        def execute(self, sql, params):
            calls.append((sql, params))

        def fetchall(self):
            return [
                (
                    "demo/basic",
                    1,
                    90,
                    80,
                    10,
                    "ok",
                    None,
                    "model",
                    1,
                    "pipe",
                    "abc",
                )
            ]

        def close(self):
            return None

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    store = MySQLEvalResultsStore(
        skill_query=_SKILL_SQL,
        all_query=_ALL_SQL,
        host="mysql.example.com",
        port=3306,
        database="evals",
        credentials=lambda: ("user", "secret"),
        connect=lambda **kwargs: FakeConn(),
        lookback_days=1,
    )

    skill_rows = store.get_results_for_skill("group/project", "demo", "abc")
    all_rows = store.get_all_latest_results("group/project", "abc")

    assert calls[0][0] == _SKILL_SQL
    assert calls[0][1][:3] == ("group/project", "demo", "abc")
    assert calls[1][0] == _ALL_SQL
    assert calls[1][1][:2] == ("group/project", "abc")
    assert skill_rows[0].test_name == "demo/basic"
    assert all_rows["demo/basic"][0].score == 90


def test_missing_host_does_not_connect():
    def connect(**kwargs):
        raise AssertionError("should not connect")

    store = MySQLEvalResultsStore(
        skill_query=_SKILL_SQL,
        all_query=_ALL_SQL,
        host="",
        port=3306,
        connect=connect,
    )
    assert store.get_results_for_skill("p", "s", "sha") == []


def test_resolve_mysql_store_without_queries(monkeypatch):
    monkeypatch.delenv("DROPMCP_EVAL_RESULTS_SKILL_QUERY", raising=False)
    monkeypatch.delenv("DROPMCP_EVAL_RESULTS_ALL_QUERY", raising=False)
    assert resolve_mysql_store() is None


def test_resolve_mysql_store_uses_env_queries(monkeypatch):
    import sys
    import types

    mysql = types.ModuleType("mysql")
    connector = types.ModuleType("mysql.connector")
    mysql.connector = connector
    monkeypatch.setitem(sys.modules, "mysql", mysql)
    monkeypatch.setitem(sys.modules, "mysql.connector", connector)
    monkeypatch.setenv("DROPMCP_EVAL_RESULTS_SKILL_QUERY", _SKILL_SQL)
    monkeypatch.setenv("DROPMCP_EVAL_RESULTS_ALL_QUERY", _ALL_SQL)

    store = resolve_mysql_store()

    assert isinstance(store, MySQLEvalResultsStore)
    assert store._skill_query == _SKILL_SQL
    assert store._all_query == _ALL_SQL
