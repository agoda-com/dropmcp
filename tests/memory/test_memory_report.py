"""S7: keyed and unkeyed ``memory_report``, dedupe and candidate keys."""

from __future__ import annotations

from dropmcp.memory.keys import KEY_ALPHABET, new_key
from dropmcp.memory.store import report_to_dict

REPO = "example-org/payments-api"
OTHER_REPO = "example-org/ledger-service"
FLAG_TITLE = "Acceptance tests need DOTNET_ROLL_FORWARD=LatestMajor"


async def _remember(server, title: str, repo: str = REPO) -> str:
    await server.remember(
        kind="gotcha",
        title=title,
        body=f"{title}. Seen while running the suite locally.",
        context={"repo": repo, "language": "csharp"},
    )
    rows = server.sql("SELECT key FROM memory WHERE title = :title", title=title)
    return rows[0]["key"]


def _reports(server) -> list[dict]:
    return [
        report_to_dict(row)
        for row in server.sql("SELECT * FROM memory_report ORDER BY created_at, id")
    ]


def _mangle(key: str) -> str:
    first = key[4]
    replacement = next(char for char in KEY_ALPHABET if char != first)
    return f"{key[:4]}{replacement}{key[5:]}"


async def test_keyed_reports_dedupe_on_memory_and_problem(memory_server, backend):
    async with memory_server() as server:
        key = await _remember(server, FLAG_TITLE)
        memory_id = server.sql("SELECT id FROM memory WHERE key = :key", key=key)[0][
            "id"
        ]

        first = await server.report(key=key, problem="stale", reason="Flag removed.")
        second = await server.report(key=key, problem="stale", reason="Still gone.")
        third = await server.report(key=key, problem="invalid", reason="Never true.")

        reports = _reports(server)
        assert len(reports) == 2
        stale, invalid = reports
        assert first == f"Reported ({stale['id']})."
        assert second == f"Already reported ({stale['id']}, occurrences: 2)."
        assert third == f"Reported ({invalid['id']})."
        assert stale["memory_id"] == memory_id
        assert stale["reported_key"] == key
        assert stale["problem"] == "stale"
        assert stale["occurrence_count"] == 2
        assert stale["last_seen_at"] >= stale["created_at"]
        assert stale["candidate_keys"] == []
        assert invalid["memory_id"] == memory_id
        assert invalid["occurrence_count"] == 1


async def test_deduplicated_keyed_sensitive_report_keeps_memory_hidden(
    memory_server, backend
):
    async with memory_server() as server:
        key = await _remember(server, FLAG_TITLE)

        await server.report(key=key, problem="sensitive", reason="Held a token.")
        server.sql("UPDATE memory SET hidden_at = NULL WHERE key = :key", key=key)
        again = await server.report(key=key, problem="sensitive", reason="Token.")

        assert again.startswith("Already reported (")
        hidden = server.sql("SELECT hidden_at FROM memory WHERE key = :key", key=key)
        assert hidden[0]["hidden_at"] is not None
        assert len(_reports(server)) == 1


async def test_unkeyed_report_stores_description_and_candidate_keys(
    memory_server, backend
):
    async with memory_server() as server:
        key = await _remember(server, FLAG_TITLE)
        await _remember(server, "Integration tests need a running Redis")
        await _remember(server, "Ledger migrations run in a single transaction", OTHER_REPO)

        result = await server.report(
            memory="Said acceptance tests need DOTNET_ROLL_FORWARD=LatestMajor",
            problem="stale",
            reason="The flag was removed; tests run without it.",
            context={"repo": REPO},
        )

        [report] = _reports(server)
        assert report["memory_id"] is None
        assert report["reported_key"] is None
        assert report["described_memory"] == (
            "Said acceptance tests need DOTNET_ROLL_FORWARD=LatestMajor"
        )
        assert key in report["candidate_keys"]
        assert len(report["candidate_keys"]) <= 3
        assert result == (
            f"Reported ({report['id']}). Possible matches: "
            + ", ".join(report["candidate_keys"])
        )


async def test_unkeyed_report_without_matches_says_so(memory_server, backend):
    async with memory_server() as server:
        result = await server.report(
            memory="Said the build needs a VPN",
            problem="invalid",
            context={"repo": REPO},
        )

        [report] = _reports(server)
        assert report["candidate_keys"] == []
        assert result == f"Reported ({report['id']}). No possible matches."


async def test_mangled_key_is_stored_unkeyed_as_sent(memory_server, backend):
    async with memory_server() as server:
        key = await _remember(server, FLAG_TITLE)
        mangled = _mangle(key)

        result = await server.report(
            key=mangled,
            memory="Said acceptance tests need DOTNET_ROLL_FORWARD",
            problem="stale",
            context={"repo": REPO},
        )

        [report] = _reports(server)
        assert result.startswith(f"Reported ({report['id']}).")
        assert report["memory_id"] is None
        assert report["reported_key"] == mangled
        assert key in report["candidate_keys"]


async def test_well_formed_unknown_key_is_stored_unkeyed(memory_server, backend):
    async with memory_server() as server:
        key = await _remember(server, FLAG_TITLE)
        unknown = next(candidate for candidate in iter(new_key, None) if candidate != key)

        result = await server.report(
            key=unknown,
            memory="Said acceptance tests need DOTNET_ROLL_FORWARD",
            problem="sensitive",
            context={"repo": REPO},
        )

        [report] = _reports(server)
        assert result.startswith(f"Reported ({report['id']}).")
        assert report["memory_id"] is None
        assert report["reported_key"] == unknown
        hidden = server.sql("SELECT hidden_at FROM memory WHERE key = :key", key=key)
        assert hidden[0]["hidden_at"] is None


async def test_report_without_key_or_description_is_refused(memory_server, backend):
    async with memory_server() as server:
        await _remember(server, FLAG_TITLE)

        no_key = await server.report(problem="stale", context={"repo": REPO})
        bad_key = await server.report(key="MEM-NOPE", problem="stale")

        assert no_key.startswith("Memory report not recorded:")
        assert "key" in no_key and "`memory`" in no_key
        assert bad_key.startswith("Memory report not recorded:")
        assert "MEM-NOPE" in bad_key and "`memory`" in bad_key
        assert _reports(server) == []


async def test_unknown_problem_is_refused(memory_server, backend):
    async with memory_server() as server:
        key = await _remember(server, FLAG_TITLE)

        result = await server.report(key=key, problem="outdated")

        assert result.startswith("Memory report not recorded: problem must be")
        assert _reports(server) == []


async def test_unkeyed_duplicates_dedupe_on_repo_problem_and_description(
    memory_server, backend
):
    async with memory_server() as server:
        first = await server.report(
            memory="Said the retry count is 3 for flaky tests",
            problem="stale",
            context={"repo": REPO},
        )
        second = await server.report(
            memory="said the RETRY count is 5 for flaky tests",
            problem="stale",
            context={"repo": REPO, "task": "test"},
        )
        other_problem = await server.report(
            memory="Said the retry count is 3 for flaky tests",
            problem="invalid",
            context={"repo": REPO},
        )
        other_repo = await server.report(
            memory="Said the retry count is 3 for flaky tests",
            problem="stale",
            context={"repo": OTHER_REPO},
        )

        reports = _reports(server)
        assert len(reports) == 3
        stale = reports[0]
        assert first.startswith(f"Reported ({stale['id']}).")
        assert second.startswith(f"Already reported ({stale['id']}, occurrences: 2).")
        assert stale["occurrence_count"] == 2
        assert other_problem.startswith("Reported (")
        assert other_repo.startswith("Reported (")


async def test_correction_and_context_round_trip(memory_server, backend):
    async with memory_server() as server:
        key = await _remember(server, FLAG_TITLE)

        await server.report(
            key=key,
            problem="stale",
            reason="The flag was removed.",
            correction="Acceptance tests run on the default roll-forward policy.",
            context={"repo": REPO, "language": "csharp", "task": "test"},
        )
        await server.report(
            memory="Said integration tests need Redis",
            problem="wrong_scope",
            reason="Only the cache module needs it.",
            correction="Scope it to the cache path.",
            context={"repo": REPO, "path": "src/cache"},
        )

        keyed, unkeyed = _reports(server)
        assert keyed["correction"] == (
            "Acceptance tests run on the default roll-forward policy."
        )
        assert keyed["reason"] == "The flag was removed."
        assert keyed["context"]["repo"] == REPO
        assert keyed["context"]["language"] == "csharp"
        assert keyed["context"]["task"] == "test"
        assert unkeyed["correction"] == "Scope it to the cache path."
        assert unkeyed["reason"] == "Only the cache module needs it."
        assert unkeyed["context"]["repo"] == REPO
        assert unkeyed["context"]["path"] == "src/cache"
