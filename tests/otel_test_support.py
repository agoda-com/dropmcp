"""Helpers for isolating OpenTelemetry from the pytest process."""

from __future__ import annotations

import logging
from contextlib import contextmanager


def reset_otel_globals() -> None:
    try:
        from opentelemetry._logs import NoOpLoggerProvider, set_logger_provider
        from opentelemetry.metrics import NoOpMeterProvider, set_meter_provider

        set_meter_provider(NoOpMeterProvider())
        set_logger_provider(NoOpLoggerProvider())
    except Exception:
        pass


def shutdown_otel_providers() -> None:
    try:
        from opentelemetry import _logs, metrics
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk.metrics import MeterProvider

        import dropmcp.telemetry as telemetry

        mp = metrics.get_meter_provider()
        if isinstance(mp, MeterProvider):
            mp.shutdown(timeout_millis=100)

        lp = _logs.get_logger_provider()
        if isinstance(lp, LoggerProvider):
            root = logging.getLogger()
            for h in list(root.handlers):
                if "LoggingHandler" in type(h).__name__:
                    root.removeHandler(h)
            lp.shutdown()
    except Exception:
        pass
    finally:
        try:
            import dropmcp.telemetry as telemetry

            telemetry._clear_exit_hooks()
        except Exception:
            pass
        reset_otel_globals()


def patch_otel_for_tests(monkeypatch) -> None:
    """Prevent OTLP exporters and atexit flush hooks in unit tests."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    monkeypatch.delenv(
        "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", raising=False
    )

    import dropmcp.telemetry as telemetry

    monkeypatch.setattr(telemetry, "_flush_on_exit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(telemetry, "_setup_logging", lambda _resource: None)
    monkeypatch.setattr(telemetry, "_setup_metrics", lambda _resource, _metrics: None)


def reset_telemetry_module_state() -> None:
    import dropmcp.telemetry as telemetry

    telemetry._clear_exit_hooks()
    telemetry._state["configured"] = False
    telemetry._state["active"] = False
    telemetry._state["instruments"] = None
    telemetry._event_logging_configured = False
    telemetry._event_logger.handlers.clear()


@contextmanager
def fresh_telemetry(monkeypatch):
    """Reload telemetry with a clean module state."""
    import dropmcp.telemetry as telemetry

    patch_otel_for_tests(monkeypatch)
    reset_otel_globals()
    reset_telemetry_module_state()
    yield telemetry
    reset_telemetry_module_state()
    shutdown_otel_providers()
