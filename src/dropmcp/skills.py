"""Filesystem-backed skills provider.

Each subdirectory under the skills root containing a `SKILL.md` becomes an
MCP tool whose body is the SKILL.md content and whose `ResourceLink`s point
at the skill's supporting files. The provider wraps FastMCP's built-in
`SkillsDirectoryProvider` to (a) hide framework plumbing from resource
listings and (b) use a more robust frontmatter `description` parser.
"""

from __future__ import annotations

import logging
import mimetypes
import re
from typing import TYPE_CHECKING, Any

import yaml
from fastmcp.resources.base import Resource
from fastmcp.server.providers.skills import SkillsDirectoryProvider
from fastmcp.server.providers.skills._common import SkillInfo
from fastmcp.server.providers.skills.skill_provider import SkillProvider
from fastmcp.tools.base import Tool, ToolResult
from mcp.types import ResourceLink, TextContent
from pydantic import AnyUrl, ConfigDict, PrivateAttr

from dropmcp.subscriptions import item_visible_over_mcp, resolve_mcp_user
from dropmcp.telemetry import track

if TYPE_CHECKING:
    from dropmcp.config import Settings
    from dropmcp.subscriptions import UserSubscriptionStore

logger = logging.getLogger(__name__)

_RESOURCE_LINK_EXCLUDED_EXTENSIONS = (".ttf", ".otf", ".woff", ".woff2")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class SkillTool(Tool):
    """Tool that returns SKILL.md content + ResourceLinks to supporting files."""

    skill_info: SkillInfo

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        with track("skill", self.skill_info.name):
            content = (self.skill_info.path / self.skill_info.main_file).read_text()
            result: list = [TextContent(type="text", text=content)]
            for f in self.skill_info.files:
                if f.path == self.skill_info.main_file or f.path.startswith("catalog/"):
                    continue
                if f.path.lower().endswith(_RESOURCE_LINK_EXCLUDED_EXTENSIONS):
                    continue
                mime, _ = mimetypes.guess_type(f.path)
                result.append(
                    ResourceLink(
                        type="resource_link",
                        name=f"{self.skill_info.name}/{f.path}",
                        uri=AnyUrl(f"skill://{self.skill_info.name}/{f.path}"),
                        mimeType=mime or "application/octet-stream",
                    )
                )
            return ToolResult(content=result)


_DESCRIPTION_RE = re.compile(
    r"^description:\s*(.+?)(?=^[A-Za-z_][A-Za-z0-9_-]*:|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _parse_description(info: SkillInfo) -> str:
    """Return the YAML frontmatter description.

    FastMCP's built-in parser splits frontmatter naively by line, which
    truncates multi-line `>-` blocks and confuses descriptions that
    contain colons. We try `yaml.safe_load` first so well-formed
    frontmatter round-trips faithfully, then fall back to a regex pull
    of the raw `description:` block, then to FastMCP's own value.

    The fallback is what gets exercised in practice: many skill
    descriptions inline phrases like "Trigger on: foo, bar" on a single
    line, and an unquoted `: ` inside a YAML scalar makes
    `yaml.safe_load` raise. Without the fallback the exception bubbles
    through `_list_tools`, FastMCP swallows it, and the server reports
    zero tools.
    """
    raw = (info.path / info.main_file).read_text()
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return info.description

    body = match.group(1)
    try:
        meta = yaml.safe_load(body) or {}
        if "description" in meta:
            return str(meta["description"])
    except yaml.YAMLError as e:
        logger.warning(
            "YAML parse failed for skill %s frontmatter (%s); "
            "falling back to regex description extraction",
            info.name,
            e.__class__.__name__,
        )

    desc_match = _DESCRIPTION_RE.search(body)
    if desc_match:
        text = desc_match.group(1).strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
            text = text[1:-1]
        return text

    return info.description


def _build_skill_tool(info: SkillInfo) -> SkillTool:
    return SkillTool(
        name=info.name,
        description=_parse_description(info),
        parameters={"type": "object", "properties": {}},
        skill_info=info,
    )


class TrackedResource(Resource):
    """Wraps any `Resource` so each read passes through the telemetry seam.

    The wrapper mirrors `uri`, `name`, `description`, and `mime_type` from
    the inner resource so MCP listings look identical, then delegates the
    actual `_read()` call. We hook `_read` (the framework entry point)
    rather than `read()` so background-task routing on the inner resource
    keeps working.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    track_name: str
    track_kind: str = "resource"

    _inner: Resource = PrivateAttr()

    @classmethod
    def wrap(
        cls, inner: Resource, *, track_name: str, track_kind: str = "resource"
    ) -> "TrackedResource":
        wrapper = cls(
            uri=inner.uri,
            name=inner.name,
            description=inner.description,
            mime_type=inner.mime_type,
            track_name=track_name,
            track_kind=track_kind,
        )
        wrapper._inner = inner
        return wrapper

    async def read(self):
        return await self._inner.read()

    async def _read(self, task_meta=None):
        with track(
            "resource", self.track_name, resource_kind=self.track_kind
        ):
            return await self._inner._read(task_meta=task_meta)


class FilteredSkillsProvider(SkillsDirectoryProvider):
    """Hide implementation-detail entries from MCP `list_resources`.

    With `supporting_files="resources"`, the base provider exposes three
    URI shapes per skill:

      * `skill://<name>/SKILL.md`     — main instruction file
      * `skill://<name>/_manifest`    — auto-generated JSON file listing
      * `skill://<name>/<path>`       — supporting files

    We surface each skill as an MCP tool (`SkillTool`) whose body is the
    SKILL.md content and whose `ResourceLink`s point at the supporting
    files. Listing the main file and `_manifest` as standalone resources
    just clutters MCP clients with duplicates of the tool body and
    FastMCP plumbing, so we hide them from discovery. They stay readable
    by URI, which keeps `ResourceLink` resolution working.

    `catalog/` files are SPA assets served via HTTP; they are never part
    of the agent-facing skill surface.
    """

    _HIDDEN_SUFFIXES = ("/SKILL.md", "/_manifest")

    def __init__(
        self,
        roots,
        *,
        supporting_files: str = "resources",
        reload: bool = False,
        subscription_store: UserSubscriptionStore | None = None,
        subscription_settings: Settings | None = None,
    ) -> None:
        super().__init__(roots, supporting_files=supporting_files, reload=reload)
        self._subscription_store = subscription_store
        self._subscription_settings = subscription_settings

    def _skill_visible(self, name: str) -> bool:
        settings = self._subscription_settings
        if settings is None or self._subscription_store is None:
            return True
        user = resolve_mcp_user(settings)
        return item_visible_over_mcp(
            settings, self._subscription_store, user, "skill", name
        )

    async def _list_resources(self):
        resources = await super()._list_resources()
        return [r for r in resources if self._is_visible(str(r.uri))]

    async def _get_resource(self, uri: str, version=None):
        resource = await super()._get_resource(uri, version)
        if resource is None:
            return None
        return TrackedResource.wrap(resource, track_name=str(uri), track_kind="skill")

    @classmethod
    def _is_visible(cls, uri: str) -> bool:
        if "/catalog/" in uri:
            return False
        return not uri.endswith(cls._HIDDEN_SUFFIXES)

    async def _list_tools(self):
        await self._ensure_discovered()
        tools: list[SkillTool] = []
        for p in self.providers:
            if not isinstance(p, SkillProvider):
                continue
            if not self._skill_visible(p.skill_info.name):
                continue
            try:
                tools.append(_build_skill_tool(p.skill_info))
            except Exception:
                logger.exception(
                    "Failed to build tool for skill %s; "
                    "skipping so other skills still surface",
                    p.skill_info.name,
                )
        return tools

    async def _get_tool(self, name, version=None):
        if not self._skill_visible(name):
            return None
        await self._ensure_discovered()
        for p in self.providers:
            if isinstance(p, SkillProvider) and p.skill_info.name == name:
                return _build_skill_tool(p.skill_info)
        return None
