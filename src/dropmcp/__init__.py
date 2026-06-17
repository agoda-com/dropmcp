"""dropmcp — drop a skills/ and prompts/ folder, get a FastMCP server.

Quick start::

    import dropmcp
    dropmcp.run(skills="skills", prompts="prompts")

Or grab the server to add your own routes/middleware first::

    mcp = dropmcp.create_server(skills="skills", prompts="prompts")
    # ... customise ...
    mcp.run(transport="stdio")
"""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from dropmcp.config import Settings
from dropmcp.server import build_server

__all__ = ["create_server", "run", "Settings"]

__version__ = "0.1.0"

# FastMCP's transport name for hosted HTTP; we accept the friendly "http" alias.
_HTTP_TRANSPORT = "streamable-http"


def create_server(
    *,
    skills: str | Path | None = None,
    prompts: str | Path | None = None,
    catalog_defaults: str | Path | None = None,
    instructions: str | Path | None = None,
    name: str | None = None,
    website_url: str | None = None,
    icon: str | Path | None = None,
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
    ui_enabled: bool | None = None,
    reload: bool | None = None,
) -> FastMCP:
    """Build and return a configured `FastMCP` server without running it.

    Use this when you want to attach custom routes or middleware before
    serving. Settings are resolved from these kwargs, then `DROPMCP_*`
    environment variables, then defaults.
    """
    settings = Settings.resolve(
        skills=skills,
        prompts=prompts,
        catalog_defaults=catalog_defaults,
        instructions=instructions,
        name=name,
        website_url=website_url,
        icon=icon,
        transport=transport,
        host=host,
        port=port,
        ui_enabled=ui_enabled,
        reload=reload,
    )
    return build_server(settings)


def run(
    *,
    skills: str | Path | None = None,
    prompts: str | Path | None = None,
    catalog_defaults: str | Path | None = None,
    instructions: str | Path | None = None,
    name: str | None = None,
    website_url: str | None = None,
    icon: str | Path | None = None,
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
    ui_enabled: bool | None = None,
    reload: bool | None = None,
) -> None:
    """Build the server and serve it over the configured transport.

    `transport` accepts ``"stdio"`` (default, for local Cursor/Claude
    Desktop) or ``"http"`` / ``"streamable-http"`` (for hosted use).
    """
    settings = Settings.resolve(
        skills=skills,
        prompts=prompts,
        catalog_defaults=catalog_defaults,
        instructions=instructions,
        name=name,
        website_url=website_url,
        icon=icon,
        transport=transport,
        host=host,
        port=port,
        ui_enabled=ui_enabled,
        reload=reload,
    )
    mcp = build_server(settings)

    if settings.transport in ("http", _HTTP_TRANSPORT):
        mcp.run(
            transport=_HTTP_TRANSPORT,
            host=settings.host,
            port=settings.port,
            stateless_http=True,
        )
    else:
        mcp.run(transport=settings.transport)
