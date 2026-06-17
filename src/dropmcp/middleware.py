"""FastMCP middleware for protocol-level telemetry.

Skill, prompt, and resource tracking live in the providers via
:func:`dropmcp.telemetry.track`. This module covers events that only
surface at the protocol layer: the ``initialize`` handshake (how clients
receive server instructions) and ``tools/list`` (whether clients see the
latest skill catalog).
"""

from __future__ import annotations

import time
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from dropmcp.telemetry import (
    client_bucket,
    record_mcp_initialization,
    record_tool_listing,
)


def _client_info(context: MiddlewareContext) -> dict[str, Any]:
    """Best-effort extract of ``clientInfo`` from an InitializeRequest."""
    info: dict[str, Any] = {}
    try:
        params = getattr(context.message, "params", None)
        client_info = None
        if params is not None:
            client_info = getattr(params, "clientInfo", None)
            if client_info is None and isinstance(params, dict):
                client_info = params.get("clientInfo")
        if client_info is None:
            return info

        name = getattr(client_info, "name", None)
        version = getattr(client_info, "version", None)
        if name is None and isinstance(client_info, dict):
            name = client_info.get("name")
            version = client_info.get("version")
        if name:
            info["client_name"] = name
        if version:
            info["client_version"] = version
    except Exception:
        return info
    return info


class TelemetryMiddleware(Middleware):
    """Records counters and structured logs for MCP protocol events."""

    async def on_initialize(self, context: MiddlewareContext, call_next):
        attrs_client = client_bucket()
        info = _client_info(context)
        client = info.get("client_name", attrs_client)

        start = time.perf_counter()
        outcome = "success"
        try:
            return await call_next(context)
        except Exception:
            outcome = "error"
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            record_mcp_initialization(
                outcome=outcome,
                duration_ms=duration_ms,
                client=client,
                **info,
            )

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        start = time.perf_counter()
        outcome = "success"
        tool_count: int | None = None
        client = client_bucket()
        try:
            tools = await call_next(context)
            try:
                tool_count = len(tools) if tools is not None else 0
            except TypeError:
                tool_count = None
            return tools
        except Exception:
            outcome = "error"
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            record_tool_listing(
                outcome=outcome,
                duration_ms=duration_ms,
                client=client,
                tool_count=tool_count,
            )
