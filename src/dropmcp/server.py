"""Build a FastMCP server from a `Settings` object.

Wires the skills + prompts providers, the aggregated instructions, and the
always-on catalog HTTP API plus the browseable React SPA shipped in the wheel.
Everything funnels through `build_server`, which the public
`create_server` / `run` API calls.
"""

from __future__ import annotations

import base64
import mimetypes
from importlib import resources
from pathlib import Path

from fastmcp import FastMCP
from mcp.types import Icon
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse

from dropmcp.catalog import CatalogProvider
from dropmcp.config import Settings
from dropmcp.feedback import FeedbackProvider, FeedbackStore, feedback_to_dict
from dropmcp.instructions import build_server_instructions
from dropmcp.prompts import PromptsDirectoryProvider
from dropmcp.skills import FilteredSkillsProvider

SUPPORTING_FILES = "resources"


def _package_static_dir() -> Path:
    return Path(resources.files("dropmcp") / "static")


def _build_icons(settings: Settings) -> list[Icon]:
    if not settings.icon.is_file():
        return []
    mime = mimetypes.guess_type(settings.icon.name)[0] or "image/svg+xml"
    data = base64.b64encode(settings.icon.read_bytes()).decode("ascii")
    return [Icon(src=f"data:{mime};base64,{data}", mimeType=mime, sizes=["any"])]


def _catalog_server_payload(settings: Settings) -> dict:
    return {
        "name": settings.name,
        "website_url": settings.website_url,
        "icon_url": "/icon.svg",
    }


def _entry_to_dict(entry) -> dict:
    prefix = f"/catalog/{entry.type}/{entry.name}"
    return {
        "name": entry.name,
        "type": entry.type,
        "category": entry.category,
        "description": entry.description,
        "arguments": entry.arguments,
        "has_hero": entry.has_hero,
        "has_thumbnail": entry.has_thumbnail,
        "screenshot_count": len(entry.screenshot_filenames),
        "example_count": len(entry.example_filenames),
        "thumbnail_url": f"{prefix}/thumbnail",
        "hero_url": f"{prefix}/hero" if entry.has_hero else None,
        "screenshots": [
            f"{prefix}/screenshots/{f}" for f in entry.screenshot_filenames
        ],
        "examples": [f"{prefix}/examples/{f}" for f in entry.example_filenames],
    }


def _file_response(path: Path) -> FileResponse:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=mime)


def build_server(settings: Settings) -> FastMCP:
    instructions = build_server_instructions(
        settings.instructions_path,
        settings.skills_dir,
        settings.prompts_dir,
    )

    mcp = FastMCP(
        settings.name,
        instructions=instructions,
        website_url=settings.website_url,
        icons=_build_icons(settings),
    )

    mcp.add_provider(
        FilteredSkillsProvider(
            roots=settings.skills_dir,
            supporting_files=SUPPORTING_FILES,
            reload=settings.reload,
        )
    )
    mcp.add_provider(
        PromptsDirectoryProvider(
            roots=settings.prompts_dir,
            reload=settings.reload,
        )
    )

    feedback_store = FeedbackStore(settings.database_url)
    mcp.add_provider(FeedbackProvider(feedback_store))

    if settings.ui_enabled:
        _register_catalog_routes(mcp, settings, feedback_store)

    return mcp


def _register_catalog_routes(
    mcp: FastMCP, settings: Settings, feedback_store: FeedbackStore
) -> None:
    defaults_dir = settings.catalog_defaults_dir or (settings.skills_dir.parent / "_none")
    catalog = CatalogProvider(
        skills_dir=settings.skills_dir,
        prompts_dir=settings.prompts_dir,
        defaults_dir=defaults_dir,
        reload=settings.reload,
    )
    dist_dir = _package_static_dir() / "dist"
    spa_index: str | None = None

    def get_spa_html() -> str:
        nonlocal spa_index
        if spa_index is None or settings.reload:
            index = dist_dir / "index.html"
            if index.is_file():
                spa_index = index.read_text(encoding="utf-8")
            else:
                rows = "".join(
                    f"<li><strong>{e.type}</strong>: {e.name} — {e.description}</li>"
                    for e in catalog.get_entries()
                )
                spa_index = (
                    f"<!doctype html><html><head><meta charset='utf-8'>"
                    f"<title>{settings.name}</title></head><body>"
                    f"<h1>{settings.name}</h1>"
                    f"<p>Catalog API: <a href='/catalog'>/catalog</a></p>"
                    f"<ul>{rows or '<li>No skills or prompts found.</li>'}</ul>"
                    f"</body></html>"
                )
        return spa_index

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    @mcp.custom_route("/favicon.svg", methods=["GET"])
    @mcp.custom_route("/favicon.ico", methods=["GET"])
    @mcp.custom_route("/icon.svg", methods=["GET"])
    async def favicon(request: Request) -> FileResponse:
        return _file_response(settings.icon)

    @mcp.custom_route("/catalog", methods=["GET"])
    async def catalog_index(request: Request) -> JSONResponse:
        items = [_entry_to_dict(e) for e in catalog.get_entries()]
        return JSONResponse(
            {"items": items, "server": _catalog_server_payload(settings)}
        )

    @mcp.custom_route("/catalog/{item_type}/{name}", methods=["GET"])
    async def catalog_detail(request: Request) -> JSONResponse:
        entry = catalog.get_entry(
            request.path_params["item_type"], request.path_params["name"]
        )
        if entry is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse(_entry_to_dict(entry))

    @mcp.custom_route("/catalog/{item_type}/{name}/hero", methods=["GET"])
    async def catalog_hero(request: Request) -> FileResponse | JSONResponse:
        path = catalog.resolve_image_path(
            request.path_params["item_type"], request.path_params["name"], "hero"
        )
        if path is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return _file_response(path)

    @mcp.custom_route("/catalog/{item_type}/{name}/thumbnail", methods=["GET"])
    async def catalog_thumbnail(request: Request) -> FileResponse | JSONResponse:
        path = catalog.resolve_thumbnail_path(
            request.path_params["item_type"], request.path_params["name"]
        )
        if path is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return _file_response(path)

    @mcp.custom_route(
        "/catalog/{item_type}/{name}/screenshots/{filename}", methods=["GET"]
    )
    async def catalog_screenshot(request: Request) -> FileResponse | JSONResponse:
        path = catalog.resolve_image_path(
            request.path_params["item_type"],
            request.path_params["name"],
            "screenshot",
            request.path_params["filename"],
        )
        if path is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return _file_response(path)

    @mcp.custom_route(
        "/catalog/{item_type}/{name}/examples/{filename}", methods=["GET"]
    )
    async def catalog_example(request: Request) -> FileResponse | JSONResponse:
        path = catalog.resolve_example_path(
            request.path_params["item_type"],
            request.path_params["name"],
            request.path_params["filename"],
        )
        if path is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return _file_response(path)

    _register_feedback_routes(mcp, feedback_store)

    @mcp.custom_route("/", methods=["GET"])
    async def catalog_ui(request: Request) -> HTMLResponse:
        return HTMLResponse(get_spa_html())

    @mcp.custom_route("/{path:path}", methods=["GET"])
    async def spa_fallback(request: Request) -> HTMLResponse | FileResponse:
        rel = request.path_params.get("path", "")
        candidate = dist_dir / rel
        if candidate.is_file() and dist_dir in candidate.resolve().parents:
            return _file_response(candidate)
        return HTMLResponse(get_spa_html())


def _register_feedback_routes(mcp: FastMCP, store: FeedbackStore) -> None:
    @mcp.custom_route("/api/feedback", methods=["GET"])
    async def feedback_list(request: Request) -> JSONResponse:
        params = request.query_params
        items = store.list(
            search=params.get("search"),
            model=params.get("model"),
            client=params.get("client"),
            skill_name=params.get("skill_name"),
            status=params.get("status"),
        )
        return JSONResponse({"items": [feedback_to_dict(item) for item in items]})

    @mcp.custom_route("/api/feedback/{entry_id}", methods=["PATCH"])
    async def feedback_patch(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid json"}, status_code=400)

        if not isinstance(body, dict):
            return JSONResponse({"error": "invalid body"}, status_code=400)

        status = body.get("status")
        resolution_url = body.get("resolution_url")
        if status is None and resolution_url is None:
            return JSONResponse({"error": "nothing to update"}, status_code=400)

        try:
            updated = store.patch(
                request.path_params["entry_id"],
                status=status,
                resolution_url=resolution_url,
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        if updated is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse(feedback_to_dict(updated))
