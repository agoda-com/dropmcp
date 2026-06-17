"""Command-line interface for dropmcp."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import dropmcp
from dropmcp.config import Settings
from dropmcp.validate import run_validation


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dropmcp", description=dropmcp.__doc__)
    parser.add_argument("--version", action="version", version=dropmcp.__version__)
    sub = parser.add_subparsers(dest="command", required=False)

    serve = sub.add_parser("serve", help="Run the MCP server.")
    serve.add_argument("--skills", help="Path to the skills/ directory.")
    serve.add_argument("--prompts", help="Path to the prompts/ directory.")
    serve.add_argument("--name", help="Server name shown to MCP clients.")
    serve.add_argument("--website-url", help="Homepage URL shown in the catalog.")
    serve.add_argument("--icon", help="Path to a server icon (svg/png).")
    serve.add_argument(
        "--instructions",
        help="Path to INSTRUCTIONS.md (auto-detected from cwd if omitted).",
    )
    serve.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http"],
        help="Transport to serve over (default: stdio).",
    )
    serve.add_argument("--host", help="Bind host for http transport.")
    serve.add_argument("--port", type=int, help="Bind port for http transport.")
    serve.add_argument(
        "--no-ui", action="store_true", help="Disable the catalog HTTP routes."
    )
    serve.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload when serving over http.",
    )

    validate = sub.add_parser(
        "validate",
        help="Validate SKILL.md and PROMPT.md files under skills/ and prompts/.",
    )
    validate.add_argument("--skills", help="Path to the skills/ directory.")
    validate.add_argument("--prompts", help="Path to the prompts/ directory.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "serve":
        dropmcp.run(
            skills=args.skills,
            prompts=args.prompts,
            name=args.name,
            website_url=args.website_url,
            icon=args.icon,
            instructions=args.instructions,
            transport=args.transport,
            host=args.host,
            port=args.port,
            ui_enabled=False if args.no_ui else None,
            reload=True if args.reload else None,
        )
        return 0

    if args.command == "validate":
        settings = Settings.resolve(skills=args.skills, prompts=args.prompts)
        return run_validation(
            settings.skills_dir,
            settings.prompts_dir,
            root=Path.cwd(),
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
