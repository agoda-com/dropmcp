"""Tests for optional OpenTelemetry telemetry."""

from __future__ import annotations

import importlib
import logging
import os
from contextlib import contextmanager

import pytest

from dropmcp.middleware import TelemetryMiddleware
from dropmcp.telemetry import METRIC_NAMES


def _reset_otel_globals() -> None:
    """Return OTEL globals to no-op providers between tests."""
    try:
        from opentelemetry._logs import NoOpLoggerProvider, set_logger_provider
        from opentelemetry.metrics import NoOpMeterProvider, set_meter_provider

        set_meter_provider(NoOpMeterProvider())
        set_logger_provider(NoOpLoggerProvider())
    except Exception:
        pass


def _shutdown_otel_providers() -> None:
    """Shut down any live OTEL providers to avoid atexit flush timeouts."""
    try:
        from opentelemetry import _logs, metrics
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk.metrics import MeterProvider

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
        _reset_otel_globals()


@contextmanager
def _fresh_telemetry(monkeypatch):
    """Reload telemetry with a clean module state."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    monkeypatch.delenv(
        "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", raising=False
    )
    import dropmcp.telemetry as telemetry

    _reset_otel_globals()
    telemetry._state["configured"] = False
    telemetry._state["active"] = False
    telemetry._state["instruments"] = None
    telemetry._event_logging_configured = False
    telemetry._event_logger.handlers.clear()
    yield telemetry
    telemetry._state["configured"] = False
    telemetry._state["active"] = False
    telemetry._state["instruments"] = None
    telemetry._event_logging_configured = False
    telemetry._event_logger.handlers.clear()
    _shutdown_otel_providers()



class _RecordingInstrument:
    def __init__(self, kind: str, name: str, unit: str) -> None:
        self.kind = kind
        self.name = name
        self.unit = unit
        self.records: list[tuple[str, float, dict[str, str]]] = []

    def add(self, amount: int, attrs: dict[str, str] | None = None) -> None:
        self.records.append(("add", float(amount), dict(attrs or {})))

    def record(self, amount: float, attrs: dict[str, str] | None = None) -> None:
        self.records.append(("record", amount, dict(attrs or {})))


class _RecordingMeter:
    def __init__(self) -> None:
        self.instruments: list[_RecordingInstrument] = []

    def create_counter(self, name: str, description: str = "", unit: str = "1"):
        inst = _RecordingInstrument("counter", name, unit)
        self.instruments.append(inst)
        return inst

    def create_histogram(self, name: str, description: str = "", unit: str = "1"):
        inst = _RecordingInstrument("histogram", name, unit)
        self.instruments.append(inst)
        return inst


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


def test_track_without_otel_logs_but_does_not_export(monkeypatch, caplog):
    with _fresh_telemetry(monkeypatch) as telemetry:
        telemetry.setup_event_logging()
        with caplog.at_level(logging.INFO, logger="dropmcp.events"):
            with telemetry.track("skill", "example"):
                pass

        assert telemetry.is_active() is False
        assert any("skill example outcome=success" in r.message for r in caplog.records)


def test_log_event_uses_console_when_otel_inactive(monkeypatch, caplog):
    with _fresh_telemetry(monkeypatch) as telemetry:
        telemetry.setup_event_logging()
        with caplog.at_level(logging.INFO, logger="dropmcp.events"):
            telemetry.log_event("skill", "demo", "success", 12.5)

        event_records = [r for r in caplog.records if r.name == "dropmcp.events"]
        assert len(event_records) == 1
        assert event_records[0].mcp_event["name"] == "demo"


def test_configure_sets_service_name(monkeypatch):
    with _fresh_telemetry(monkeypatch) as telemetry:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

        def _stub_setup(service_name: str) -> None:
            os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
            os.environ.setdefault(
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "Delta"
            )
            telemetry._state["instruments"] = object()

        monkeypatch.setattr(telemetry, "_setup_otel", _stub_setup)
        assert telemetry.configure(service_name="my-skills-mcp") is True
        assert os.environ["OTEL_SERVICE_NAME"] == "my-skills-mcp"
        assert (
            os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] == "Delta"
        )


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

        _shutdown_otel_providers()


@pytest.mark.skipif(
    importlib.util.find_spec("opentelemetry") is None,
    reason="dropmcp[otel] not installed",
)
def test_metric_contract(monkeypatch):
    with _fresh_telemetry(monkeypatch) as telemetry:
        recorder = _RecordingMeter()
        instruments = telemetry._create_instruments(recorder)

        assert {inst.name for inst in recorder.instruments} == set(METRIC_NAMES)

        telemetry._state["instruments"] = instruments
        telemetry._state["active"] = True

        with telemetry.track("skill", "demo-skill"):
            pass

        with telemetry.track("prompt", "demo-prompt"):
            pass

        with telemetry.track("resource", "skill://demo/file", resource_kind="skill"):
            pass

        telemetry.record_mcp_initialization(
            outcome="success",
            duration_ms=1.0,
            client="cursor-vscode",
        )
        telemetry.record_tool_listing(
            outcome="success",
            duration_ms=2.0,
            client="cursor",
            tool_count=3,
        )

        skill_counter = instruments.skill_invocations
        assert ("add", 1.0, {
            "skill": "demo-skill",
            "client": "unknown",
            "outcome": "success",
        }) in skill_counter.records

        prompt_counter = instruments.prompt_invocations
        assert ("add", 1.0, {
            "prompt": "demo-prompt",
            "client": "unknown",
            "outcome": "success",
        }) in prompt_counter.records

        resource_counter = instruments.resource_downloads
        assert ("add", 1.0, {
            "resource": "skill://demo/file",
            "kind": "skill",
            "client": "unknown",
            "outcome": "success",
        }) in resource_counter.records

        assert ("add", 1.0, {
            "client": "cursor-vscode",
            "outcome": "success",
        }) in instruments.mcp_initializations.records

        assert ("add", 1.0, {
            "client": "cursor",
            "outcome": "success",
        }) in instruments.mcp_tool_listings.records


def test_build_server_registers_telemetry_middleware(tmp_path, monkeypatch):
    from dropmcp.config import Settings
    from dropmcp.server import build_server

    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()

    with _fresh_telemetry(monkeypatch) as telemetry:
        settings = Settings.resolve(
            skills=skills,
            prompts=prompts,
            ui_enabled=False,
            feedback_enabled=False,
            name="test-mcp",
        )
        mcp = build_server(settings)

        assert any(isinstance(m, TelemetryMiddleware) for m in mcp.middleware)
        assert telemetry.is_active() is False
