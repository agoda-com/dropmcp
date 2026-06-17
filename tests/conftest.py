"""Shared pytest configuration."""

from __future__ import annotations

import pytest

_OTEL_ENV_VARS = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_SERVICE_NAME",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE",
)


@pytest.fixture(autouse=True)
def _clean_otel_env(monkeypatch):
    """Keep an ambient OTLP endpoint from starting real exporters in tests.

    ``build_server()`` calls ``telemetry.configure()``, so without this a
    developer's (or CI's) shell-level ``OTEL_EXPORTER_OTLP_ENDPOINT`` would spin
    up live OTLP exporters during otherwise-unrelated tests.
    """
    for var in _OTEL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
