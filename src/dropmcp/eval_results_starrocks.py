"""StarRocks-backed eval results store (optional ``dropmcp[starrocks]`` extra).

The library does not ship a deployment's SQL or connection defaults. Pass the
queries in, or set ``DROPMCP_EVAL_RESULTS_SKILL_QUERY`` and
``DROPMCP_EVAL_RESULTS_ALL_QUERY``. Connection settings come from the
constructor or ``STARROCKS_HOST``, ``STARROCKS_PORT``, ``STARROCKS_SCHEMA``,
``STARROCKS_USER``, and ``STARROCKS_PASSWORD``.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from dropmcp.eval_results import EvalResult

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 30

# Skill query bind order: project, skill_name, commit_sha, datadate.
# All-results query bind order: project, commit_sha, datadate.
Credentials = Callable[[], tuple[str, str]]
Connect = Callable[..., object]


def _env_credentials() -> tuple[str, str]:
    return os.environ.get("STARROCKS_USER", ""), os.environ.get("STARROCKS_PASSWORD", "")


def _datadate_cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


def _row_to_result(row) -> EvalResult:
    return EvalResult(
        test_name=row[0] or "",
        passed=bool(row[1]),
        score=float(row[2] or 0),
        threshold=float(row[3] or 0),
        duration_ms=int(row[4] or 0),
        reasoning=row[5] or "",
        error=row[6],
        worker_model=row[7] or "",
        triggered_at=int(row[8] or 0),
        pipeline_id=str(row[9] or ""),
        commit_sha=row[10] or "",
    )


def _default_connect(**kwargs):
    import mysql.connector

    return mysql.connector.connect(**kwargs)


class StarRocksEvalResultsStore:
    """Run caller-supplied SQL against a MySQL-compatible StarRocks endpoint.

    ``skill_query`` is executed as
    ``(project, skill_name, commit_sha, datadate)``. ``all_query`` is executed
    as ``(project, commit_sha, datadate)``. Both must return rows in
    ``EvalResult`` column order.
    """

    def __init__(
        self,
        *,
        skill_query: str,
        all_query: str,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        credentials: Credentials | None = None,
        connect: Connect | None = None,
        lookback_days: int = _LOOKBACK_DAYS,
    ) -> None:
        skill_query = skill_query.strip()
        all_query = all_query.strip()
        if not skill_query or not all_query:
            raise ValueError("StarRocks eval queries must be provided by the caller")

        self._skill_query = skill_query
        self._all_query = all_query
        self._host = host if host is not None else os.environ.get("STARROCKS_HOST", "")
        port_raw = port if port is not None else os.environ.get("STARROCKS_PORT")
        self._port = int(port_raw) if port_raw else None
        self._database = (
            database if database is not None else os.environ.get("STARROCKS_SCHEMA", "")
        )
        self._credentials = credentials or _env_credentials
        self._connect = connect or _default_connect
        self._lookback_days = lookback_days

    def get_results_for_skill(
        self, project: str, skill_name: str, commit_sha: str
    ) -> list[EvalResult]:
        params = (project, skill_name, commit_sha, _datadate_cutoff(self._lookback_days))
        return list(self._fetch(self._skill_query, params))

    def get_all_latest_results(
        self, project: str, commit_sha: str
    ) -> dict[str, list[EvalResult]]:
        params = (project, commit_sha, _datadate_cutoff(self._lookback_days))
        results: dict[str, list[EvalResult]] = {}
        for result in self._fetch(self._all_query, params):
            results.setdefault(result.test_name, []).append(result)
        return results

    def _fetch(self, sql: str, params: tuple) -> list[EvalResult]:
        if not self._host or self._port is None:
            logger.warning("StarRocks eval store is missing STARROCKS_HOST or STARROCKS_PORT")
            return []

        username, password = self._credentials()
        results: list[EvalResult] = []
        try:
            conn = self._connect(
                host=self._host,
                port=self._port,
                database=self._database,
                user=username,
                password=password,
                ssl_disabled=False,
                connection_timeout=30,
            )
            cursor = conn.cursor()
            cursor.execute(sql, params)
            for row in cursor.fetchall():
                results.append(_row_to_result(row))
            cursor.close()
            conn.close()
        except Exception as exc:
            logger.warning("Failed to query StarRocks for eval results: %s", exc)
        return results
