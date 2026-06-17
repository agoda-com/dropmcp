"""StarRocks-backed eval results store (optional ``dropmcp[starrocks]`` extra)."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import mysql.connector

from dropmcp.eval_results import EvalResult

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 30
_FLEET_TOKEN_PATH = "/var/agoda/fleet/app.jwt"


def _parse_fleet_token(token_path: str = _FLEET_TOKEN_PATH) -> tuple[str, str]:
    with open(token_path) as f:
        token = f.read().strip()

    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid JWT format (expected 3 parts, got {len(parts)})")

    body_b64 = parts[1]
    padding = 4 - (len(body_b64) % 4)
    if padding != 4:
        body_b64 += "=" * padding

    body = json.loads(base64.urlsafe_b64decode(body_b64))
    sub = body.get("sub", "")
    if not sub:
        raise ValueError("Fleet JWT missing 'sub' claim")

    match = re.search(r"\.([^.]+)\.", sub)
    username = match.group(1) if match else sub
    return username, token


def _resolve_credentials() -> tuple[str, str]:
    user = os.environ.get("STARROCKS_USER", "")
    password = os.environ.get("STARROCKS_PASSWORD", "")
    if user and password:
        return user, password

    if os.path.exists(_FLEET_TOKEN_PATH):
        return _parse_fleet_token()

    return user, password


def _get_connection():
    host = os.environ.get("STARROCKS_HOST", "sr-query.agodata.io")
    port = int(os.environ.get("STARROCKS_PORT", "9030"))
    schema = os.environ.get("STARROCKS_SCHEMA", "messaging")
    username, password = _resolve_credentials()

    logger.info(
        "Connecting to StarRocks at %s:%d db=%s user=%s",
        host,
        port,
        schema,
        username or "(empty)",
    )

    return mysql.connector.connect(
        host=host,
        port=port,
        database=schema,
        user=username,
        password=password,
        ssl_disabled=False,
        connection_timeout=30,
    )


def _datadate_cutoff(days: int = _LOOKBACK_DAYS) -> str:
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


class StarRocksEvalResultsStore:
    """Fetch E2E results from ``messaging.SkillEvaluationResultMessage``."""

    def get_results_for_skill(
        self, project: str, skill_name: str, commit_sha: str
    ) -> list[EvalResult]:
        sql = """
            SELECT
                testname,
                passed,
                score,
                threshold,
                durationms,
                reasoning,
                error,
                workermodel,
                triggeredat,
                pipelineid,
                commitsha
            FROM messaging.SkillEvaluationResultMessage
            WHERE project = %s
              AND testname LIKE CONCAT(%s, '/%%')
              AND commitsha = %s
              AND branch = 'main'
              AND datadate >= %s
            ORDER BY testname, workermodel
        """
        results: list[EvalResult] = []
        try:
            conn = _get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, (project, skill_name, commit_sha, _datadate_cutoff()))
            for row in cursor.fetchall():
                results.append(_row_to_result(row))
            cursor.close()
            conn.close()
        except Exception as exc:
            logger.warning("Failed to query StarRocks for test results: %s", exc)
        return results

    def get_all_latest_results(
        self, project: str, commit_sha: str
    ) -> dict[str, EvalResult]:
        sql = """
            SELECT
                testname,
                passed,
                score,
                threshold,
                durationms,
                reasoning,
                error,
                workermodel,
                triggeredat,
                pipelineid,
                commitsha
            FROM messaging.SkillEvaluationResultMessage
            WHERE project = %s
              AND commitsha = %s
              AND branch = 'main'
              AND datadate >= %s
            ORDER BY testname, workermodel
        """
        results: dict[str, EvalResult] = {}
        try:
            conn = _get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, (project, commit_sha, _datadate_cutoff()))
            for row in cursor.fetchall():
                result = _row_to_result(row)
                results[result.test_name] = result
            cursor.close()
            conn.close()
        except Exception as exc:
            logger.warning("Failed to query StarRocks for all results: %s", exc)
        return results
