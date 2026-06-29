"""Tests for optional OpenTelemetry telemetry."""

from __future__ import annotations

import importlib
import logging
import os
from types import SimpleNamespace

import pytest
from starlette.datastructures import Headers

from dropmcp.middleware import TelemetryMiddleware
from dropmcp.telemetry import METRIC_NAMES
from otel_test_support import fresh_telemetry


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


def _request(headers: dict[str, str]):
    return SimpleNamespace(
        headers=Headers(headers),
        client=None,
        method="POST",
        url=SimpleNamespace(path="/mcp"),
    )


def _mcp_context(
    *,
    session_id: str = "session-1",
    transport: str = "streamable-http",
    request_id: str = "request-1",
    meta: dict[str, object] | None = None,
):
    return SimpleNamespace(
        session_id=session_id,
        transport=transport,
        request_context=SimpleNamespace(request_id=request_id, meta=meta),
    )


def _middleware_context(*, message, context=None):
    return SimpleNamespace(
        message=message,
        fastmcp_context=context or _mcp_context(),
    )


def _has_record(
    instrument: _RecordingInstrument,
    action: str,
    expected_attrs: dict[str, str],
) -> bool:
    return any(
        record_action == action and expected_attrs.items() <= attrs.items()
        for record_action, _amount, attrs in instrument.records
    )


def test_configure_noop_without_endpoint(monkeypatch):
    with fresh_telemetry(monkeypatch) as telemetry:
        assert telemetry.configure() is False
        assert telemetry.is_active() is False


def test_configure_noop_without_otel_packages(monkeypatch):
    with fresh_telemetry(monkeypatch) as telemetry:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

        def _raise_import(*_args, **_kwargs):
            raise ImportError("otel not installed")

        monkeypatch.setattr(telemetry, "_setup_otel", _raise_import)
        assert telemetry.configure() is False
        assert telemetry.is_active() is False


def test_track_without_otel_logs_but_does_not_export(monkeypatch, caplog):
    with fresh_telemetry(monkeypatch) as telemetry:
        telemetry.setup_event_logging()
        with caplog.at_level(logging.INFO, logger="dropmcp.events"):
            with telemetry.track("skill", "example"):
                pass

        assert telemetry.is_active() is False
        assert any("skill example outcome=success" in r.message for r in caplog.records)


def test_log_event_uses_console_when_otel_inactive(monkeypatch, caplog):
    with fresh_telemetry(monkeypatch) as telemetry:
        telemetry.setup_event_logging()
        with caplog.at_level(logging.INFO, logger="dropmcp.events"):
            telemetry.log_event("skill", "demo", "success", 12.5)

        event_records = [r for r in caplog.records if r.name == "dropmcp.events"]
        assert len(event_records) == 1
        assert event_records[0].mcp_event["name"] == "demo"


def test_request_context_logs_originator_header(monkeypatch):
    with fresh_telemetry(monkeypatch) as telemetry:
        monkeypatch.setattr(
            "fastmcp.server.dependencies.get_http_request",
            lambda: _request({"originator": "codex_cli_rs"}),
        )

        ctx = telemetry.request_context()

        assert ctx["http_originator"] == "codex_cli_rs"
        assert ctx["http.originator"] == "codex_cli_rs"
        assert telemetry.client_bucket() == "codex"


def test_client_bucket_detects_codex_user_agent(monkeypatch):
    with fresh_telemetry(monkeypatch) as telemetry:
        monkeypatch.setattr(
            "fastmcp.server.dependencies.get_http_request",
            lambda: _request({"user-agent": "OpenAI Codex CLI/0.142.3"}),
        )

        assert telemetry.client_bucket() == "codex"


def test_configure_sets_service_name(monkeypatch):
    with fresh_telemetry(monkeypatch) as telemetry:
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
    with fresh_telemetry(monkeypatch) as telemetry:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

        assert telemetry.configure(service_name="test-server") is True
        assert telemetry.is_active() is True
        assert telemetry.configure() is True

        with telemetry.track("skill", "demo"):
            pass

        with telemetry.track("resource", "skill://demo/file", resource_kind="skill"):
            pass


@pytest.mark.skipif(
    importlib.util.find_spec("opentelemetry") is None,
    reason="dropmcp[otel] not installed",
)
def test_metric_contract(monkeypatch):
    with fresh_telemetry(monkeypatch) as telemetry:
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
        assert _has_record(
            skill_counter,
            "add",
            {
                "skill": "demo-skill",
                "client": "unknown",
                "client_version": "unknown",
                "client_source": "unknown",
                "transport": "unknown",
                "team": "unknown",
                "environment": "unknown",
                "operation_kind": "skill",
                "outcome": "success",
                "error.type": "none",
            },
        )

        prompt_counter = instruments.prompt_invocations
        assert _has_record(
            prompt_counter,
            "add",
            {
                "prompt": "demo-prompt",
                "client": "unknown",
                "operation_kind": "prompt",
                "outcome": "success",
            },
        )

        resource_counter = instruments.resource_downloads
        assert _has_record(
            resource_counter,
            "add",
            {
                "resource": "skill://demo/file",
                "kind": "skill",
                "client": "unknown",
                "operation_kind": "resource",
                "outcome": "success",
            },
        )

        assert _has_record(
            instruments.mcp_initializations,
            "add",
            {
                "client": "cursor",
                "client_version": "unknown",
                "client_source": "initialize",
                "operation_kind": "initialize",
                "outcome": "success",
            },
        )

        assert _has_record(
            instruments.mcp_tool_listings,
            "add",
            {
                "client": "cursor",
                "client_source": "initialize",
                "operation_kind": "tools/list",
                "outcome": "success",
            },
        )


def test_initialize_metadata_is_cached_and_reused_by_track(monkeypatch, caplog):
    with fresh_telemetry(monkeypatch) as telemetry:
        telemetry.setup_event_logging()
        init_context = _middleware_context(
            message=SimpleNamespace(
                params={
                    "protocolVersion": "2025-03-26",
                    "clientInfo": {
                        "name": "OpenAI Codex CLI",
                        "version": "0.142.3",
                    },
                    "capabilities": {
                        "roots": {"listChanged": True},
                        "sampling": {},
                    },
                }
            ),
            context=_mcp_context(session_id="shared-session"),
        )

        telemetry.record_mcp_initialization(
            outcome="success",
            duration_ms=1.0,
            context=init_context,
        )
        monkeypatch.setattr(
            "fastmcp.server.dependencies.get_context",
            lambda: _mcp_context(session_id="shared-session"),
        )

        with caplog.at_level(logging.INFO, logger="dropmcp.events"):
            with telemetry.track("skill", "cached-skill"):
                pass

        skill_event = [
            record.mcp_event
            for record in caplog.records
            if getattr(record, "mcp_event", {}).get("kind") == "skill"
        ][-1]
        assert skill_event["mcp.protocol_version"] == "2025-03-26"
        assert skill_event["mcp.client.name.raw"] == "OpenAI Codex CLI"
        assert skill_event["mcp.client.name"] == "codex"
        assert skill_event["mcp.client.version.major_minor"] == "0.142"
        assert skill_event["mcp.client.source"] == "initialize"
        assert skill_event["mcp.client.capabilities"] == "roots,sampling"


def test_request_meta_is_sanitized_and_bucketed_for_metrics(monkeypatch, caplog):
    with fresh_telemetry(monkeypatch) as telemetry:
        telemetry.setup_event_logging()
        recorder = _RecordingMeter()
        instruments = telemetry._create_instruments(recorder)
        telemetry._state["instruments"] = instruments
        telemetry._state["active"] = True

        monkeypatch.setattr(
            "fastmcp.server.dependencies.get_context",
            lambda: _mcp_context(
                meta={
                    "agent": "Cursor",
                    "team": "supply",
                    "environment": "local",
                    "repo": "r" * 200,
                    "launcher": "Bearer glpat-abcdefghijklmnop",
                    "nested": {"drop": "me"},
                    "api_key": "secret",
                }
            ),
        )

        with caplog.at_level(logging.INFO, logger="dropmcp.events"):
            with telemetry.track("skill", "meta-skill"):
                pass

        event = [
            record.mcp_event
            for record in caplog.records
            if getattr(record, "mcp_event", {}).get("name") == "meta-skill"
        ][-1]
        assert event["mcp.meta.agent"] == "Cursor"
        assert event["mcp.meta.team"] == "supply"
        assert event["mcp.meta.environment"] == "local"
        assert event["mcp.meta.repo"].endswith("...")
        assert event["mcp.meta.launcher"] == "[redacted]"
        assert "mcp.meta.nested" not in event
        assert "mcp.meta.api_key" not in event

        attrs = instruments.skill_invocations.records[-1][2]
        assert attrs["client"] == "cursor"
        assert attrs["client_source"] == "meta"
        assert attrs["team"] == "supply"
        assert attrs["environment"] == "local"
        assert "repo" not in attrs


def test_metric_cardinality_rolls_unknown_values_to_buckets(monkeypatch):
    with fresh_telemetry(monkeypatch) as telemetry:
        recorder = _RecordingMeter()
        instruments = telemetry._create_instruments(recorder)
        telemetry._state["instruments"] = instruments
        telemetry._state["active"] = True

        telemetry.record_tool_listing(
            outcome="success",
            duration_ms=2.0,
            tool_count=3,
            metadata={
                "mcp.client.name.raw": "Internal Wrapper 872364987263",
                "mcp.client.version.raw": "build-abcdef123456",
                "mcp.client.source": "initialize",
                "mcp.transport": "preview-http-98234",
                "mcp.meta.team": "new-team-98234",
                "mcp.meta.environment": "preview-98234",
            },
        )

        attrs = instruments.mcp_tool_listings.records[-1][2]
        assert attrs["client"] == "other"
        assert attrs["client_version"] == "other"
        assert attrs["client_source"] == "initialize"
        assert attrs["transport"] == "other"
        assert attrs["team"] == "other"
        assert attrs["environment"] == "other"
        assert attrs["operation_kind"] == "tools/list"


def test_error_context_is_sanitized_for_logs_and_bounded_for_metrics(
    monkeypatch, caplog
):
    with fresh_telemetry(monkeypatch) as telemetry:
        telemetry.setup_event_logging()
        recorder = _RecordingMeter()
        instruments = telemetry._create_instruments(recorder)
        telemetry._state["instruments"] = instruments
        telemetry._state["active"] = True

        with caplog.at_level(logging.WARNING, logger="dropmcp.events"):
            with pytest.raises(RuntimeError):
                with telemetry.track("skill", "broken"):
                    raise RuntimeError("failed with Bearer glpat-abcdefghijklmnop")

        event = [
            record.mcp_event
            for record in caplog.records
            if getattr(record, "mcp_event", {}).get("name") == "broken"
        ][-1]
        assert event["error.type"] == "RuntimeError"
        assert event["mcp.error.message"] == "failed with [redacted]"

        attrs = instruments.skill_invocations.records[-1][2]
        assert attrs["outcome"] == "error"
        assert attrs["error.type"] == "RuntimeError"


def test_build_server_registers_telemetry_middleware(tmp_path, monkeypatch):
    from dropmcp.config import Settings
    from dropmcp.server import build_server

    skills = tmp_path / "skills"
    prompts = tmp_path / "prompts"
    skills.mkdir()
    prompts.mkdir()

    with fresh_telemetry(monkeypatch) as telemetry:
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
