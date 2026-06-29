"""Helpers for testing dropmcp's telemetry wiring in isolation."""

from __future__ import annotations

from contextlib import contextmanager


def _reset_telemetry_state() -> None:
    import dropmcp.telemetry as telemetry

    telemetry._state["configured"] = False
    telemetry._state["active"] = False
    telemetry._state["instruments"] = None
    telemetry._session_metadata.clear()
    telemetry._event_logging_configured = False
    telemetry._event_logger.handlers.clear()


@contextmanager
def fresh_telemetry(monkeypatch):
    """Run a telemetry test with clean module state and no real exporters.

    The OTLP exporter setup (``_setup_logging`` / ``_setup_metrics``) is the
    boundary to the OpenTelemetry SDK — another package whose exporter threads
    and atexit flushes we don't own and shouldn't exercise here. Stubbing it
    keeps these tests on dropmcp's own wiring and prevents live exporters from
    leaking into the pytest process.
    """
    import dropmcp.telemetry as telemetry

    monkeypatch.setattr(telemetry, "_setup_logging", lambda _resource: None)
    monkeypatch.setattr(telemetry, "_setup_metrics", lambda _resource, _metrics: None)

    _reset_telemetry_state()
    try:
        yield telemetry
    finally:
        _reset_telemetry_state()
