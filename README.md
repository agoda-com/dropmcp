# dropmcp

Drop a `skills/` and `prompts/` folder, get a [FastMCP](https://gofastmcp.com)
server — with a browseable catalog — in one line.

```python
import dropmcp

dropmcp.run(skills="skills", prompts="prompts")
```

`dropmcp` is the reusable, repo-agnostic engine behind several internal
skills/prompts MCP servers, extracted as a standalone library.

## Install

```bash
pip install dropmcp
```

Optional OpenTelemetry export:

```bash
pip install "dropmcp[otel]"
```

## Quick start

Lay out your content:

```
skills/
  my-skill/
    SKILL.md         # YAML frontmatter: name, category, description
    reference.md     # optional supporting files -> resource links
prompts/
  my-prompt/
    PROMPT.md        # YAML frontmatter: name, description, arguments
    assets/          # optional assets -> prompt://my-prompt/assets/<file>
```

Then serve it:

```python
import dropmcp

dropmcp.run(skills="skills", prompts="prompts")          # stdio (default)
dropmcp.run(skills="skills", prompts="prompts", transport="http", port=8000)
```

Or from the command line:

```bash
dropmcp serve --skills skills --prompts prompts
dropmcp serve --skills skills --prompts prompts --transport http --port 8000
dropmcp validate --skills skills --prompts prompts
```

Need to customise the server before it runs? Use the factory:

```python
mcp = dropmcp.create_server(skills="skills", prompts="prompts")
# add your own routes / middleware ...
mcp.run(transport="stdio")
```

A runnable example lives in [`examples/`](examples/).

## Scaffold a new server (copier)

Generate a ready-to-run project from the bundled template:

```bash
pip install copier
copier copy gh:agoda-com/dropmcp//template my-skills-mcp
cd my-skills-mcp
pip install -r requirements.txt
dropmcp validate
python server.py
```

The template asks for a project name and whether to include [Promptfoo](https://www.promptfoo.dev/) eval scaffolding under `tests/`.

## Configuration

Every option can be passed as a keyword argument, set via a `DROPMCP_*`
environment variable, or left to its default (kwargs win, then env, then
default).

| kwarg | env | default | purpose |
|---|---|---|---|
| `skills` | `DROPMCP_SKILLS` | `skills` | skills directory |
| `prompts` | `DROPMCP_PROMPTS` | `prompts` | prompts directory |
| `name` | `DROPMCP_NAME` | `dropmcp` | server name shown to clients |
| `website_url` | `DROPMCP_WEBSITE_URL` | – | server homepage URL |
| `icon` | `DROPMCP_ICON` | – | path to an icon (svg/png) |
| `instructions` | `DROPMCP_INSTRUCTIONS` | auto | `INSTRUCTIONS.md` template |
| `transport` | `DROPMCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `host` | `DROPMCP_HOST` | `127.0.0.1` | bind host (http) |
| `port` | `DROPMCP_PORT` | `8000` | bind port (http) |
| `ui_enabled` | `DROPMCP_UI` | `true` | serve the catalog HTTP routes |
| `reload` | `DROPMCP_RELOAD` | `false` | re-scan skills/prompts on every request |

If an `INSTRUCTIONS.md` sits next to your content folders it is picked up
automatically; otherwise a generic default ships with the package. The
`{{INSTRUCTION_SUMMARIES}}` and `{{PROMPT_SUMMARIES}}` placeholders are
filled from each item's `instruction_summary` frontmatter.

## Hosting guide

### Local (stdio)

The default `stdio` transport is for local AI clients such as [Cursor](https://cursor.sh)
and [Claude Desktop](https://claude.ai/download). Add an entry to your MCP
config (e.g. `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "my-skills": {
      "command": "dropmcp",
      "args": ["serve", "--skills", "/path/to/skills", "--prompts", "/path/to/prompts"]
    }
  }
}
```

Or if you have a `server.py`:

```json
{
  "mcpServers": {
    "my-skills": {
      "command": "python",
      "args": ["/path/to/server.py"]
    }
  }
}
```

### HTTP (hosted / remote clients)

Switch to streamable-HTTP for multi-client hosted deployments:

```bash
dropmcp serve --transport http --host 0.0.0.0 --port 8000
```

The catalog UI is available at `http://localhost:8000/` and the health check
endpoint at `http://localhost:8000/health`.

### Docker

A minimal `Dockerfile` for a hosted deployment:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install dropmcp

COPY skills/ skills/
COPY prompts/ prompts/
COPY INSTRUCTIONS.md .          # optional

ENV DROPMCP_TRANSPORT=http
ENV DROPMCP_HOST=0.0.0.0
ENV DROPMCP_PORT=8000
ENV DROPMCP_NAME="My Skills MCP"

EXPOSE 8000
CMD ["dropmcp", "serve"]
```

Build and run:

```bash
docker build -t my-skills-mcp .
docker run -p 8000:8000 my-skills-mcp
```

Connect a remote MCP client to `http://<host>:8000/mcp`.

### Environment-only deployment

All settings can be passed via environment variables — no `server.py` needed:

```bash
export DROPMCP_SKILLS=/data/skills
export DROPMCP_PROMPTS=/data/prompts
export DROPMCP_TRANSPORT=http
export DROPMCP_HOST=0.0.0.0
export DROPMCP_PORT=8000
export DROPMCP_NAME="Acme Skills"
export DROPMCP_WEBSITE_URL="https://skills.example.com"

dropmcp serve
```

### OpenTelemetry

Install the OTEL extra and point at your collector:

```bash
pip install "dropmcp[otel]"
export OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector:4318"
dropmcp serve --transport http
```

Metrics and structured logs are emitted per skill invocation, prompt render,
and resource read. When `OTEL_EXPORTER_OTLP_ENDPOINT` is unset (the default),
telemetry is a no-op — no extra imports, no overhead.

## Skill and prompt format

### SKILL.md

```markdown
---
name: my-skill
category: my-category
description: One-line description shown to the LLM as the tool description.
instruction_summary: Short phrase for the server-level INSTRUCTIONS.md bullet.
---

Full skill body here — this is what the LLM receives when it calls the tool.
```

### PROMPT.md

```markdown
---
name: my-prompt
description: Short description shown in the catalog.
instruction_summary: Short phrase for INSTRUCTIONS.md.
arguments:
  - name: who
    description: The person to greet.
    required: true
  - name: tone
    description: Greeting tone (optional).
    required: false
---

Write a {{tone}} greeting addressed to {{who}}.
```

Validate your content before starting the server:

```bash
dropmcp validate --skills skills --prompts prompts
```

## License

Apache-2.0.
