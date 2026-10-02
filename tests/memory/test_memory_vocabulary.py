"""S9: host vocabulary files, stack-tag logging and D6 recall tolerance."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import pytest
from sqlalchemy import insert

import dropmcp.memory.vocabulary as vocabulary_module
from dropmcp.memory.store import memory_table
from dropmcp.memory.vocabulary import DEFAULT_VOCABULARY, resolve_vocabulary

_KEY_IN_TEXT = re.compile(r"\[(MEM-[A-Z0-9]{6})\]")


async def _language_enum(mem) -> list[str]:
    tools = await mem.client.list_tools()
    remember = next(tool for tool in tools if tool.name == "memory_remember")
    return remember.inputSchema["properties"]["context"]["properties"]["language"][
        "enum"
    ]


async def _remember_language(mem, language: str) -> str:
    text = await mem.remember(
        context={"language": language},
        kind="gotcha",
        title="Custom vocabulary language check",
        body="Stored under a host-defined language list.",
    )
    match = _KEY_IN_TEXT.search(text)
    assert match is not None, text
    return match.group(1)


@pytest.mark.parametrize("suffix", [".yaml", ".json"])
async def test_vocabulary_file_replaces_languages_in_tool_schema(
    memory_server, tmp_path, suffix
):
    vocab_path = tmp_path / f"vocab{suffix}"
    if suffix == ".yaml":
        vocab_path.write_text(
            "languages:\n  - zig\n  - nim\n",
            encoding="utf-8",
        )
    else:
        vocab_path.write_text(
            '{"languages": ["zig", "nim"]}',
            encoding="utf-8",
        )

    async with memory_server(memory_vocabulary=vocab_path) as mem:
        assert await _language_enum(mem) == ["zig", "nim"]

        key = await _remember_language(mem, "zig")
        row = mem.sql("SELECT language FROM memory WHERE key = :key", key=key)[0]
        assert row["language"] == "zig"

        refused = await mem.remember(
            context={"language": "csharp"},
            kind="gotcha",
            title="Should not store",
            body="csharp is not in the host vocabulary.",
        )
        assert "Memory not stored:" in refused
        assert "csharp" in refused


async def test_vocabulary_file_with_only_stack_keeps_default_languages(
    memory_server, tmp_path
):
    vocab_path = tmp_path / "stack-only.yaml"
    vocab_path.write_text("stack:\n  - bespoke-framework\n", encoding="utf-8")

    async with memory_server(memory_vocabulary=vocab_path) as mem:
        assert await _language_enum(mem) == list(DEFAULT_VOCABULARY.languages)


async def test_unknown_stack_tag_is_stored_and_logged(
    memory_server, tmp_path, caplog, backend
):
    vocabulary_module._logged_unknown_stack_tags.clear()
    tag = f"mystery-stack-{backend}"
    vocab_path = tmp_path / "vocab.yaml"
    vocab_path.write_text("stack:\n  - react\n", encoding="utf-8")

    async with memory_server(memory_vocabulary=vocab_path) as mem:
        with caplog.at_level(logging.INFO, logger="dropmcp.memory.vocabulary"):
            text = await mem.remember(
                context={"language": "python", "stack": [tag]},
                kind="gotcha",
                title="Unknown stack tag",
                body="Tag is not in the vocabulary file.",
            )
        assert _KEY_IN_TEXT.search(text) is not None, text
        key = _KEY_IN_TEXT.search(text).group(1)
        row = mem.sql("SELECT stack FROM memory WHERE key = :key", key=key)[0]
        stack = row["stack"]
        if isinstance(stack, str):
            stack = json.loads(stack)
        assert stack == [tag]
        assert any(
            record.message == f"Unknown memory stack tag: {tag}"
            for record in caplog.records
        )


async def test_recall_returns_memory_with_language_not_in_current_vocabulary(
    memory_server, tmp_path
):
    vocab_path = tmp_path / "vocab.yaml"
    vocab_path.write_text("languages:\n  - zig\n", encoding="utf-8")
    now = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)
    legacy_key = "MEM-LEGACY"

    async with memory_server(memory_vocabulary=vocab_path) as mem:
        mem.sql(
            insert(memory_table).values(
                id="legacy-memory-id",
                key=legacy_key,
                created_at=now,
                created_by="agent@example.com",
                server=mem.settings.name,
                last_confirmed_at=now,
                kind="gotcha",
                title="Legacy language recall token",
                body="Inserted with a language outside the current vocabulary.",
                language="legacylang",
                stack=[],
                fingerprint="f" * 64,
                occurrence_count=1,
                model="test-model",
            )
        )

        text = await mem.recall()
        assert legacy_key in text


def test_resolve_vocabulary_rejects_bad_extension(tmp_path):
    path = tmp_path / "vocab.txt"
    path.write_text("languages: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="extension '.txt'"):
        resolve_vocabulary(path)


def test_resolve_vocabulary_rejects_missing_file(tmp_path):
    path = tmp_path / "missing.yaml"
    with pytest.raises(ValueError, match=f"not found: {path}"):
        resolve_vocabulary(path)


def test_resolve_vocabulary_rejects_non_list_value(tmp_path):
    path = tmp_path / "vocab.yaml"
    path.write_text("languages: zig\n", encoding="utf-8")
    with pytest.raises(ValueError, match=f"{path}") as exc:
        resolve_vocabulary(path)
    assert "languages" in str(exc.value)


async def test_dropmcp_memory_vocabulary_env_var(
    memory_server, tmp_path, monkeypatch
):
    vocab_path = tmp_path / "env-vocab.json"
    vocab_path.write_text('{"languages": ["gleam"]}', encoding="utf-8")
    monkeypatch.setenv("DROPMCP_MEMORY_VOCABULARY", str(vocab_path))

    async with memory_server() as mem:
        assert await _language_enum(mem) == ["gleam"]
