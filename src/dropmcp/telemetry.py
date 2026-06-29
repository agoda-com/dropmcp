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
from collections.abc import Iterator, Mapping
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
_UA_VERSION_RE = re.compile(r"/([0-9]+(?:\.[0-9A-Za-z._-]+)?)")
_VERSION_RE = re.compile(r"^v?([0-9]+)(?:\.([0-9]+))?")
_SECRET_KEY_RE = re.compile(
    r"(authorization|cookie|credential|passwd|password|secret|token|api[_-]?key|key)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~+/\-=]+|"
    r"(?:sk|ghp|github_pat|glpat)-[a-z0-9_\-]{8,})"
)

_MAX_LOG_STRING_LENGTH = 256
_MAX_META_STRING_LENGTH = 128
_MAX_ERROR_MESSAGE_LENGTH = 512
_SESSION_METADATA_CACHE_LIMIT = 2048

_ALLOWED_META_KEYS = frozenset(
    {
        "agent",
        "ide",
        "team",
        "repo",
        "environment",
        "launcher",
        "launcher_version",
        "trace_id",
    }
)

_SESSION_CACHE_FIELDS = frozenset(
    {
        "mcp.session_id",
        "mcp.transport",
        "mcp.protocol_version",
        "mcp.client.name.raw",
        "mcp.client.name",
        "mcp.client.version.raw",
        "mcp.client.version.major_minor",
        "mcp.client.source",
        "mcp.client.capabilities",
        "mcp.auth.subject",
        "mcp.auth.source",
        "http.originator",
        "user_agent.original",
        "user_agent.name",
        "user_agent.version",
    }
)

_KNOWN_CLIENT_SOURCES = {"initialize", "originator", "user_agent", "meta", "unknown"}
_KNOWN_ENVIRONMENTS = {
    "ci",
    "dev",
    "development",
    "local",
    "prod",
    "production",
    "qa",
    "stage",
    "staging",
    "test",
    "unknown",
}
_DEFAULT_TEAM_BUCKETS = {"ai", "data", "infra", "platform", "supply", "unknown"}
_KNOWN_TRANSPORTS = {"in-memory", "sse", "stdio", "streamable-http", "unknown"}
_KNOWN_OPERATION_KINDS = {
    "initialize",
    "prompt",
    "prompt_tool",
    "resource",
    "skill",
    "tools/list",
    "unknown",
}

_event_logger = logging.getLogger("dropmcp.events")

_event_logging_configured = False
_session_metadata_lock = threading.Lock()
_session_metadata: dict[str, dict[str, Any]] = {}

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


def _safe_attr(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _get_value(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        for name in names:
            if name in obj:
                return obj[name]
        return None
    for name in names:
        value = _safe_attr(obj, name)
        if value is not None:
            return value
    return None


def _clean_string(value: Any, *, max_length: int = _MAX_LOG_STRING_LENGTH) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, int | float | str):
        text = str(value)
    else:
        return None

    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text).strip()
    if not text:
        return None
    text = _SECRET_VALUE_RE.sub("[redacted]", text)
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def _sanitize_log_value(value: Any) -> Any:
    if isinstance(value, bool | int | float):
        return value
    return _clean_string(value)


def _sanitize_log_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        safe_key = _clean_string(key)
        if not safe_key or _SECRET_KEY_RE.search(safe_key):
            continue
        safe_value = _sanitize_log_value(value)
        if safe_value is not None:
            clean[safe_key] = safe_value
    return clean


def _slug(value: Any) -> str:
    text = _clean_string(value, max_length=64)
    if not text:
        return "unknown"
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "unknown"


def _normalize_client_name(value: Any) -> str:
    raw = _slug(value)
    if raw == "unknown":
        return "unknown"
    if "codex" in raw:
        return "codex"
    if "cursor" in raw:
        return "cursor"
    if "claude" in raw and "code" in raw:
        return "claude-code"
    if "chatgpt" in raw:
        return "chatgpt"
    if raw in {"code", "visual-studio-code", "vscode"}:
        return "vscode"
    if "fastmcp" in raw:
        return "fastmcp-client"
    return "other"


def _normalize_version(value: Any) -> str:
    text = _clean_string(value, max_length=64)
    if not text:
        return "unknown"
    if text.lower() in {"other", "unknown"}:
        return text.lower()
    match = _VERSION_RE.match(text.strip())
    if not match:
        return "other"
    major, minor = match.groups()
    return f"{major}.{minor}" if minor is not None else major


def _parse_user_agent(value: Any) -> dict[str, str]:
    text = _clean_string(value)
    if not text:
        return {}
    fields: dict[str, str] = {"user_agent.original": text}
    product = _UA_PRODUCT_RE.match(text)
    if product:
        fields["user_agent.name"] = product.group(1).lower()
    version = _UA_VERSION_RE.search(text)
    if version:
        fields["user_agent.version"] = _clean_string(
            version.group(1), max_length=64
        ) or "unknown"
    return fields


def _object_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    model_dump = _safe_attr(value, "model_dump")
    if callable(model_dump):
        try:
            dumped = model_dump(exclude_none=True)
            if isinstance(dumped, Mapping):
                return dumped
        except Exception:
            pass
    extra = _safe_attr(value, "model_extra") or _safe_attr(value, "__pydantic_extra__")
    if isinstance(extra, Mapping):
        return extra
    return {}


def _meta_fields(meta: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key, value in _object_mapping(meta).items():
        key_text = _clean_string(key, max_length=64)
        if not key_text:
            continue
        key_name = key_text.lower()
        if key_name not in _ALLOWED_META_KEYS or _SECRET_KEY_RE.search(key_name):
            continue
        clean_value = _clean_string(value, max_length=_MAX_META_STRING_LENGTH)
        if clean_value is not None:
            fields[f"mcp.meta.{key_name}"] = clean_value
    return fields


def _capabilities_summary(capabilities: Any) -> str | None:
    if capabilities is None:
        return None

    enabled: list[str] = []
    for name in ("elicitation", "roots", "sampling", "tasks"):
        if _get_value(capabilities, name) is not None:
            enabled.append(name)
    experimental = _get_value(capabilities, "experimental")
    if experimental:
        enabled.append("experimental")
    return ",".join(enabled) if enabled else "none"


def _initialize_fields(message: Any) -> dict[str, Any]:
    params = _get_value(message, "params") or message
    fields: dict[str, Any] = {}

    protocol_version = _get_value(params, "protocolVersion", "protocol_version")
    if protocol_version is not None:
        fields["mcp.protocol_version"] = protocol_version

    client_info = _get_value(params, "clientInfo", "client_info")
    client_name = _get_value(client_info, "name")
    client_version = _get_value(client_info, "version")
    if client_name is not None:
        fields["mcp.client.name.raw"] = client_name
        fields["client_name"] = client_name
    if client_version is not None:
        fields["mcp.client.version.raw"] = client_version
        fields["client_version"] = client_version

    capabilities = _capabilities_summary(_get_value(params, "capabilities"))
    if capabilities is not None:
        fields["mcp.client.capabilities"] = capabilities

    fields.update(_meta_fields(_get_value(params, "meta", "_meta")))
    return _sanitize_log_fields(fields)


def _fastmcp_context(context: Any | None = None) -> Any | None:
    if context is not None:
        fastmcp_context = _safe_attr(context, "fastmcp_context")
        if fastmcp_context is not None:
            return fastmcp_context
        if _safe_attr(context, "session_id") is not None or _safe_attr(
            context, "request_context"
        ) is not None:
            return context

    try:
        from fastmcp.server.dependencies import get_context

        return get_context()
    except Exception:
        return None


def _context_fields(context: Any | None = None) -> dict[str, Any]:
    ctx = _fastmcp_context(context)
    if ctx is None:
        return {}

    fields: dict[str, Any] = {}
    session_id = _safe_attr(ctx, "session_id")
    if session_id is not None:
        fields["mcp.session_id"] = session_id

    transport = _safe_attr(ctx, "transport")
    if transport is not None:
        fields["mcp.transport"] = transport

    request_context = _safe_attr(ctx, "request_context")
    if request_context is not None:
        request_id = _safe_attr(request_context, "request_id")
        if request_id is not None:
            fields["mcp.request_id"] = request_id
        fields.update(_meta_fields(_safe_attr(request_context, "meta")))

    return _sanitize_log_fields(fields)


def _auth_fields() -> dict[str, Any]:
    try:
        from fastmcp.server.dependencies import get_access_token

        access_token = get_access_token()
    except Exception:
        return {}

    if access_token is None:
        return {}

    claims = _safe_attr(access_token, "claims")
    subject = None
    source = None
    if isinstance(claims, Mapping):
        for claim in ("sub", "oid", "client_id", "email"):
            value = claims.get(claim)
            if value:
                subject = value
                source = f"claim:{claim}"
                break
    if subject is None:
        subject = _safe_attr(access_token, "client_id")
        source = "client_id" if subject else None

    fields: dict[str, Any] = {}
    if subject:
        fields["mcp.auth.subject"] = subject
    if source:
        fields["mcp.auth.source"] = source
    return _sanitize_log_fields(fields)


def _session_id_from(fields: Mapping[str, Any]) -> str | None:
    session_id = fields.get("mcp.session_id") or fields.get("http_mcp_session_id")
    return _clean_string(session_id, max_length=128)


def _cached_session_metadata(session_id: str | None) -> dict[str, Any]:
    if not session_id:
        return {}
    with _session_metadata_lock:
        return dict(_session_metadata.get(session_id, {}))


def _cache_session_metadata(fields: Mapping[str, Any]) -> None:
    session_id = _session_id_from(fields)
    if not session_id:
        return
    cached = {k: v for k, v in fields.items() if k in _SESSION_CACHE_FIELDS}
    if not cached:
        return
    with _session_metadata_lock:
        if len(_session_metadata) >= _SESSION_METADATA_CACHE_LIMIT:
            _session_metadata.clear()
        _session_metadata[session_id] = cached


def _resolve_client_fields(fields: dict[str, Any]) -> None:
    source = "unknown"
    raw_client = None
    raw_version = None

    if fields.get("mcp.client.name.raw"):
        source = "initialize"
        raw_client = fields.get("mcp.client.name.raw")
        raw_version = fields.get("mcp.client.version.raw")
    elif fields.get("http.originator"):
        source = "originator"
        raw_client = fields.get("http.originator")
    elif fields.get("user_agent.original"):
        source = "user_agent"
        raw_client = fields.get("user_agent.original")
        raw_version = fields.get("user_agent.version")
    elif fields.get("mcp.meta.agent"):
        source = "meta"
        raw_client = fields.get("mcp.meta.agent")

    fields["mcp.client.name"] = _normalize_client_name(raw_client)
    fields["mcp.client.source"] = source
    fields["mcp.client.version.major_minor"] = _normalize_version(raw_version)


def metadata_envelope(
    *,
    context: Any | None = None,
    initialize_message: Any | None = None,
    extra: Mapping[str, Any] | None = None,
    error: BaseException | None = None,
) -> dict[str, Any]:
    """Build the sanitized metadata envelope shared by logs and metrics.

    Self-reported MCP and request values are telemetry-only signals. They must
    not be used as authorization or trust boundaries.
    """
    context_fields = _context_fields(context)
    http_fields = request_context()
    session_id = _session_id_from(context_fields) or _session_id_from(http_fields)

    fields: dict[str, Any] = {}
    fields.update(_cached_session_metadata(session_id))
    fields.update(context_fields)
    fields.update(http_fields)
    if initialize_message is not None:
        fields.update(_initialize_fields(initialize_message))
    fields.update(_auth_fields())
    if extra:
        fields.update(_sanitize_log_fields(extra))
    if error is not None:
        fields.update(_error_fields(error))

    _resolve_client_fields(fields)
    return fields


def cache_initialize_metadata(context: Any) -> dict[str, Any]:
    """Extract and cache static initialize metadata for later session events."""
    fields = metadata_envelope(
        context=context,
        initialize_message=_safe_attr(context, "message"),
    )
    _cache_session_metadata(fields)
    return fields


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
                clean_value = _clean_string(value)
                if not clean_value:
                    continue
                ctx[f"http_{header.replace('-', '_')}"] = clean_value
                if header == "originator":
                    ctx["http.originator"] = clean_value
                elif header == "user-agent":
                    ctx.update(_parse_user_agent(clean_value))
                elif header == "x-forwarded-proto":
                    ctx["http.forwarded_proto"] = clean_value
                elif header == "x-request-id":
                    ctx["http.request_id"] = clean_value
                elif header == "mcp-session-id":
                    ctx["mcp.session_id"] = clean_value

        method = getattr(request, "method", None)
        if method:
            ctx["http_method"] = method
            ctx["http.request.method"] = method
        url = getattr(request, "url", None)
        if url is not None:
            ctx["http_path"] = getattr(url, "path", None)
            ctx["url.path"] = getattr(url, "path", None)
    except Exception:
        return ctx

    return _sanitize_log_fields(ctx)


def client_bucket() -> str:
    """Low-cardinality client identifier for the active MCP/HTTP request."""
    return str(metadata_envelope().get("mcp.client.name", "unknown"))


def _operation_kind(kind: str, name: str) -> str:
    if kind == "mcp" and name in {"initialize", "tools/list"}:
        return name
    return kind


def _operation_fields(kind: str, name: str) -> dict[str, Any]:
    operation_kind = _operation_kind(kind, name)
    fields: dict[str, Any] = {
        "mcp.operation.kind": operation_kind,
        "mcp.operation.name": name,
    }
    if kind == "skill":
        fields["mcp.tool.name"] = name
    elif kind in {"prompt", "prompt_tool"}:
        fields["mcp.prompt.name"] = name
    elif kind == "resource":
        fields["mcp.resource.name"] = name
    return _sanitize_log_fields(fields)


def _error_type(error: BaseException | None) -> str:
    if error is None:
        return "none"
    name = error.__class__.__name__
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", name):
        return name
    return "other"


def _error_fields(error: BaseException) -> dict[str, Any]:
    fields: dict[str, Any] = {"error.type": _error_type(error)}
    code = _safe_attr(error, "code") or _safe_attr(error, "error_code")
    if code is not None:
        fields["mcp.error.code"] = code
    message = _clean_string(str(error), max_length=_MAX_ERROR_MESSAGE_LENGTH)
    if message is not None:
        fields["mcp.error.message"] = message
    return _sanitize_log_fields(fields)


def log_event(
    kind: str,
    name: str,
    outcome: str,
    duration_ms: float,
    *,
    metadata: Mapping[str, Any] | None = None,
    error: BaseException | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Emit a structured log line for an MCP invocation or download."""
    fields: dict[str, Any] = dict(metadata or metadata_envelope(error=error))
    fields.update(
        {
            "event": f"{kind}.invoked" if kind != "resource" else "resource.read",
            "kind": kind,
            "name": name,
            "outcome": outcome,
            "duration_ms": round(duration_ms, 2),
        }
    )
    fields.update(_operation_fields(kind, name))
    fields.update(_sanitize_log_fields(extra))
    if error is not None:
        fields.update(_error_fields(error))

    fields = _sanitize_log_fields(fields)
    fields.update(
        {
            "event": f"{kind}.invoked" if kind != "resource" else "resource.read",
            "kind": kind,
            "name": name,
            "outcome": outcome,
            "duration_ms": round(duration_ms, 2),
        }
    )

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
    return fields


def _instruments() -> _Instruments | None:
    return _state.get("instruments")


def _metric_text(value: Any, *, max_length: int = 128) -> str:
    return _clean_string(value, max_length=max_length) or "unknown"


def _known_or_other(value: Any, known: set[str]) -> str:
    text = _clean_string(value, max_length=64)
    if not text:
        return "unknown"
    normalized = text.lower()
    if normalized in known:
        return normalized
    slug = _slug(value)
    if slug == "unknown":
        return "unknown"
    return slug if slug in known else "other"


def _environment_bucket(value: Any) -> str:
    slug = _slug(value)
    aliases = {
        "development": "dev",
        "production": "prod",
        "stage": "staging",
    }
    slug = aliases.get(slug, slug)
    if slug == "unknown":
        return "unknown"
    return slug if slug in _KNOWN_ENVIRONMENTS else "other"


def _allowed_team_buckets() -> set[str]:
    configured = os.environ.get("DROPMCP_TELEMETRY_TEAM_BUCKETS")
    if not configured:
        return set(_DEFAULT_TEAM_BUCKETS)
    values = {_slug(value) for value in configured.split(",")}
    return {value for value in values if value != "unknown"} | {"unknown"}


def _team_bucket(value: Any) -> str:
    slug = _slug(value)
    if slug == "unknown":
        return "unknown"
    return slug if slug in _allowed_team_buckets() else "other"


def _metric_attrs(
    fields: Mapping[str, Any],
    *,
    outcome: str,
    error: BaseException | None,
) -> dict[str, str]:
    return {
        "client": _normalize_client_name(fields.get("mcp.client.name")),
        "client_version": _normalize_version(
            fields.get("mcp.client.version.major_minor")
        ),
        "client_source": _known_or_other(
            fields.get("mcp.client.source"), _KNOWN_CLIENT_SOURCES
        ),
        "transport": _known_or_other(fields.get("mcp.transport"), _KNOWN_TRANSPORTS),
        "team": _team_bucket(fields.get("mcp.meta.team")),
        "environment": _environment_bucket(fields.get("mcp.meta.environment")),
        "operation_kind": _known_or_other(
            fields.get("mcp.operation.kind"), _KNOWN_OPERATION_KINDS
        ),
        "outcome": "error" if outcome == "error" else "success",
        "error.type": _metric_text(fields.get("error.type") or _error_type(error)),
    }


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
    error: BaseException | None = None
    try:
        yield
    except Exception as exc:
        outcome = "error"
        error = exc
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        _record(kind, name, outcome, duration_ms, error=error, **extra)


def _record(
    kind: str,
    name: str,
    outcome: str,
    duration_ms: float,
    *,
    error: BaseException | None = None,
    **extra: Any,
) -> None:
    if kind == "skill":
        fields = log_event(
            kind="skill",
            name=name,
            outcome=outcome,
            duration_ms=duration_ms,
            error=error,
            **extra,
        )
        attrs = {
            **_metric_attrs(fields, outcome=outcome, error=error),
            "skill": _metric_text(name),
        }
        _record_metrics(
            kind,
            attrs=attrs,
            duration_ms=duration_ms,
        )
        return

    if kind == "prompt":
        fields = log_event(
            kind="prompt",
            name=name,
            outcome=outcome,
            duration_ms=duration_ms,
            error=error,
            **extra,
        )
        attrs = {
            **_metric_attrs(fields, outcome=outcome, error=error),
            "prompt": _metric_text(name),
        }
        _record_metrics(
            kind,
            attrs=attrs,
            duration_ms=duration_ms,
        )
        return

    resource_kind = extra.get("resource_kind", kind)
    fields = log_event(
        kind="resource",
        name=name,
        outcome=outcome,
        duration_ms=duration_ms,
        error=error,
        resource_kind=resource_kind,
    )
    attrs = {
        **_metric_attrs(fields, outcome=outcome, error=error),
        "resource": _metric_text(name),
        "kind": _metric_text(resource_kind, max_length=64),
    }
    _record_metrics(
        kind,
        attrs=attrs,
        duration_ms=duration_ms,
    )


def _record_metrics(
    kind: str,
    *,
    attrs: dict[str, str],
    duration_ms: float,
) -> None:
    instruments = _instruments()
    if instruments is None:
        return

    if kind == "skill":
        instruments.skill_invocations.add(1, attrs)
        instruments.skill_invocation_duration_ms.record(duration_ms, attrs)
        return

    if kind == "prompt":
        instruments.prompt_invocations.add(1, attrs)
        instruments.prompt_invocation_duration_ms.record(duration_ms, attrs)
        return

    instruments.resource_downloads.add(1, attrs)
    instruments.resource_download_duration_ms.record(duration_ms, attrs)


def record_mcp_initialization(
    *,
    outcome: str,
    duration_ms: float,
    client: str | None = None,
    context: Any | None = None,
    metadata: Mapping[str, Any] | None = None,
    error: BaseException | None = None,
    **info: Any,
) -> None:
    event_metadata = dict(metadata or {})
    if context is not None and metadata is None:
        event_metadata.update(cache_initialize_metadata(context))
    if not event_metadata:
        event_metadata.update(metadata_envelope(extra=info, error=error))

    info = dict(info)
    client_name = info.pop("client_name", None)
    client_version = info.pop("client_version", None)
    if client is not None:
        event_metadata["mcp.client.name.raw"] = client
    elif client_name is not None:
        event_metadata["mcp.client.name.raw"] = client_name
    if client_version is not None:
        event_metadata["mcp.client.version.raw"] = client_version
    if info:
        event_metadata.update(_sanitize_log_fields(info))
    _resolve_client_fields(event_metadata)

    fields = log_event(
        kind="mcp",
        name="initialize",
        outcome=outcome,
        duration_ms=duration_ms,
        metadata=event_metadata,
        error=error,
    )
    instruments = _instruments()
    if instruments is None:
        return
    instruments.mcp_initializations.add(
        1,
        _metric_attrs(fields, outcome=outcome, error=error),
    )


def record_tool_listing(
    *,
    outcome: str,
    duration_ms: float,
    client: str | None = None,
    tool_count: int | None,
    context: Any | None = None,
    metadata: Mapping[str, Any] | None = None,
    error: BaseException | None = None,
) -> None:
    event_metadata = dict(
        metadata or metadata_envelope(context=context, error=error)
    )
    if client is not None:
        event_metadata["mcp.client.name.raw"] = client
    _resolve_client_fields(event_metadata)

    fields = log_event(
        kind="mcp",
        name="tools/list",
        outcome=outcome,
        duration_ms=duration_ms,
        metadata=event_metadata,
        error=error,
        tool_count=tool_count,
    )
    instruments = _instruments()
    if instruments is None:
        return
    instruments.mcp_tool_listings.add(
        1,
        _metric_attrs(fields, outcome=outcome, error=error),
    )
