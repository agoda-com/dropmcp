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

## Features

- **Browseable skill catalog** — a built-in web UI to search, filter, and
  preview every skill and prompt, with copy-paste install snippets for each MCP
  client.
- **Zero-boilerplate server** — point it at a `skills/` and `prompts/` folder
  and get a tested FastMCP server over streamable-HTTP.
- **Filesystem as source of truth** — skills and prompts are just markdown with
  YAML frontmatter; no registry to drift out of sync.
- **Observability built in** — per-invocation structured logs plus optional
  OpenTelemetry metrics and traces.
- **Agent feedback loop** — a `record_feedback` tool and triage UI for when
  agents get corrected.
- **Repository feedback backlog** — an optional `record_repo_feedback` tool and
  triage UI for flaky tests, CI-only checks, setup gaps, and other repo friction.
- **Shared agent memory** — optional `memory_remember` / `memory_recall` /
  `memory_report` tools so agents pass short, reusable working facts about repos
  and stacks to the next agent.
- **Benchmarks page** — an optional models × skills matrix of the latest E2E
  eval results, shown only to identified users.
- **Per-user subscriptions** — optional opt-in so each user's agent sees only a
  curated subset of the catalog.

<div align="center">
  <img src="docs/images/catalog.png" alt="Drop MCP browseable skill catalog" width="800" />
</div>

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

Optional numpy for faster vector scoring in [shared agent memory](#shared-agent-memory):

```bash
pip install "dropmcp[memory]"
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
| `repo_feedback_enabled` | `DROPMCP_REPO_FEEDBACK` | `false` | enable the optional `record_repo_feedback` tool, repo feedback HTTP routes, and always-on instructions |
| `memory_enabled` | `DROPMCP_MEMORY` | `false` | enable the [shared agent memory](#shared-agent-memory) tools and always-on instructions |
| `memory_embedder` | – | – | `MemoryEmbedder` for vector recall and the near-duplicate check; keyword-only when unset |
| `memory_vocabulary` | `DROPMCP_MEMORY_VOCABULARY` | bundled list | YAML/JSON file (or dict) of languages, stack tags, domains, kinds and tasks |
| `memory_lint_rules` | – | – | extra write-side checks for memory and report text |
| `memory_store` | – | built from `database_url` | replace the memory store entirely |
| `memory_candidate_cap` | `DROPMCP_MEMORY_CANDIDATE_CAP` | `500` | max candidates scored per recall or near-duplicate check |
| `user_subscriptions_enabled` | `DROPMCP_USER_SUBSCRIPTIONS` | `false` | per-user skill/prompt opt-in over MCP and subscription HTTP API |
| `user_header` | `DROPMCP_USER_HEADER` | `X-User-Email` | HTTP header carrying the trusted caller identity |
| `reload` | `DROPMCP_RELOAD` | `false` | re-scan skills/prompts on every request |
| `database_url` | `DROPMCP_DATABASE_URL` | `sqlite:///<cwd>/dropmcp.db` | feedback and memory database tables (SQLite file or Postgres URL) |
| `eval_results_project` | `DROPMCP_EVAL_RESULTS_PROJECT` | – | project path for E2E eval results (enables `/api/telemetry` when a store is available) |
| `eval_results_commit_sha` | `DROPMCP_EVAL_RESULTS_COMMIT_SHA` | `COMMIT_SHA` file | deployed commit to filter eval results |
| – | `DROPMCP_EVAL_RESULTS_SKILL_QUERY` | – | SQL for one skill; required for the built-in MySQL store |
| – | `DROPMCP_EVAL_RESULTS_ALL_QUERY` | – | SQL for every skill; required for the built-in MySQL store |
| `benchmarks_enabled` | `DROPMCP_BENCHMARKS` | `false` | serve the `/benchmarks` page and `/api/benchmarks` (needs `eval_results_project` and `benchmark_results_store`) |
| `benchmark_results_store` | – | – | object implementing `get_latest_benchmark_results(project, lookback_days)`; required when benchmarks are enabled |
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

Telemetry preserves richer self-reported MCP metadata in structured logs,
including `initialize.params.clientInfo`, protocol version, capability summary,
selected request `_meta` keys (`agent`, `ide`, `team`, `repo`, `environment`,
`launcher`, `launcher_version`, `trace_id`), session/transport details, HTTP
fallback headers, operation names, and sanitized error context. These values are
for observability only and are not security signals.

Metric attributes are deliberately bounded: `client`, `client_version`,
`client_source`, `transport`, `team`, `environment`, `operation_kind`,
`outcome`, and `error.type`, plus the relevant local operation name such as
`skill`, `prompt`, or `resource`. Unknown values roll up to `other`, missing
values roll up to `unknown`, and request `_meta` values are allowlisted,
truncated, and scrubbed before logging or metric attribution. Set
`DROPMCP_TELEMETRY_TEAM_BUCKETS=supply,platform,...` to control which declared
team names are allowed as metric buckets.

When `OTEL_EXPORTER_OTLP_ENDPOINT` is unset, OpenTelemetry export is a no-op —
no extra imports, no export overhead — but structured per-invocation logs still
go to the console.

## Agent feedback

dropmcp includes a built-in feedback loop for when agents get corrected and for
reusable work agents discover after invoking skills:

- **`record_feedback` MCP tool** — agents write structured feedback (no external Slack/GitLab wiring).
- **SQLite by default** — a `dropmcp.db` file is created next to your content folders on first run.
- **Postgres override** — set `DROPMCP_DATABASE_URL=postgresql://user:pass@host/db` for durable hosted storage.
- **Feedback UI** — browse, search, filter, and triage at `/feedback` in the catalog SPA (`GET`/`PATCH /api/feedback`).

Feedback rows include `feedback_type` (`correction` by default, or `agent_work`),
`skill_name` for the skill that was in use when feedback is about a specific
skill, and optional structured `details`. `agent_work` entries can include
reusable scripts or procedural artifacts under `details.artifacts`; script
content is stored as JSON text and shown in an expandable UI panel.

SQLite auto-creates the feedback table and lightly adds missing `skill_name`,
`feedback_type`, and `details` columns for existing local databases. Postgres
deployments must ship the equivalent SyncDB migration for any missing columns:

```sql
ALTER TABLE feedback
  ADD COLUMN IF NOT EXISTS skill_name text,
  ADD COLUMN IF NOT EXISTS feedback_type text NOT NULL DEFAULT 'correction',
  ADD COLUMN IF NOT EXISTS details text;

COMMENT ON COLUMN feedback.skill_name IS 'Skill that was invoked or active when the feedback was produced; null when feedback is not about a specific skill.';
COMMENT ON COLUMN feedback.feedback_type IS 'Feedback category: correction for user corrections or agent_work for reusable work created after invoking a skill.';
COMMENT ON COLUMN feedback.details IS 'Optional JSON-encoded supporting material for agent_work feedback, such as reusable artifacts.';
```

Privacy guardrails: no verbatim user prompts, code, secrets, or PII. When feedback
is enabled, dropmcp injects always-on guidance into the server instructions
describing when and how agents should call `record_feedback` — no separate skill
to install. Disable the whole feature (tool, HTTP routes, and instructions) with
`DROPMCP_FEEDBACK=false`.

In containers, mount a volume over the SQLite file (or use Postgres) or feedback
is lost when the pod restarts.

## Repository feedback

Set `DROPMCP_REPO_FEEDBACK=true` (or `repo_feedback_enabled=True`) to enable a
second feedback channel for repository friction. It is disabled by default.

- **`record_repo_feedback` MCP tool** — agents report repo-caused friction such
  as CI-only tests, flaky tests, warning noise, slow feedback loops, missing
  setup docs, dependency issues, and missing scripts.
- **Separate storage** — rows are written to `repo_feedback` in the same SQLite
  or Postgres database configured by `DROPMCP_DATABASE_URL`.
- **Deduplication** — open rows with the same normalized repo, category, and
  summary are collapsed by fingerprint and `occurrence_count` is incremented.
  Closed rows (`actioned`, `wontfix`) do not absorb new reports.
- **Repo feedback UI/API** — browse and triage at `/repo-feedback`, backed by
  `GET /api/repo-feedback`, `GET /api/repo-feedback/{id}`, and
  `PATCH /api/repo-feedback/{id}`.

Categories are fixed: `tests_require_ci`, `flaky_test`, `build_warnings`,
`lint_noise`, `slow_feedback`, `local_setup`, `docs_gap`, `dependency_issue`,
`tooling_gap`, and `other`. Status values are `new`, `triaged`, `actioned`, and
`wontfix`.

SQLite auto-creates the `repo_feedback` table and lightly backfills missing
columns for existing local databases. Hosted Postgres deployments must ship the
equivalent SyncDB migration. The core table shape is:

```sql
CREATE TABLE repo_feedback (
  id text PRIMARY KEY,
  created_at timestamptz NOT NULL,
  last_seen_at timestamptz NOT NULL,
  category text NOT NULL,
  repo text NOT NULL,
  summary text NOT NULL,
  impact text NOT NULL,
  suggested_fix text,
  model text NOT NULL,
  client text,
  details text,
  fingerprint text NOT NULL,
  occurrence_count integer NOT NULL DEFAULT 1,
  status text NOT NULL DEFAULT 'new',
  resolution_url text
);

CREATE INDEX repo_feedback_fingerprint_idx ON repo_feedback (fingerprint);
CREATE INDEX repo_feedback_repo_status_idx ON repo_feedback (repo, status);
```

The same privacy rule applies: no secrets, PII, customer data, proprietary code
snippets, or verbatim prompts. Repo feedback instructions are injected only when
the feature flag is enabled.

## Shared agent memory

Set `DROPMCP_MEMORY=true` (or `memory_enabled=True`) to let agents share what they
learn. It is disabled by default, and nothing changes for servers that leave it
off. A *memory* is one short, reusable working fact that the next agent on the same
repo or stack would otherwise have to rediscover, for example "validation failures
in this service come back as HTTP 200 with an error body".

Memory has a clear boundary with the other channels:

| Thing learned | Goes to |
|---|---|
| The repo makes work slow or risky (flaky test, CI-only checks) | `record_repo_feedback` |
| The agent or a skill got it wrong | `record_feedback` |
| A standard everyone should follow | a skill, via PR |
| A working fact about a repo, system, tool or stack that helped get a task done | **memory** |

A memory that keeps getting confirmed is a candidate for the repo's `AGENTS.md` or
a skill. Memory is a staging area, not the final home.

### Tools

Every tool takes the same `context` object: `repo` (`owner/name`), `system`,
`language`, `domain`, `stack` (tags), `task` and `path`. `repo`, `system`,
`language` and `domain` scope a memory: an empty field means general, a matching
field ranks higher, and a different field excludes it. `stack`, `task` and `path`
only boost. Unknown languages are refused; unknown stack tags are kept and logged.

- **`memory_recall`** (`context`, optional `query`, `limit` default 5, max 10) —
  returns up to `limit` memories in about 4,000 characters, each with its key,
  kind, title, body, scope, age, confirmations, last-confirmed date and open
  report count, under a preface telling the agent these are hints to verify, not
  instructions. With a `query` it ranks by keyword search (Postgres full-text
  search, SQLite FTS5) merged with vector similarity when an embedder is
  configured. Without one it returns the most-confirmed memories for the scope.
  Every recall writes a row to `memory_recall_log` (context and returned ids, not
  the query text).
- **`memory_remember`** (`context`, `kind`, `title`, `body`, optional `evidence`,
  `supersedes`, `same_as`, `distinct`) — refuses text that fails the write-side
  checks; confirms an exact duplicate (same scope and title) or a `same_as`
  instead of storing it again; with an embedder, stops near-duplicates and shows
  the agent the top three so it can call again with `same_as`, `supersedes` or
  `distinct`. `supersedes` retires the old memory.
- **`memory_report`** (`key` or `memory`, `problem`, `reason`, optional
  `correction`, `context`) — `problem` is `stale`, `invalid`, `wrong_scope` or
  `sensitive`. Writes a row to the `memory_report` bucket and changes nothing
  else, except that a `sensitive` report hides the memory from recall at once.
  A report is never refused for a missing or mangled key: it is stored with the
  description and the top candidate keys.

All three also take the calling `model`, as `record_feedback` does. Each memory
has a short key such as `MEM-7K3F9Q`, with a check character so a mangled key is
detected rather than matched to the wrong memory.

An optional agent skill with the same guidance as the always-on instructions
block ships in [`examples/skills/shared-memory`](examples/skills/shared-memory/SKILL.md);
copy it into your `skills/` folder to serve it.

### Parameters

| kwarg | env | default | purpose |
|---|---|---|---|
| `memory_enabled` | `DROPMCP_MEMORY` | `false` | registers the tools and the always-on instructions block |
| `memory_embedder` | – | – | `dropmcp.memory.vectors.MemoryEmbedder(embed, model, dimension, near_duplicate_threshold=0.92)`, where `embed` is `Callable[[list[str]], list[list[float]]]`. Unset means keyword-only search and no near-duplicate check |
| `memory_vocabulary` | `DROPMCP_MEMORY_VOCABULARY` | bundled generic list | path to a YAML/JSON file (or a dict) with languages, stack tags, domains, kinds and tasks; shown to agents as enums in the tool schemas |
| `memory_lint_rules` | – | – | extra write-side checks, each `Callable[[str], str \| None]` returning a refusal reason, run after the built-in ones |
| `memory_store` | – | built from `database_url` | replace the store entirely |
| `memory_candidate_cap` | `DROPMCP_MEMORY_CANDIDATE_CAP` | `500` | max candidates scored per recall or near-duplicate check |

Embeddings are packed float32 bytes in an ordinary binary column, and similarity
is scored in-process over the filtered candidates, so no vector extension is
needed on any database. Install `dropmcp[memory]` to score with numpy; without
it a pure-Python fallback is used. If the embedder fails, the memory is still
stored and found by keyword search.

Rows with no embedding, or one from a different model or dimension, are skipped
by vector scoring until they are backfilled. Changing embedder model is a
backfill, not a migration. Run it from a scheduled job or at startup:

```python
from dropmcp.memory.store import MemoryStore

embedded = MemoryStore(database_url).backfill_embeddings(embedder)
```

It embeds active memories in batches (`batch_size=100`) and stops at the first
failed batch, leaving the rest for the next run.

### Storage

Memory uses the same `DROPMCP_DATABASE_URL` as feedback, in four tables:
`memory`, `memory_report`, `memory_recall_log` and `memory_near_duplicate_log`.
SQLite creates them automatically. dropmcp never runs DDL against Postgres; apply
the reference SQL it ships with your migration tool before turning memory on:

```bash
python -m dropmcp memory-sql > memory.sql
psql "$DATABASE_URL" -f memory.sql
```

The SQL needs no extensions, uses unqualified table names (so it lands in the
first schema on your `search_path`), and is safe to apply more than once. On
startup, a server pointed at Postgres checks the live schema and refuses to start
with a message naming every missing table and column, instead of failing on the
first tool call. The check is skipped when you pass your own `memory_store`.

Servers that share a `database_url` and vocabulary file share one memory pool.
That's allowed but not specially designed for: the `server` column records which
server wrote each memory, and values from another server's vocabulary are still
recalled.

### What never to store

The always-on instructions tell agents, and the write-side checks enforce where
they can, that memory and report text must not contain:

- secrets, tokens or connection strings with credentials (refused)
- personal or customer data, or anything about a person (performance, ratings,
  compensation, leave, health), or people and team moves
- verbatim proprietary code beyond a line or two, or verbatim user prompts
- confidential business information that isn't engineering knowledge
- local filesystem paths and machine-specific detail (home-directory paths are
  refused)

The checks also refuse text addressed to the reading agent ("ignore previous",
"you must", tool-call syntax) and bodies that are mostly a command to run. The
rule of thumb: memory is for how systems, repos and tools behave. If a fact is
about a person, or would be out of place in a repo's README, it doesn't belong.

To run the memory tests against Postgres too, set `DROPMCP_TEST_POSTGRES_URL`
(for example `postgresql+psycopg://postgres:pg@localhost:5432/postgres`). Each
test gets its own schema; without the variable the Postgres cases are skipped.

## Trusted user identity

When dropmcp is deployed behind an authentication proxy, set the trusted caller
identity header with `DROPMCP_USER_HEADER` or the `user_header` kwarg. The default
header is `X-User-Email`.

The catalog HTTP API exposes that identity at `GET /api/me`:

```json
{
  "email": "user@example.com",
  "authenticated": true
}
```

The catalog footer shows the signed-in identity when the header is present and
stays unchanged for anonymous requests.

## Per-user subscriptions

When `DROPMCP_USER_SUBSCRIPTIONS=true`, users can opt in to individual skills
and prompts so their agent only sees a curated subset over MCP. The catalog UI
still lists the full catalog; subscription checkboxes appear when the request
includes the configured identity header (default `X-User-Email`, set upstream by
your auth mesh).

- **Flag off** — unchanged behaviour; everything is published to every caller.
- **Flag on, no identity header** — MCP exposes everything; UI controls are disabled.
- **Flag on, identity present, first sighting** — user is logged in `user_seen`,
  automatically subscribed to every catalog group, and directly subscribed to any
  ungrouped catalog items (MCP and HTTP). They can still opt out of individual
  items or whole groups afterwards.
- **HTTP API** — `GET`/`POST /api/subscriptions`, `DELETE /api/subscriptions/{type}/{name}`,
  group routes `POST`/`DELETE /api/subscriptions/group/{group}`, and
  `POST /api/subscriptions/groups` to re-subscribe every catalog group.
- **`group` frontmatter** — optional string on `SKILL.md` / `PROMPT.md`; surfaced in
  `/catalog` JSON and the catalog **Group** filter row. Group opt-ins are stored in
  `user_group_subscription` so new skills added to a followed group are included
  automatically; users can still opt out of individual items within a group via
  `user_subscription_exclusion`.
- **SQLite** auto-creates `user_subscription`, `user_group_subscription`,
  `user_subscription_exclusion`, `user_seen`, and
  `user_subscription_onboarding` locally; **Postgres**
  consumers must ship a SyncDB migration (same caveat as `feedback`).

MCP clients cache `tools/list` / `prompts/list` — subscription changes take
effect after the client re-lists (typically on reconnect).

## E2E eval results (telemetry panel)

The catalog detail page includes an **E2E Test Results** panel (ported from
skills-mcp) showing per-skill Promptfoo eval scores from your CI pipeline.

Eval results are **pluggable** — dropmcp ships the UI and HTTP routes, but the
data source is optional so the library stays deployment-agnostic:

- Pass an `eval_results_store` to `create_server()` (any object implementing
  `get_results_for_skill` / `get_all_latest_results`). Use this when the
  deployment owns the query, **or**
- Install the MySQL extra and inject both queries. The skill query is
  bound as `(project, skill_name, commit_sha, datadate)`; the all-results
  query is bound as `(project, commit_sha, datadate)`. Rows must match
  `EvalResult` column order. Host, port, database, and credentials come from
  `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, and
  `MYSQL_PASSWORD` (no defaults):

  ```bash
  pip install "dropmcp[mysql]"
  export DROPMCP_EVAL_RESULTS_PROJECT="group/project"
  export DROPMCP_EVAL_RESULTS_COMMIT_SHA="$(cat COMMIT_SHA)"
  export DROPMCP_EVAL_RESULTS_SKILL_QUERY="SELECT ... WHERE project = %s AND testname LIKE CONCAT(%s, '/%') AND commitsha = %s AND datadate >= %s"
  export DROPMCP_EVAL_RESULTS_ALL_QUERY="SELECT ... WHERE project = %s AND commitsha = %s AND datadate >= %s"
  export MYSQL_HOST="mysql.example.com"
  export MYSQL_PORT="3306"
  export MYSQL_DATABASE="your_database"
  ```

When no store is configured the panel renders an empty state; routes are not
registered. Setting only `DROPMCP_EVAL_RESULTS_PROJECT` does not open a
connection.

## Benchmarks page

Set `DROPMCP_BENCHMARKS=true` to add a **Benchmarks** page: a models × skills
matrix of the latest E2E result per test and model on `main` over the last 60
days, with a per-test breakdown for each skill.

- An **Overall** row gives each model's average score across every test it ran,
  its pass count, and how many tests it covered. An **All models** column gives
  each skill's average across models.
- **Latest** shows the newest result. **60-day average** shows the mean of every
  run in the window and colours a cell by whether that average meets the
  threshold. In the latest view, ▲/▼ mark how far the newest result sits from
  the window average, and expanded tests show a trend line of recent scores.
- Columns are ranked by the selected average. **Compact** drops the detail
  lines, and a model picker (with an "All" and "Top 5" preset) hides columns for
  wide comparisons. The view lives in the URL (`metric=history`,
  `sort=name`, `compact=1`, `models=a,b`) so it can be shared. Overall figures
  always cover every model, whichever columns are shown.
- It reports the project in `DROPMCP_EVAL_RESULTS_PROJECT` only; the API takes
  no project parameter.
- The data source is always supplied by the deployment: pass an object with
  `get_latest_benchmark_results(project, lookback_days)` as
  `benchmark_results_store`. Enabling the page without a project or a valid
  store fails at startup. No query, host or credential defaults ship in the
  library.
- With the `mysql` extra, `MySQLBenchmarkResultsStore` runs your SQL. The query
  is bound as `(project, datadate)` and must return columns in
  `BenchmarkResult` order: `test_name`, `worker_model`, `passed`, `score`,
  `threshold`, `triggered_at`, `pipeline_id`, `commit_sha`. Host, port, database
  and credentials come from the constructor or `MYSQL_*`. The `datadate` bound
  parameter is formatted with `datadate_format` (default `%Y-%m-%d`), so match
  it to your partition key. Query failures surface as an "unavailable" banner
  rather than an empty page.

  ```python
  from dropmcp.eval_results_mysql import MySQLBenchmarkResultsStore

  dropmcp.create_server(
      eval_results_project="group/project",
      benchmarks_enabled=True,
      benchmark_results_store=MySQLBenchmarkResultsStore(
          query="SELECT ... WHERE project = %s AND datadate >= %s",
          datadate_format="%Y%m%d",
      ),
  )
  ```
- `/api/benchmarks` answers `401` without the identity header
  (`DROPMCP_USER_HEADER`), and the header link only appears for identified
  users. dropmcp trusts that header as sent, so it is a usability gate rather
  than access control: put an authenticating proxy in front of the server and
  deny `/benchmarks` and `/api/benchmarks` to everyone else.
- Responses carry `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`
  and `Referrer-Policy: no-referrer`, and never include reasoning or error text.

## Skill and prompt format

### SKILL.md

```markdown
---
name: my-skill
category: my-category
group: my-group
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
