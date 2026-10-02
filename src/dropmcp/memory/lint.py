"""Write-side checks on memory and report free text."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable, Sequence

LintRule = Callable[[str], str | None]

_PLACEHOLDER = r"(?![$<{*%]|(?:none|null|nil|true|false)\b)"
_SECRET_NAME = (
    r"\w*(?:password|passwd|secret(?:_?key)?|private_?key|token|api_?key"
    r"|access_?key)"
)

_SECRET_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
        r"\bgh[pousr]_[A-Za-z0-9]{30,}",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}",
        r"\bglpat-[A-Za-z0-9_-]{20,}",
        r"\bxox[abposr]-[A-Za-z0-9-]{10,}",
        r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        rf"(?i)\b{_SECRET_NAME}\s*=\s*[\"']?{_PLACEHOLDER}[^\s\"'`]{{4,}}",
        rf"(?i)[\"']{_SECRET_NAME}[\"']\s*:\s*[\"']{_PLACEHOLDER}[^\"']{{4,}}[\"']",
        rf"(?i)\b[a-z][a-z0-9+.-]*://[^\s/:@]+:{_PLACEHOLDER}[^\s/@]+@",
    )
)

_TOKEN = re.compile(r"[A-Za-z0-9_+]{24,}={0,2}")
_HEX = re.compile(r"[0-9a-fA-F]+")
_MIN_ENTROPY_BITS = 4.0

_AGENT_ADDRESSED = re.compile(
    r"(?i)\b(?:ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier)"
    r"|ignore\s+all\s+instructions|disregard|you\s+must|as\s+an\s+ai"
    r"|system\s+prompt)\b"
)

# A user's home directory: machine-specific, and it often names the person.
_LOCAL_PATH = re.compile(
    r"(?<![\w/])(?:/home/|/Users/|(?i:[a-z]:[\\/]users[\\/]))[^\s/\\]+"
)

_TOOL_CALL = re.compile(
    r"(?i)</?\s*(?:tool_call|function_calls)\b|<\s*invoke\b"
    r"|\bfunctions\.\w+\s*\("
)
_JSON_NAME = re.compile(r"[\"']name[\"']\s*:")
_JSON_ARGUMENTS = re.compile(r"[\"']arguments[\"']\s*:")

_COMMAND_BINARIES = frozenset(
    {
        "apt", "apt-get", "bash", "brew", "cargo", "cat", "cd", "chmod", "cp",
        "curl", "docker", "docker-compose", "dotnet", "export", "gh", "git",
        "glab", "go", "gradle", "helm", "kubectl", "ls", "make", "mkdir", "mv",
        "mvn", "node", "npm", "npx", "pip", "pip3", "pnpm", "python", "python3",
        "rm", "sh", "ssh", "sudo", "terraform", "uv", "wget", "yarn",
    }
)  # fmt: skip
_COMMAND_SHARE = 0.6


def _shannon_entropy(token: str) -> float:
    counts = Counter(token)
    total = len(token)
    return -sum(n / total * math.log2(n / total) for n in counts.values())


def _has_high_entropy_token(text: str) -> bool:
    for token in _TOKEN.findall(text):
        if _HEX.fullmatch(token):
            continue
        has_digit = any(c.isdigit() for c in token)
        has_letter = any(c.isalpha() for c in token)
        if has_digit and has_letter and _shannon_entropy(token) >= _MIN_ENTROPY_BITS:
            return True
    return False


def _looks_like_secret(text: str) -> bool:
    return any(p.search(text) for p in _SECRET_PATTERNS) or _has_high_entropy_token(
        text
    )


def _has_tool_call(text: str) -> bool:
    if _TOOL_CALL.search(text):
        return True
    return bool(_JSON_NAME.search(text) and _JSON_ARGUMENTS.search(text))


def _is_command_line(line: str) -> bool:
    if line.startswith("$ "):
        return True
    first = line.split(maxsplit=1)[0]
    return first in _COMMAND_BINARIES or first.startswith("./")


def _is_command_dominated(text: str) -> bool:
    lines = 0
    commands = 0
    in_fence = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not line:
            continue
        lines += 1
        if in_fence or _is_command_line(line):
            commands += 1
    return lines > 0 and commands / lines > _COMMAND_SHARE


def _check_field(
    name: str,
    text: str | None,
    extra_rules: Sequence[LintRule],
    *,
    commands: bool = False,
) -> list[str]:
    if not text:
        return []
    reasons: list[str] = []
    if _looks_like_secret(text):
        reasons.append(
            f"{name} looks like a credential; never store secrets or tokens."
        )
    if _AGENT_ADDRESSED.search(text):
        reasons.append(
            f"{name} addresses the reader as an agent; state the fact instead."
        )
    if _has_tool_call(text):
        reasons.append(
            f"{name} contains tool-call syntax; describe the behaviour in prose."
        )
    if _LOCAL_PATH.search(text):
        reasons.append(
            f"{name} contains a local filesystem path; use a path inside the repo."
        )
    if commands and _is_command_dominated(text):
        reasons.append(
            f"{name} is mostly commands to run; explain the fact and keep at most "
            "a command or two."
        )
    for rule in extra_rules:
        reason = rule(text)
        if reason is not None:
            reasons.append(f"{name}: {reason.rstrip('.')}.")
    return reasons


def check_memory(
    title: str,
    body: str,
    evidence: str | None,
    extra_rules: Sequence[LintRule],
) -> list[str]:
    return [
        *_check_field("title", title, extra_rules),
        *_check_field("body", body, extra_rules, commands=True),
        *_check_field("evidence", evidence, extra_rules),
    ]


def check_report(
    described_memory: str | None,
    reason: str | None,
    correction: str | None,
    extra_rules: Sequence[LintRule],
) -> list[str]:
    return [
        *_check_field("memory", described_memory, extra_rules),
        *_check_field("reason", reason, extra_rules),
        *_check_field("correction", correction, extra_rules),
    ]
