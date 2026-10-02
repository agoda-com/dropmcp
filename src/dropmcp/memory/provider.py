"""Registers the three shared memory tools."""

from __future__ import annotations

from fastmcp.server.providers import Provider

from dropmcp.config import Settings
from dropmcp.memory.recall import MemoryRecallTool
from dropmcp.memory.remember import MemoryRememberTool
from dropmcp.memory.report import MemoryReportTool
from dropmcp.memory.store import MemoryStore
from dropmcp.memory.vocabulary import Vocabulary


class MemoryProvider(Provider):
    """Exposes ``memory_remember``, ``memory_recall`` and ``memory_report``."""

    def __init__(
        self, store: MemoryStore, settings: Settings, vocabulary: Vocabulary
    ) -> None:
        super().__init__()
        tools = (
            MemoryRememberTool.create(store, settings, vocabulary),
            MemoryRecallTool.create(store, settings, vocabulary),
            MemoryReportTool.create(store, settings, vocabulary),
        )
        self._tools = {tool.name: tool for tool in tools}

    async def _list_tools(self):
        return list(self._tools.values())

    async def _get_tool(self, name, version=None):
        return self._tools.get(name)
