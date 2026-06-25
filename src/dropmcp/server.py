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
from dropmcp.eval_results import EvalResultsStore, result_view_model, resolve_starrocks_store
from dropmcp.feedback import FeedbackProvider, FeedbackStore, feedback_to_dict
from dropmcp.identity import user_from_request
from dropmcp.instructions import build_server_instructions
from dropmcp.middleware import TelemetryMiddleware
from dropmcp.prompts import PromptsDirectoryProvider
from dropmcp.skills import FilteredSkillsProvider
from dropmcp.subscriptions import (
    ITEM_TYPES,
    SubscriptionCoordinator,
    UserSubscriptionStore,
    group_subscription_to_dict,
    subscription_to_dict,
)
from dropmcp.telemetry import configure

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


def _entry_to_dict(entry, *, subscribed: bool | None = None) -> dict:
    prefix = f"/catalog/{entry.type}/{entry.name}"
    payload = {
        "name": entry.name,
        "type": entry.type,
        "category": entry.category,
        "group": entry.group,
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
    if subscribed is not None:
        payload["subscribed"] = subscribed
    return payload


def _file_response(path: Path) -> FileResponse:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=mime)


def _resolve_eval_results_store(settings: Settings) -> EvalResultsStore | None:
    if settings.eval_results_store is not None:
        return settings.eval_results_store
    if settings.eval_results_project:
        return resolve_starrocks_store()
    return None


def build_server(settings: Settings) -> FastMCP:
    configure(service_name=settings.name)

    instructions = build_server_instructions(
        settings.instructions_path,
        settings.skills_dir,
        settings.prompts_dir,
        feedback_enabled=settings.feedback_enabled,
    )

    mcp = FastMCP(
        settings.name,
        instructions=instructions,
        website_url=settings.website_url,
        icons=_build_icons(settings),
    )

    mcp.add_middleware(TelemetryMiddleware())

    subscription_store = (
        UserSubscriptionStore(settings.database_url)
        if settings.user_subscriptions_enabled
        else None
    )
    subscription_coordinator: SubscriptionCoordinator | None = None
    if subscription_store is not None:
        subscription_catalog = CatalogProvider(
            skills_dir=settings.skills_dir,
            prompts_dir=settings.prompts_dir,
            defaults_dir=settings.catalog_defaults_dir,
            reload=settings.reload,
        )

        def _subscription_groups() -> list[str]:
            return sorted(
                {e.group for e in subscription_catalog.get_entries() if e.group}
            )

        subscription_coordinator = SubscriptionCoordinator(
            subscription_store,
            settings,
            _subscription_groups,
        )

    mcp.add_provider(
        FilteredSkillsProvider(
            roots=settings.skills_dir,
            supporting_files=SUPPORTING_FILES,
            reload=settings.reload,
            subscription_store=subscription_store,
            subscription_settings=settings,
            subscription_coordinator=subscription_coordinator,
        )
    )
    mcp.add_provider(
        PromptsDirectoryProvider(
            roots=settings.prompts_dir,
            reload=settings.reload,
            subscription_store=subscription_store,
            subscription_settings=settings,
            subscription_coordinator=subscription_coordinator,
        )
    )

    feedback_store = (
        FeedbackStore(settings.database_url) if settings.feedback_enabled else None
    )
    if feedback_store is not None:
        mcp.add_provider(FeedbackProvider(feedback_store))

    if settings.ui_enabled:
        eval_store = _resolve_eval_results_store(settings)
        _register_catalog_routes(
            mcp,
            settings,
            feedback_store,
            eval_store,
            subscription_store,
            subscription_coordinator,
        )
    elif subscription_store is not None and settings.user_subscriptions_enabled:
        subscription_catalog = CatalogProvider(
            skills_dir=settings.skills_dir,
            prompts_dir=settings.prompts_dir,
            defaults_dir=settings.catalog_defaults_dir,
            reload=settings.reload,
        )
        _register_subscription_routes(
            mcp,
            settings,
            subscription_store,
            subscription_catalog,
            subscription_coordinator,
        )

    return mcp


def _register_catalog_routes(
    mcp: FastMCP,
    settings: Settings,
    feedback_store: FeedbackStore | None,
    eval_store: EvalResultsStore | None,
    subscription_store: UserSubscriptionStore | None,
    subscription_coordinator: SubscriptionCoordinator | None,
) -> None:
    defaults_dir = settings.catalog_defaults_dir
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
        payload: dict[str, str] = {"status": "healthy"}
        if settings.eval_results_commit_sha:
            payload["commit_sha"] = settings.eval_results_commit_sha
        return JSONResponse(payload)

    @mcp.custom_route("/favicon.svg", methods=["GET"])
    @mcp.custom_route("/favicon.ico", methods=["GET"])
    @mcp.custom_route("/icon.svg", methods=["GET"])
    async def favicon(request: Request) -> FileResponse:
        return _file_response(settings.icon)

    @mcp.custom_route("/catalog", methods=["GET"])
    async def catalog_index(request: Request) -> JSONResponse:
        user = None
        subscribed_groups: list[str] = []
        if settings.user_subscriptions_enabled and subscription_coordinator is not None:
            user = subscription_coordinator.http_user(request)

        available_groups = sorted(
            {e.group for e in catalog.get_entries() if e.group}
        )

        items = []
        for entry in catalog.get_entries():
            subscribed = None
            if user is not None and subscription_store is not None:
                subscribed = subscription_store.is_visible(
                    user, entry.type, entry.name, group=entry.group
                )
            items.append(_entry_to_dict(entry, subscribed=subscribed))

        if user is not None and subscription_store is not None:
            subscribed_groups = sorted(subscription_store.subscribed_groups(user))

        payload = {
            "items": items,
            "server": _catalog_server_payload(settings),
            "subscriptions_enabled": settings.user_subscriptions_enabled,
            "user": user,
            "subscribed_groups": subscribed_groups,
            "available_groups": available_groups,
        }
        return JSONResponse(payload)

    @mcp.custom_route("/catalog/{item_type}/{name}", methods=["GET"])
    async def catalog_detail(request: Request) -> JSONResponse:
        entry = catalog.get_entry(
            request.path_params["item_type"], request.path_params["name"]
        )
        if entry is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        user = None
        if settings.user_subscriptions_enabled and subscription_coordinator is not None:
            user = subscription_coordinator.http_user(request)
        elif settings.user_subscriptions_enabled:
            user = user_from_request(request, settings.user_header)
        subscribed = None
        if (
            user is not None
            and subscription_store is not None
            and settings.user_subscriptions_enabled
        ):
            subscribed = subscription_store.is_visible(
                user, entry.type, entry.name, group=entry.group
            )
        return JSONResponse(_entry_to_dict(entry, subscribed=subscribed))

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

    if feedback_store is not None:
        _register_feedback_routes(mcp, feedback_store)

    if subscription_store is not None and settings.user_subscriptions_enabled:
        _register_subscription_routes(
            mcp,
            settings,
            subscription_store,
            catalog,
            subscription_coordinator,
        )

    if eval_store is not None and settings.eval_results_project:
        _register_eval_results_routes(mcp, settings, eval_store)

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


def _register_subscription_routes(
    mcp: FastMCP,
    settings: Settings,
    store: UserSubscriptionStore,
    catalog: CatalogProvider,
    coordinator: SubscriptionCoordinator | None,
) -> None:
    def _require_user(request: Request) -> str | JSONResponse:
        user = (
            coordinator.http_user(request)
            if coordinator is not None
            else user_from_request(request, settings.user_header)
        )
        if user is None:
            return JSONResponse(
                {"error": "identity header required"},
                status_code=401,
            )
        return user

    def _group_members(group: str) -> list[tuple[str, str]]:
        return [
            (e.type, e.name)
            for e in catalog.get_entries()
            if e.group == group
        ]

    def _all_groups() -> list[str]:
        return sorted({e.group for e in catalog.get_entries() if e.group})

    @mcp.custom_route("/api/subscriptions", methods=["GET"])
    async def subscriptions_list(request: Request) -> JSONResponse:
        user = _require_user(request)
        if isinstance(user, JSONResponse):
            return user
        items = store.list_for_user(user)
        groups = store.list_groups_for_user(user)
        return JSONResponse(
            {
                "items": [subscription_to_dict(item) for item in items],
                "groups": [group_subscription_to_dict(g) for g in groups],
            }
        )

    @mcp.custom_route("/api/subscriptions", methods=["POST"])
    async def subscriptions_add(request: Request) -> JSONResponse:
        user = _require_user(request)
        if isinstance(user, JSONResponse):
            return user
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid json"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "invalid body"}, status_code=400)

        item_type = body.get("item_type")
        item_name = body.get("item_name")
        if item_type not in ITEM_TYPES or not item_name:
            return JSONResponse({"error": "invalid item"}, status_code=400)

        entry = catalog.get_entry(item_type, str(item_name))
        if entry is None:
            return JSONResponse({"error": "not found"}, status_code=404)

        store.add_item(user, item_type, str(item_name))
        return JSONResponse({"status": "subscribed"})

    @mcp.custom_route("/api/subscriptions/groups", methods=["POST"])
    async def subscriptions_add_all_groups(request: Request) -> JSONResponse:
        user = _require_user(request)
        if isinstance(user, JSONResponse):
            return user
        groups = _all_groups()
        if not groups:
            return JSONResponse({"error": "no groups available"}, status_code=404)
        count = store.add_groups(user, groups)
        for group in groups:
            members = _group_members(group)
            store.clear_group_exclusions(user, members)
        return JSONResponse({"status": "subscribed", "count": count})

    @mcp.custom_route(
        "/api/subscriptions/group/{group}", methods=["POST"]
    )
    async def subscriptions_add_group(request: Request) -> JSONResponse:
        user = _require_user(request)
        if isinstance(user, JSONResponse):
            return user
        group = request.path_params["group"]
        members = _group_members(group)
        if not members:
            return JSONResponse({"error": "group not found"}, status_code=404)
        store.add_group(user, group)
        store.clear_group_exclusions(user, members)
        return JSONResponse({"status": "subscribed", "count": len(members)})

    @mcp.custom_route(
        "/api/subscriptions/group/{group}", methods=["DELETE"]
    )
    async def subscriptions_remove_group(request: Request) -> JSONResponse:
        user = _require_user(request)
        if isinstance(user, JSONResponse):
            return user
        group = request.path_params["group"]
        members = _group_members(group)
        if not members:
            return JSONResponse({"error": "group not found"}, status_code=404)
        store.remove_group(user, group)
        store.clear_group_exclusions(user, members)
        return JSONResponse({"status": "unsubscribed", "count": len(members)})

    @mcp.custom_route(
        "/api/subscriptions/{item_type}/{item_name}", methods=["DELETE"]
    )
    async def subscriptions_remove(request: Request) -> JSONResponse:
        user = _require_user(request)
        if isinstance(user, JSONResponse):
            return user
        item_type = request.path_params["item_type"]
        item_name = request.path_params["item_name"]
        if item_type not in ITEM_TYPES:
            return JSONResponse({"error": "invalid item type"}, status_code=400)
        entry = catalog.get_entry(item_type, item_name)
        group = entry.group if entry is not None else None
        store.remove_item(user, item_type, item_name, group=group)
        return JSONResponse({"status": "unsubscribed"})


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


def _register_eval_results_routes(
    mcp: FastMCP, settings: Settings, store: EvalResultsStore
) -> None:
    project = settings.eval_results_project or ""
    commit_sha = settings.eval_results_commit_sha or "unknown"

    @mcp.custom_route("/api/telemetry", methods=["GET"])
    async def telemetry_all(request: Request) -> JSONResponse:
        results = store.get_all_latest_results(project, commit_sha)
        return JSONResponse(
            {
                "project": project,
                "commit_sha": commit_sha,
                "results": {
                    name: [
                        {"test_name": r.test_name, **result_view_model(r)}
                        for r in rs
                    ]
                    for name, rs in results.items()
                },
            }
        )

    @mcp.custom_route("/api/telemetry/{skill_name}", methods=["GET"])
    async def telemetry_skill(request: Request) -> JSONResponse:
        skill_name = request.path_params.get("skill_name", "")
        results = store.get_results_for_skill(project, skill_name, commit_sha)
        return JSONResponse(
            {
                "project": project,
                "skill_name": skill_name,
                "commit_sha": commit_sha,
                "results": [
                    {"test_name": r.test_name, **result_view_model(r)} for r in results
                ],
            }
        )
