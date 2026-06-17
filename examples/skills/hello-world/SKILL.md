---
name: hello-world
category: examples
description: A minimal example skill. Use when demonstrating how dropmcp turns a SKILL.md folder into an MCP tool.
instruction_summary: Demonstrating how dropmcp serves a skill as an MCP tool.
---

# Hello World

This is an example skill shipped with `dropmcp`. When an MCP client invokes
this tool, it receives this entire file as text, plus resource links to any
supporting files in this folder.

## How skills work

1. Create a folder under your `skills/` directory.
2. Add a `SKILL.md` with YAML frontmatter (`name`, `category`, `description`).
3. Drop any supporting files (scripts, references) alongside it — they become
   `skill://hello-world/<path>` resource links.

Replace this skill with your own.
