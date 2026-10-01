from __future__ import annotations

from datetime import datetime

import pytest

from dropmcp import eval_results_mysql
from dropmcp.benchmarks import BenchmarkResult, BenchmarkResultsStore
from dropmcp.eval_results_mysql import MySQLBenchmarkResultsStore

_QUERY = "SELECT results WHERE project = %s AND day >= %s"
_ROW = ("alpha/basic", "model-a", 1, 88.5, 80, 1714200000000, 12345, "abc123")


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 9, 30, 12, 0, tzinfo=tz)


class _FakeCursor:
    def __init__(self, rows=None, error: Exception | None = None) -> None:
        self.rows = rows or []
        self.error = error
        self.executed: tuple[str, tuple] | None = None
        self.closed = False

    def execute(self, sql, params):
        self.executed = (sql, params)
        if self.error is not None:
            raise self.error

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


class _Connector:
    def __init__(self, cursor: _FakeCursor) -> None:
        self.connection = _FakeConnection(cursor)
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.connection


def _store(connector, **overrides) -> MySQLBenchmarkResultsStore:
    options = {
        "query": _QUERY,
        "host": "db.example.com",
        "port": 3306,
        "database": "results",
        "credentials": lambda: ("reader", "secret"),
        "connect": connector,
    }
    options.update(overrides)
    return MySQLBenchmarkResultsStore(**options)


@pytest.fixture(autouse=True)
def _frozen_clock(monkeypatch):
    monkeypatch.setattr(eval_results_mysql, "datetime", _FrozenDatetime)


def test_store_requires_a_query():
    with pytest.raises(ValueError):
        MySQLBenchmarkResultsStore(query="  ")


def test_store_satisfies_benchmark_protocol():
    assert isinstance(_store(_Connector(_FakeCursor())), BenchmarkResultsStore)


def test_store_runs_injected_query_and_maps_rows():
    cursor = _FakeCursor([_ROW])
    connector = _Connector(cursor)

    results = _store(connector).get_latest_benchmark_results("org/repo", 60)

    assert cursor.executed == (_QUERY, ("org/repo", "2026-08-01"))
    assert results == [
        BenchmarkResult(
            test_name="alpha/basic",
            worker_model="model-a",
            passed=True,
            score=88.5,
            threshold=80.0,
            triggered_at=1714200000000,
            pipeline_id="12345",
            commit_sha="abc123",
        )
    ]
    assert cursor.closed
    assert connector.connection.closed


def test_store_formats_the_partition_cutoff_as_the_caller_asks():
    cursor = _FakeCursor()

    _store(_Connector(cursor), datadate_format="%Y%m%d").get_latest_benchmark_results(
        "org/repo", 60
    )

    assert cursor.executed[1] == ("org/repo", "20260801")


def test_store_connects_with_injected_settings_and_credentials():
    connector = _Connector(_FakeCursor())

    _store(connector).get_latest_benchmark_results("org/repo", 60)

    assert connector.calls == [
        {
            "host": "db.example.com",
            "port": 3306,
            "database": "results",
            "user": "reader",
            "password": "secret",
            "ssl_disabled": False,
            "connection_timeout": 30,
        }
    ]


def test_store_reads_connection_settings_from_the_environment(monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "env.example.com")
    monkeypatch.setenv("MYSQL_PORT", "3307")
    monkeypatch.setenv("MYSQL_DATABASE", "env_db")
    monkeypatch.setenv("MYSQL_USER", "env_user")
    monkeypatch.setenv("MYSQL_PASSWORD", "env_pass")
    connector = _Connector(_FakeCursor())
    store = MySQLBenchmarkResultsStore(query=_QUERY, connect=connector)

    store.get_latest_benchmark_results("org/repo", 60)

    [call] = connector.calls
    assert (call["host"], call["port"], call["database"]) == (
        "env.example.com",
        3307,
        "env_db",
    )
    assert (call["user"], call["password"]) == ("env_user", "env_pass")


def test_store_tolerates_null_columns():
    connector = _Connector(_FakeCursor([(None, None, 0, None, None, None, None, None)]))

    [result] = _store(connector).get_latest_benchmark_results("org/repo", 60)

    assert result == BenchmarkResult(
        test_name="",
        worker_model="",
        passed=False,
        score=0.0,
        threshold=0.0,
        triggered_at=0,
        pipeline_id="",
        commit_sha="",
    )


def test_store_propagates_query_failure_and_closes_resources():
    cursor = _FakeCursor(error=RuntimeError("query failed"))
    connector = _Connector(cursor)

    with pytest.raises(RuntimeError, match="query failed"):
        _store(connector).get_latest_benchmark_results("org/repo", 60)

    assert cursor.closed
    assert connector.connection.closed


def test_store_propagates_connection_failure():
    def connect(**kwargs):
        raise ConnectionError("unreachable")

    with pytest.raises(ConnectionError):
        _store(connect).get_latest_benchmark_results("org/repo", 60)


def test_store_without_host_or_port_raises_instead_of_connecting(monkeypatch):
    for name in ("MYSQL_HOST", "MYSQL_PORT"):
        monkeypatch.delenv(name, raising=False)
    connector = _Connector(_FakeCursor())
    store = MySQLBenchmarkResultsStore(query=_QUERY, connect=connector)

    with pytest.raises(RuntimeError, match="host or port"):
        store.get_latest_benchmark_results("org/repo", 60)

    assert connector.calls == []
