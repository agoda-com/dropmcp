"""Opt-in shared agent memory: remember, recall and report, behind a flag."""

from __future__ import annotations

from fastmcp import FastMCP

from dropmcp.config import Settings
from dropmcp.memory.admin import register_admin_routes
from dropmcp.memory.provider import MemoryProvider
from dropmcp.memory.schema_check import check_memory_schema
from dropmcp.memory.store import MemoryStore
from dropmcp.memory.vocabulary import resolve_vocabulary


def register_memory(mcp: FastMCP, settings: Settings) -> None:
    if not settings.memory_enabled:
        return
    store = settings.memory_store or MemoryStore(settings.database_url)
    if settings.memory_store is None:
        check_memory_schema(store.engine)
    vocabulary = resolve_vocabulary(settings.memory_vocabulary)
    mcp.add_provider(MemoryProvider(store, settings, vocabulary))
    if settings.ui_enabled:
        register_admin_routes(mcp, store, settings)
