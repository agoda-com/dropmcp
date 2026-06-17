This server exposes a curated set of **skills** and **prompts** loaded from a
filesystem. Skills are returned as tools; prompts are templated messages you
invoke by name.

### Skills

Check this server's skills when the user is working on a task one of them
covers:

{{INSTRUCTION_SUMMARIES}}

Each skill tool returns its full instructions plus resource links to any
supporting files (scripts, templates, references). Call the tool, then follow
the returned instructions.

### Prompts

This server also exposes prompts — templated messages you can invoke with
arguments:

{{PROMPT_SUMMARIES}}
