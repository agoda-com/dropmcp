"""S6: exact duplicates, ``same_as``, ``supersedes`` and near-duplicates on write."""

from __future__ import annotations

import re

from fakes import FakeEmbedder

REPO = "example-org/payments-api"
OTHER_REPO = "example-org/billing-api"
KEY_RE = re.compile(r"MEM-[A-Z0-9]{6}")

ORIGINAL = {
    "kind": "gotcha",
    "title": "Tests fail locally with a startup error",
    "body": "Start the service before tests run locally.",
}
PARAPHRASE = {
    "kind": "gotcha",
    "title": "Specs break on my laptop with boot errors",
    "body": "Boot the service before specs on the laptop.",
}


def _keys(text: str) -> list[str]:
    return KEY_RE.findall(text)


def _memories(mem) -> list[dict]:
    return mem.sql("SELECT * FROM memory ORDER BY created_at")


def _log(mem) -> list[dict]:
    return mem.sql("SELECT * FROM memory_near_duplicate_log")


async def test_same_title_and_scope_twice_confirms_instead_of_copying(
    backend, memory_server
):
    async with memory_server() as mem:
        first = await mem.remember(
            context={"repo": REPO},
            kind="gotcha",
            title="Build takes 300 seconds on a cold cache",
            body="Warm the cache before timing builds.",
        )
        second = await mem.remember(
            context={"repo": REPO.upper()},
            kind="gotcha",
            title="  build takes 45   seconds on a cold CACHE ",
            body="A different body does not matter.",
        )

        [row] = _memories(mem)
        assert row["occurrence_count"] == 2
        assert second == f"Already known [{row['key']}] (confirmations: 2)."
        assert _keys(first) == [row["key"]]


async def test_same_as_confirms_the_named_memory(backend, memory_server):
    async with memory_server() as mem:
        key = _keys(await mem.remember(context={"repo": REPO}, **ORIGINAL))[0]

        result = await mem.remember(
            context={"repo": REPO}, same_as=key, **PARAPHRASE
        )

        [row] = _memories(mem)
        assert row["key"] == key
        assert row["occurrence_count"] == 2
        assert result == f"Already known [{key}] (confirmations: 2)."


async def test_unknown_same_as_key_is_refused_and_nothing_stored(
    backend, memory_server
):
    async with memory_server() as mem:
        await mem.remember(context={"repo": REPO}, **ORIGINAL)

        mangled = await mem.remember(
            context={"repo": REPO}, same_as="MEM-NOPE", **PARAPHRASE
        )
        unknown = await mem.remember(
            context={"repo": REPO}, same_as="MEM-222222", **PARAPHRASE
        )

        assert mangled.startswith("Memory not stored:")
        assert "MEM-NOPE" in mangled
        assert unknown.startswith("Memory not stored:")
        [row] = _memories(mem)
        assert row["occurrence_count"] == 1


async def test_supersedes_replaces_the_old_memory_in_recall(backend, memory_server):
    async with memory_server() as mem:
        old_key = _keys(
            await mem.remember(
                context={"repo": REPO},
                kind="setup",
                title="Acceptance tests need DOTNET_ROLL_FORWARD set",
                body="Export DOTNET_ROLL_FORWARD=LatestMajor before running them.",
            )
        )[0]

        result = await mem.remember(
            context={"repo": REPO},
            kind="setup",
            title="Acceptance tests run without any roll-forward flag",
            body="The flag was removed; run the acceptance tests directly.",
            supersedes=old_key,
        )

        new_key = next(key for key in _keys(result) if key != old_key)
        assert old_key in result
        recalled = await mem.recall(context={"repo": REPO})
        assert new_key in recalled
        assert old_key not in recalled
        old = mem.sql("SELECT * FROM memory WHERE key = :key", key=old_key)[0]
        new = mem.sql("SELECT * FROM memory WHERE key = :key", key=new_key)[0]
        assert old["status"] == "superseded"
        assert old["superseded_by"] == new["id"]
        assert new["status"] == "active"


async def test_unknown_supersedes_key_is_refused_and_nothing_stored(
    backend, memory_server
):
    async with memory_server() as mem:
        result = await mem.remember(
            context={"repo": REPO}, supersedes="MEM-222222", **ORIGINAL
        )

        assert result.startswith("Memory not stored:")
        assert _memories(mem) == []


async def test_near_duplicate_is_not_stored_until_agent_says_distinct(
    backend, memory_server
):
    async with memory_server(memory_embedder=FakeEmbedder()) as mem:
        key = _keys(await mem.remember(context={"repo": REPO}, **ORIGINAL))[0]

        prompt = await mem.remember(context={"repo": REPO}, **PARAPHRASE)

        assert prompt.startswith("Memory not stored:")
        assert f"[{key}] {ORIGINAL['title']} (similarity " in prompt
        assert "distinct" in prompt
        assert len(_memories(mem)) == 1
        [log] = _log(mem)
        assert log["choice"] == "abandoned"
        assert log["top_key"] == key
        assert log["top_similarity"] >= log["threshold"] == 0.92
        assert log["embedding_model"] == "fake-concepts-v1"

        stored = await mem.remember(context={"repo": REPO}, distinct=True, **PARAPHRASE)

        assert stored.startswith("Remembered [")
        assert len(_memories(mem)) == 2
        [log] = _log(mem)
        assert log["choice"] == "distinct"


async def test_near_duplicate_follow_up_with_same_as_confirms_original(
    backend, memory_server
):
    async with memory_server(memory_embedder=FakeEmbedder()) as mem:
        key = _keys(await mem.remember(context={"repo": REPO}, **ORIGINAL))[0]
        await mem.remember(context={"repo": REPO}, **PARAPHRASE)

        result = await mem.remember(context={"repo": REPO}, same_as=key, **PARAPHRASE)

        assert result == f"Already known [{key}] (confirmations: 2)."
        assert len(_memories(mem)) == 1
        [log] = _log(mem)
        assert log["choice"] == "same_as"


async def test_near_duplicate_follow_up_with_supersedes_is_logged(
    backend, memory_server
):
    async with memory_server(memory_embedder=FakeEmbedder()) as mem:
        key = _keys(await mem.remember(context={"repo": REPO}, **ORIGINAL))[0]
        await mem.remember(context={"repo": REPO}, **PARAPHRASE)

        await mem.remember(context={"repo": REPO}, supersedes=key, **PARAPHRASE)

        [log] = _log(mem)
        assert log["choice"] == "supersedes"


async def test_paraphrase_in_conflicting_repo_is_stored_without_prompt(
    backend, memory_server
):
    async with memory_server(memory_embedder=FakeEmbedder()) as mem:
        await mem.remember(context={"repo": REPO}, **ORIGINAL)

        result = await mem.remember(context={"repo": OTHER_REPO}, **PARAPHRASE)

        assert result.startswith("Remembered [")
        assert len(_memories(mem)) == 2
        assert _log(mem) == []


async def test_without_embedder_paraphrase_is_stored_without_check(
    backend, memory_server
):
    async with memory_server() as mem:
        await mem.remember(context={"repo": REPO}, **ORIGINAL)

        result = await mem.remember(context={"repo": REPO}, **PARAPHRASE)

        assert result.startswith("Remembered [")
        assert len(_memories(mem)) == 2
        assert _log(mem) == []
