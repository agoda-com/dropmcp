"""Tests for optional OpenTelemetry telemetry."""

from __future__ import annotations

import importlib
import logging
from contextlib import contextmanager

import pytest


def _shutdown_otel_providers() -> None:
    """Shut down any live OTEL providers to avoid atexit flush timeouts."""
    try:
        from opentelemetry import metrics, _logs
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk._logs import LoggerProvider

        mp = metrics.get_meter_provider()
        if isinstance(mp, MeterProvider):
            mp.shutdown(timeout_millis=100)

        lp = _logs.get_logger_provider()
        if isinstance(lp, LoggerProvider):
            # Remove the OTel logging handler to prevent further side-effects
            root = logging.getLogger()
            for h in list(root.handlers):
                if "LoggingHandler" in type(h).__name__:
                    root.removeHandler(h)
            lp.shutdown()
    except Exception:
        pass


@contextmanager
def _fresh_telemetry(monkeypatch):
    """Reload telemetry with a clean module state."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    import dropmcp.telemetry as telemetry

    telemetry._state["configured"] = False
    telemetry._state["active"] = False
    telemetry._state["instruments"] = None
    yield telemetry
    telemetry._state["configured"] = False
    telemetry._state["active"] = False
    telemetry._state["instruments"] = None


def test_configure_noop_without_endpoint(monkeypatch):
    with _fresh_telemetry(monkeypatch) as telemetry:
        assert telemetry.configure() is False
        assert telemetry.is_active() is False


def test_configure_noop_without_otel_packages(monkeypatch):
    with _fresh_telemetry(monkeypatch) as telemetry:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

        def _raise_import(*_args, **_kwargs):
            raise ImportError("otel not installed")

        monkeypatch.setattr(telemetry, "_setup_otel", _raise_import)
        assert telemetry.configure() is False
        assert telemetry.is_active() is False


def test_track_is_noop_when_inactive(monkeypatch):
    with _fresh_telemetry(monkeypatch) as telemetry:
        with telemetry.track("skill", "example"):
            pass


@pytest.mark.skipif(
    importlib.util.find_spec("opentelemetry") is None,
    reason="dropmcp[otel] not installed",
)
def test_configure_active_with_otel(monkeypatch):
    with _fresh_telemetry(monkeypatch) as telemetry:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        assert telemetry.configure(service_name="test-server") is True
        assert telemetry.is_active() is True
        assert telemetry.configure() is True

        with telemetry.track("skill", "demo"):
            pass

        with telemetry.track("resource", "skill://demo/file", resource_kind="skill"):
            pass

        # Shut down OTEL providers immediately so their atexit handlers don't
        # block pytest teardown trying to flush to a nonexistent collector.
        _shutdown_otel_providers()
