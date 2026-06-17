<div align="center">
  <img src="src/dropmcp/static/icon.svg" alt="Drop MCP Logo" width="120" />
</div>

# Drop MCP

Drop a `skills/` and `prompts/` folder, get a [FastMCP](https://gofastmcp.com)
server — with a browseable catalog — in one line.

```python
import dropmcp

dropmcp.run(skills="skills", prompts="prompts")
```

`dropmcp` is the reusable, repo-agnostic engine behind several internal
skills/prompts MCP servers, extracted as a standalone library.

## Why dropmcp?

Skills and prompts are just markdown — anyone can write them, and there are
plenty of ways to get them in front of an agent: copy them into `.cursor/skills`,
ship an IDE plugin, sync a folder, paste them into context. The trouble is that
every one of those is tied to a single tool, has no central updates, no way to
scope who sees what, and no signal about what actually gets used. Spread across
many people, repos, and editors, that fragments fast — the same skill forked
five ways with no canonical copy, and skills that work in one agent but not the
next.

Serving skills over MCP solves the delivery problem generically: one server is
reachable from any MCP client (Cursor, Claude Code, CI, whatever comes next),
the filesystem stays the single source of truth so there's no registry to drift,
and because every skill call is one request, usage is observable for free. The
catch is that standing up that server is the same boilerplate every time —
frontmatter parsing, tool/prompt/resource registration, a browseable catalog,
telemetry, hosting.

`dropmcp` is that boilerplate, extracted and built around Fast MCP. Point it at a `skills/` and `prompts/`
folder and you get a tested, observable MCP server, so you run one focused
server per audience instead of rebuilding the engine each time. Authors maintain
content, not infrastructure.

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

Then serve it over streamable-HTTP:

```python
import dropmcp

dropmcp.run(skills="skills", prompts="prompts")              # binds 127.0.0.1:8000
dropmcp.run(skills="skills", prompts="prompts", host="0.0.0.0", port=8000)
```

dropmcp is a *hosted* server — it exists to share skills and prompts with
remote MCP clients, so it serves over streamable-HTTP only (no local stdio).
The catalog UI is at `http://<host>:<port>/` and the MCP endpoint at `/mcp`.

Need to customise the server before it runs? Use the factory:

```python
mcp = dropmcp.create_server(skills="skills", prompts="prompts")
# add your own routes / middleware ...
mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
```

A runnable example lives in [`examples/`](examples/).

## Scaffold a new server (copier)

Generate a ready-to-run project from the bundled template:

```bash
pip install copier
copier copy gh:agoda-com/dropmcp//template my-skills-mcp
cd my-skills-mcp
pip install -r requirements.txt
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
| `name` | `DROPMCP_NAME` | `dropmcp` | server name shown to clients and OTEL service name |
| `website_url` | `DROPMCP_WEBSITE_URL` | – | server homepage URL |
| `icon` | `DROPMCP_ICON` | – | path to an icon (svg/png) |
| `instructions` | `DROPMCP_INSTRUCTIONS` | auto | `INSTRUCTIONS.md` template |
| `host` | `DROPMCP_HOST` | `127.0.0.1` | bind host |
| `port` | `DROPMCP_PORT` | `8000` | bind port |
| `ui_enabled` | `DROPMCP_UI` | `true` | serve the catalog HTTP routes |
| `feedback_enabled` | `DROPMCP_FEEDBACK` | `true` | enable the `record_feedback` tool, feedback HTTP routes, and always-on instructions |
| `reload` | `DROPMCP_RELOAD` | `false` | re-scan skills/prompts on every request |
| `database_url` | `DROPMCP_DATABASE_URL` | `sqlite:///<cwd>/dropmcp.db` | feedback database (SQLite file or Postgres URL) |
| `eval_results_project` | `DROPMCP_EVAL_RESULTS_PROJECT` | – | GitLab project path for E2E eval results (enables `/api/telemetry` when a store is available) |
| `eval_results_commit_sha` | `DROPMCP_EVAL_RESULTS_COMMIT_SHA` | `COMMIT_SHA` file | deployed commit to filter eval results |
| `catalog_defaults` | `DROPMCP_CATALOG_DEFAULTS` | bundled SVGs | category thumbnail fallbacks for the catalog grid |

If an `INSTRUCTIONS.md` sits next to your content folders it is picked up
automatically; otherwise a generic default ships with the package. The
`{{INSTRUCTION_SUMMARIES}}` and `{{PROMPT_SUMMARIES}}` placeholders are
filled from each item's `instruction_summary` frontmatter.

## Hosting guide

dropmcp serves over streamable-HTTP for multi-client hosted deployments. Run
your `server.py`:

```bash
DROPMCP_HOST=0.0.0.0 DROPMCP_PORT=8000 python server.py
```

The catalog UI is available at `http://localhost:8000/`, the health check
endpoint at `http://localhost:8000/health`, and the MCP endpoint at
`http://localhost:8000/mcp`. Point your remote MCP clients there.

### Docker

A minimal `Dockerfile` for a hosted deployment:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install dropmcp

COPY skills/ skills/
COPY prompts/ prompts/
COPY INSTRUCTIONS.md .          # optional

ENV DROPMCP_HOST=0.0.0.0
ENV DROPMCP_PORT=8000
ENV DROPMCP_NAME="My Skills MCP"

EXPOSE 8000
CMD ["python", "-m", "dropmcp"]
```

Build and run:

```bash
docker build -t my-skills-mcp .
docker run -p 8000:8000 my-skills-mcp
```

Connect a remote MCP client to `http://<host>:8000/mcp`.

### Environment-only deployment

All settings can be passed via environment variables and started with
`python -m dropmcp` — no `server.py` needed:

```bash
export DROPMCP_SKILLS=/data/skills
export DROPMCP_PROMPTS=/data/prompts
export DROPMCP_HOST=0.0.0.0
export DROPMCP_PORT=8000
export DROPMCP_NAME="Acme Skills"
export DROPMCP_WEBSITE_URL="https://skills.example.com"

python -m dropmcp
```

### OpenTelemetry

Install the OTEL extra and point at your collector:

```bash
pip install "dropmcp[otel]"
export OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector:4318"
python -m dropmcp
```

Metrics and structured logs are emitted per skill invocation, prompt render,
resource read, and MCP protocol event (`initialize`, `tools/list`). Metric
names use dotted OTel style (for example `skill.invocations`,
`skill.invocation.duration`) with delta temporality for histograms. The OTEL
service name defaults to `DROPMCP_NAME`; override with `OTEL_SERVICE_NAME` if
needed.

When `OTEL_EXPORTER_OTLP_ENDPOINT` is unset, OpenTelemetry export is a no-op —
no extra imports, no export overhead — but structured per-invocation logs still
go to the console.

## Agent feedback

dropmcp includes a built-in feedback loop for when agents get corrected:

- **`record_feedback` MCP tool** — agents write structured feedback (no external Slack/GitLab wiring).
- **SQLite by default** — a `dropmcp.db` file is created next to your content folders on first run.
- **Postgres override** — set `DROPMCP_DATABASE_URL=postgresql://user:pass@host/db` for durable hosted storage.
- **Feedback UI** — browse, search, filter, and triage at `/feedback` in the catalog SPA (`GET`/`PATCH /api/feedback`).

Privacy guardrails: no verbatim user prompts, code, secrets, or PII. When feedback
is enabled, dropmcp injects always-on guidance into the server instructions
describing when and how agents should call `record_feedback` — no separate skill
to install. Disable the whole feature (tool, HTTP routes, and instructions) with
`DROPMCP_FEEDBACK=false`.

In containers, mount a volume over the SQLite file (or use Postgres) or feedback
is lost when the pod restarts.

## E2E eval results (telemetry panel)

The catalog detail page includes an **E2E Test Results** panel (ported from
skills-mcp) showing per-skill Promptfoo eval scores from your CI pipeline.

Eval results are **pluggable** — dropmcp ships the UI and HTTP routes, but the
data source is optional so the library stays deployment-agnostic:

- Pass an `eval_results_store` to `create_server()` (any object implementing
  `get_results_for_skill` / `get_all_latest_results`), **or**
- Set `DROPMCP_EVAL_RESULTS_PROJECT` and install the StarRocks extra:

  ```bash
  pip install "dropmcp[starrocks]"
  export DROPMCP_EVAL_RESULTS_PROJECT="full-stack/agents/skills-mcp"
  export DROPMCP_EVAL_RESULTS_COMMIT_SHA="$(cat COMMIT_SHA)"
  ```

When no store is configured the panel renders an empty state; routes are not
registered. This keeps StarRocks / Fleet JWT coupling out of the base package.

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

Validate your content before starting the server with the bundled checker:

```bash
python -c "import sys; from dropmcp.validate import run_validation; sys.exit(run_validation('skills', 'prompts'))"
```

## Releasing

Releases are cut by pushing a `v*` git tag. The [CI workflow](.github/workflows/ci.yml)
does the rest: on a tag it builds the catalog UI, builds the wheel + sdist,
publishes to PyPI via [trusted publishing](https://docs.pypi.org/trusted-publishers/)
(no API token needed), and creates a GitHub Release with auto-generated notes.

To ship a new version:

1. Bump the version in **both** [`pyproject.toml`](pyproject.toml) (`version`)
   and [`src/dropmcp/__init__.py`](src/dropmcp/__init__.py) (`__version__`) —
   they must match, and the tag must match too. Use [semver](https://semver.org/).
2. Land the bump on `main` via a merged PR (CI runs tests + the UI build on the PR).
3. Tag the merge commit and push the tag:

   ```bash
   git checkout main && git pull
   git tag v0.2.0
   git push origin v0.2.0
   ```

4. Watch the `publish-pypi` job in Actions. When it's green, the new version is
   live on [PyPI](https://pypi.org/project/dropmcp/) and a GitHub Release exists
   for the tag.

The tag must start with `v` (e.g. `v0.2.0`) — that prefix is what gates the
publish job. Pushing to `main` without a tag only runs tests and builds the
wheel artifact; it never publishes.

## License

Apache-2.0.
