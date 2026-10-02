"""Write-side checks on memory and report free text."""

from __future__ import annotations

from collections.abc import Callable, Sequence

LintRule = Callable[[str], str | None]


def check_memory(
    title: str,
    body: str,
    evidence: str | None,
    extra_rules: Sequence[LintRule],
) -> list[str]:
    # TODO(S8): built-in rules plus ``extra_rules`` over each non-empty field.
    return []


def check_report(
    described_memory: str | None,
    reason: str | None,
    correction: str | None,
    extra_rules: Sequence[LintRule],
) -> list[str]:
    # TODO(S8): built-in rules plus ``extra_rules`` over each non-empty field.
    return []
