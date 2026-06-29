"""Optional, env-gated OpenTelemetry telemetry.

All OTEL imports are deferred until ``configure()`` runs with
``OTEL_EXPORTER_OTLP_ENDPOINT`` set and ``dropmcp[otel]`` installed. Without
the endpoint or optional deps, ``track()`` is a near-zero-cost no-op and no
OTEL packages are imported.

Providers wrap skill invocations, prompt renders, and resource reads in
``track(...)``; protocol-level events (``initialize``, ``tools/list``) are
handled by :mod:`dropmcp.middleware`.
"""

from __future__ import annotations

import atexit
import logging
import os
import re
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_FLUSH_TIMEOUT_MS = 5000

_LOGGED_HEADERS = (
    "originator",
    "user-agent",
    "x-forwarded-for",
    "x-real-ip",
    "x-forwarded-proto",
    "x-request-id",
    "mcp-session-id",
)

_UA_PRODUCT_RE = re.compile(r"^([A-Za-z0-9._-]+)")

_event_logger = logging.getLogger("dropmcp.events")

_event_logging_configured = False

# Stable metric names for dashboards and contract tests.
METRIC_NAMES = (
    "skill.invocations",
    "skill.invocation.duration",
    "prompt.invocations",
    "prompt.invocation.duration",
    "resource.downloads",
    "resource.download.duration",
    "mcp.initializations",
    "mcp.tool_listings",
)


@dataclass
class _Instruments:
    skill_invocations: Any
    skill_invocation_duration_ms: Any
    prompt_invocations: Any
    prompt_invocation_duration_ms: Any
    resource_downloads: Any
    resource_download_duration_ms: Any
    mcp_initializations: Any
    mcp_tool_listings: Any


_state: dict[str, Any] = {
    "configured": False,
    "active": False,
    "instruments": None,
}


def _otel_endpoint_set() -> bool:
    return bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))


def is_active() -> bool:
    """Return whether telemetry is configured and exporting."""
    return bool(_state["active"])


def setup_event_logging() -> None:
    """Ensure structured invocation logs reach the console.

    When OTLP export is active, the root logger also receives an OTEL handler;
    otherwise console output is the only sink for per-invocation events.
    """
    global _event_logging_configured
    if _event_logging_configured:
        return
    _event_logging_configured = True
    _event_logger.setLevel(logging.INFO)
    if not _event_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        _event_logger.addHandler(handler)


def configure(*, service_name: str = "dropmcp") -> bool:
    """Initialise OTEL exporters when the OTLP endpoint env var is set.

    Returns ``True`` when metrics/logs export is active. Safe to call more
    than once; later calls are no-ops. Structured per-invocation logs are
    always enabled via :func:`setup_event_logging`.
    """
    setup_event_logging()

    if _state["configured"]:
        return bool(_state["active"])

    _state["configured"] = True

    if not _otel_endpoint_set():
        return False

    try:
        _setup_otel(service_name)
    except ImportError:
        logger.warning(
            "OTEL_EXPORTER_OTLP_ENDPOINT is set but OpenTelemetry is not "
            "installed — install dropmcp[otel] to enable telemetry"
        )
        return False
    except Exception:
        logger.warning("Failed to initialise OpenTelemetry", exc_info=True)
        return False

    _state["active"] = True
    return True


def _setup_otel(service_name: str) -> None:
    from opentelemetry import metrics

    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    os.environ.setdefault(
        "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "Delta"
    )

    resource = _service_resource(service_name)
    _setup_logging(resource)
    _setup_metrics(resource, metrics)

    meter = metrics.get_meter("dropmcp")
    _state["instruments"] = _create_instruments(meter)
    logger.info("OpenTelemetry telemetry configured for service %s", service_name)


def _create_instruments(meter) -> _Instruments:
    return _Instruments(
        skill_invocations=meter.create_counter(
            name="skill.invocations",
            description="Number of times an MCP skill tool was invoked",
            unit="1",
        ),
        skill_invocation_duration_ms=meter.create_histogram(
            name="skill.invocation.duration",
            description="Wall-clock time spent serving a skill tool invocation",
            unit="ms",
        ),
        prompt_invocations=meter.create_counter(
            name="prompt.invocations",
            description="Number of times an MCP prompt was rendered",
            unit="1",
        ),
        prompt_invocation_duration_ms=meter.create_histogram(
            name="prompt.invocation.duration",
            description="Wall-clock time spent rendering a prompt",
            unit="ms",
        ),
        resource_downloads=meter.create_counter(
            name="resource.downloads",
            description="Number of times an MCP resource was read (downloaded)",
            unit="1",
        ),
        resource_download_duration_ms=meter.create_histogram(
            name="resource.download.duration",
            description="Wall-clock time spent serving a resource read",
            unit="ms",
        ),
        mcp_initializations=meter.create_counter(
            name="mcp.initializations",
            description=(
                "Number of MCP initialize handshakes — roughly one per "
                "client session that received server instructions"
            ),
            unit="1",
        ),
        mcp_tool_listings=meter.create_counter(
            name="mcp.tool_listings",
            description="Number of tools/list calls from MCP clients",
            unit="1",
        ),
    )


def _service_resource(service_name: str):
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource

    name = os.environ.get("OTEL_SERVICE_NAME", service_name)
    return Resource.create({SERVICE_NAME: name})


def _flush_on_exit(provider: Any, label: str) -> None:
    atexit.register(_safe_shutdown, provider, label)


def _safe_shutdown(provider: Any, label: str) -> None:
    """Flush and shut a provider down without blocking process exit.

    The OTLP HTTP exporter retries with exponential backoff, so flushing to an
    unreachable collector can take ~60s and ignores the requested flush timeout.
    Run the flush on a daemon thread and wait at most ``_FLUSH_TIMEOUT_MS``; if it
    overruns, abandon it (the daemon thread dies with the process) so shutdown
    stays bounded.
    """

    def _run() -> None:
        try:
            force_flush = getattr(provider, "force_flush", None)
            if callable(force_flush):
                force_flush(_FLUSH_TIMEOUT_MS)
            provider.shutdown()
        except Exception:
            logger.warning(
                "Failed to shut down OTel %s provider", label, exc_info=True
            )

    worker = threading.Thread(
        target=_run, name=f"dropmcp-otel-shutdown-{label}", daemon=True
    )
    worker.start()
    worker.join(_FLUSH_TIMEOUT_MS / 1000)
    if worker.is_alive():
        logger.warning(
            "OTel %s provider shutdown exceeded %dms; abandoning flush",
            label,
            _FLUSH_TIMEOUT_MS,
        )


def _setup_logging(resource) -> None:
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    provider = LoggerProvider(resource=resource, shutdown_on_exit=False)
    provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(provider)

    handler = LoggingHandler(level=logging.NOTSET, logger_provider=provider)
    logging.getLogger().addHandler(handler)
    _flush_on_exit(provider, "log")


def _setup_metrics(resource, metrics_module) -> None:
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    provider = MeterProvider(
        resource=resource, metric_readers=[reader], shutdown_on_exit=False
    )
    metrics_module.set_meter_provider(provider)
    _flush_on_exit(provider, "metric")


def request_context() -> dict[str, Any]:
    """Best-effort snapshot of the active HTTP request for log enrichment."""
    try:
        from fastmcp.server.dependencies import get_http_request
    except Exception:
        return {}

    try:
        request = get_http_request()
    except Exception:
        return {}

    ctx: dict[str, Any] = {}
    try:
        client = getattr(request, "client", None)
        if client is not None and getattr(client, "host", None):
            ctx["client_host"] = client.host
            if getattr(client, "port", None):
                ctx["client_port"] = client.port

        headers = getattr(request, "headers", {}) or {}
        for header in _LOGGED_HEADERS:
            value = headers.get(header) if hasattr(headers, "get") else None
            if value:
                ctx[f"http_{header.replace('-', '_')}"] = value

        method = getattr(request, "method", None)
        if method:
            ctx["http_method"] = method
        url = getattr(request, "url", None)
        if url is not None:
            ctx["http_path"] = getattr(url, "path", None)
    except Exception:
        return ctx

    return ctx


def client_bucket() -> str:
    """Low-cardinality client identifier for the active HTTP request."""
    ctx = request_context()
    originator = ctx.get("http_originator")
    if originator:
        match = _UA_PRODUCT_RE.match(originator)
        return match.group(1).lower() if match else "other"

    ua = ctx.get("http_user_agent")
    if not ua:
        return "unknown"
    if "codex" in ua.lower():
        return "codex"
    match = _UA_PRODUCT_RE.match(ua)
    return match.group(1).lower() if match else "other"


def log_event(
    kind: str,
    name: str,
    outcome: str,
    duration_ms: float,
    **extra: Any,
) -> None:
    """Emit a structured log line for an MCP invocation or download."""
    fields: dict[str, Any] = {
        "event": f"{kind}.invoked" if kind != "resource" else "resource.read",
        "kind": kind,
        "name": name,
        "outcome": outcome,
        "duration_ms": round(duration_ms, 2),
    }
    fields.update(request_context())
    fields.update({k: v for k, v in extra.items() if v is not None})

    level = logging.WARNING if outcome == "error" else logging.INFO
    _event_logger.log(
        level,
        "%s %s outcome=%s duration_ms=%.2f",
        kind,
        name,
        outcome,
        duration_ms,
        extra={"mcp_event": fields},
    )


def _instruments() -> _Instruments | None:
    return _state.get("instruments")


@contextmanager
def track(kind: str, name: str, **extra: Any) -> Iterator[None]:
    """Wrap an operation so it is timed, logged, and optionally metered.

    ``kind`` is one of ``"skill"``, ``"prompt"``, or ``"resource"``.
    ``name`` identifies the specific item. For resource reads, pass
    ``resource_kind`` in ``extra`` (e.g. ``"prompt"`` or ``"skill"``).

    Structured logs are always emitted (console when OTLP is off). OpenTelemetry
    counters and histograms are recorded only when export is configured.
    """
    start = time.perf_counter()
    outcome = "success"
    try:
        yield
    except Exception:
        outcome = "error"
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        _record(kind, name, outcome, duration_ms, **extra)


def _record(
    kind: str,
    name: str,
    outcome: str,
    duration_ms: float,
    **extra: Any,
) -> None:
    client = client_bucket()

    if kind == "skill":
        attrs = {"skill": name, "client": client}
        log_event(kind="skill", name=name, outcome=outcome, duration_ms=duration_ms)
        _record_metrics(
            kind,
            attrs=attrs,
            outcome=outcome,
            duration_ms=duration_ms,
        )
        return

    if kind == "prompt":
        attrs = {"prompt": name, "client": client}
        log_event(kind="prompt", name=name, outcome=outcome, duration_ms=duration_ms)
        _record_metrics(
            kind,
            attrs=attrs,
            outcome=outcome,
            duration_ms=duration_ms,
        )
        return

    resource_kind = extra.get("resource_kind", kind)
    attrs = {"resource": name, "kind": resource_kind, "client": client}
    log_event(
        kind="resource",
        name=name,
        outcome=outcome,
        duration_ms=duration_ms,
        resource_kind=resource_kind,
    )
    _record_metrics(
        kind,
        attrs=attrs,
        outcome=outcome,
        duration_ms=duration_ms,
    )


def _record_metrics(
    kind: str,
    *,
    attrs: dict[str, str],
    outcome: str,
    duration_ms: float,
) -> None:
    instruments = _instruments()
    if instruments is None:
        return

    if kind == "skill":
        instruments.skill_invocations.add(1, {**attrs, "outcome": outcome})
        instruments.skill_invocation_duration_ms.record(duration_ms, attrs)
        return

    if kind == "prompt":
        instruments.prompt_invocations.add(1, {**attrs, "outcome": outcome})
        instruments.prompt_invocation_duration_ms.record(duration_ms, attrs)
        return

    instruments.resource_downloads.add(1, {**attrs, "outcome": outcome})
    instruments.resource_download_duration_ms.record(duration_ms, attrs)


def record_mcp_initialization(
    *,
    outcome: str,
    duration_ms: float,
    client: str,
    **info: Any,
) -> None:
    log_event(
        kind="mcp",
        name="initialize",
        outcome=outcome,
        duration_ms=duration_ms,
        **info,
    )
    instruments = _instruments()
    if instruments is None:
        return
    instruments.mcp_initializations.add(1, {"client": client, "outcome": outcome})


def record_tool_listing(
    *,
    outcome: str,
    duration_ms: float,
    client: str,
    tool_count: int | None,
) -> None:
    log_event(
        kind="mcp",
        name="tools/list",
        outcome=outcome,
        duration_ms=duration_ms,
        tool_count=tool_count,
    )
    instruments = _instruments()
    if instruments is None:
        return
    instruments.mcp_tool_listings.add(1, {"client": client, "outcome": outcome})
