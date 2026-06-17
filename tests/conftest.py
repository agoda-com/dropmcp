"""Shared pytest configuration."""

from __future__ import annotations

import pytest

from otel_test_support import (
    patch_otel_for_tests,
    reset_telemetry_module_state,
    shutdown_otel_providers,
)


@pytest.fixture(autouse=True)
def _isolate_otel_exporters(monkeypatch):
    """Keep OTLP exporter threads from blocking pytest exit."""
    patch_otel_for_tests(monkeypatch)
    reset_telemetry_module_state()
    yield
    shutdown_otel_providers()
