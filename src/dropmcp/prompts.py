"""Directory-scanning provider that registers MCP prompts from PROMPT.md files.

Each subdirectory under the prompts root containing a PROMPT.md file becomes
an MCP prompt. The PROMPT.md uses YAML frontmatter for metadata and the body
as the template text with {{arg}} placeholders.

If an `assets/` subdirectory exists, each file inside is exposed as an MCP
resource at `prompt://{prompt-name}/assets/{filename}`.
"""

from __future__ import annotations

import logging
import mimetypes
import re
from collections.abc import Sequence
from inspect import Parameter, Signature
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from fastmcp.prompts import Prompt
from fastmcp.resources import Resource
from fastmcp.server.providers import Provider

from dropmcp.subscriptions import item_visible_over_mcp, resolve_mcp_user
from dropmcp.telemetry import track

if TYPE_CHECKING:
    from dropmcp.config import Settings
    from dropmcp.subscriptions import UserSubscriptionStore

log = logging.getLogger(__name__)

MAIN_FILE = "PROMPT.md"
ASSETS_DIR = "assets"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_prompt_file(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(raw)
    if not match:
        raise ValueError(f"{path}: missing YAML frontmatter")
    meta = yaml.safe_load(match.group(1)) or {}
    body = raw[match.end():]
    return meta, body


def _build_prompt(meta: dict[str, Any], template: str) -> Prompt:
    name: str = meta["name"]
    description: str = meta.get("description", "")
    arg_defs: list[dict[str, Any]] = meta.get("arguments", [])

    params: list[Parameter] = []
    annotations: dict[str, type] = {}
    for arg in arg_defs:
        default = Parameter.empty if arg.get("required", False) else ""
        params.append(
            Parameter(
                arg["name"],
                kind=Parameter.POSITIONAL_OR_KEYWORD,
                default=default,
                annotation=str,
            )
        )
        annotations[arg["name"]] = str

    sig = Signature(params, return_annotation=str)

    def render(**kwargs: str) -> str:
        with track("prompt", name):
            text = template
            for key, value in kwargs.items():
                text = text.replace(f"{{{{{key}}}}}", value or "")
            return text

    render.__signature__ = sig  # type: ignore[attr-defined]
    render.__annotations__ = {**annotations, "return": str}
    render.__doc__ = description

    return Prompt.from_function(render, name=name, description=description)


def _collect_assets(prompt_name: str, assets_dir: Path) -> list[Resource]:
    resources: list[Resource] = []
    if not assets_dir.is_dir():
        return resources

    for asset in sorted(assets_dir.iterdir()):
        if not asset.is_file():
            continue
        uri = f"prompt://{prompt_name}/assets/{asset.name}"
        mime = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"

        file_path = asset

        def _read(path: Path = file_path, _uri: str = uri) -> str:
            with track("resource", _uri, resource_kind="prompt"):
                return path.read_text(encoding="utf-8")

        resources.append(
            Resource.from_function(
                _read,
                uri=uri,
                name=f"{prompt_name}/{asset.name}",
                description=f"Asset for prompt '{prompt_name}'",
                mime_type=mime,
            )
        )
    return resources


class PromptsDirectoryProvider(Provider):
    """Scans a directory for PROMPT.md files and exposes them as MCP prompts.

    If a prompt directory contains an `assets/` subdirectory, each file inside
    is exposed as an MCP resource at `prompt://{name}/assets/{filename}`.
    """

    def __init__(
        self,
        roots: Path | str,
        *,
        reload: bool = False,
        subscription_store: UserSubscriptionStore | None = None,
        subscription_settings: Settings | None = None,
    ) -> None:
        super().__init__()
        self._roots = Path(roots)
        self._reload = reload
        self._prompts: list[Prompt] | None = None
        self._resources: list[Resource] | None = None
        self._subscription_store = subscription_store
        self._subscription_settings = subscription_settings

    def _prompt_visible(self, name: str) -> bool:
        settings = self._subscription_settings
        if settings is None or self._subscription_store is None:
            return True
        user = resolve_mcp_user(settings)
        return item_visible_over_mcp(
            settings, self._subscription_store, user, "prompt", name
        )

    def _discover(self) -> tuple[list[Prompt], list[Resource]]:
        prompts: list[Prompt] = []
        resources: list[Resource] = []
        if not self._roots.is_dir():
            return prompts, resources

        for prompt_dir in sorted(self._roots.iterdir()):
            main_file = prompt_dir / MAIN_FILE
            if not main_file.is_file():
                continue
            try:
                meta, template = _parse_prompt_file(main_file)
                prompt = _build_prompt(meta, template)
                prompts.append(prompt)
                resources.extend(_collect_assets(meta["name"], prompt_dir / ASSETS_DIR))
            except Exception as exc:
                log.warning("Skipping %s: %s", prompt_dir.name, exc)
        return prompts, resources

    def _ensure_discovered(self) -> None:
        if self._reload or self._prompts is None:
            self._prompts, self._resources = self._discover()

    async def _list_prompts(self) -> Sequence[Prompt]:
        self._ensure_discovered()
        prompts = self._prompts or []
        return [p for p in prompts if self._prompt_visible(p.name)]

    async def _list_resources(self) -> Sequence[Resource]:
        self._ensure_discovered()
        resources = self._resources or []
        visible_names = {p.name for p in await self._list_prompts()}
        return [
            r
            for r in resources
            if any(str(r.uri).startswith(f"prompt://{name}/") for name in visible_names)
        ]
