"""FastMCP middleware for protocol-level telemetry.

Skill, prompt, and resource tracking live in the providers via
:func:`dropmcp.telemetry.track`. This module covers events that only
surface at the protocol layer: the ``initialize`` handshake (how clients
receive server instructions) and ``tools/list`` (whether clients see the
latest skill catalog).
"""

from __future__ import annotations

import time

from fastmcp.server.middleware import Middleware, MiddlewareContext

from dropmcp.telemetry import (
    record_mcp_initialization,
    record_tool_listing,
)


class TelemetryMiddleware(Middleware):
    """Records counters and structured logs for MCP protocol events."""

    async def on_initialize(self, context: MiddlewareContext, call_next):
        start = time.perf_counter()
        outcome = "success"
        error: BaseException | None = None
        try:
            return await call_next(context)
        except Exception as exc:
            outcome = "error"
            error = exc
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            record_mcp_initialization(
                outcome=outcome,
                duration_ms=duration_ms,
                context=context,
                error=error,
            )

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        start = time.perf_counter()
        outcome = "success"
        tool_count: int | None = None
        error: BaseException | None = None
        try:
            tools = await call_next(context)
            try:
                tool_count = len(tools) if tools is not None else 0
            except TypeError:
                tool_count = None
            return tools
        except Exception as exc:
            outcome = "error"
            error = exc
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            record_tool_listing(
                outcome=outcome,
                duration_ms=duration_ms,
                tool_count=tool_count,
                context=context,
                error=error,
            )
