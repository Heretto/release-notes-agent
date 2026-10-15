# release-notes-agent — agent notes

Built on [hop-core](https://github.com/Heretto/hop-core), pinned at **v0.1.14**.

Automated DITA release-notes generation from Jira tickets: FastAPI backend, Angular 22
frontend, Celery workers, Postgres, Redis.

**Node ^22.22.3 || ^24.15.0 || >=26 is required** — Angular 22's engine constraint. A plain
major-version check is not enough: Node 22.22.1 satisfies "Node 22" and still fails the build.

## Before changing anything

Run `hop-doctor` (installed with hop-core, via `backend/venv/bin/hop-doctor`). It audits this
project's hop-core integration and exits non-zero on real problems.

## hop-core references — a different repository, not loaded here

- Integration rules, failure modes, upgrade steps: hop-core [`AGENTS.md`](https://github.com/Heretto/hop-core/blob/main/AGENTS.md)
- Design system, components, tokens, app skeleton: hop-core [`DESIGN-SYSTEM.md`](https://github.com/Heretto/hop-core/blob/main/DESIGN-SYSTEM.md)

Read those instead of inferring from this project's code. Do not copy them here.

## What is specific to this project

**The job is a collaborative release, not a one-shot file.** A run snapshots the Jira issues,
evaluates them, consolidates and organizes release note items, writes one DITA fragment per
item, and assembles topics; a person then finishes the notes in the workspace
(`/jobs/:id/workspace`) with the writer agent in chat. `docs/COLLABORATIVE_WORKFLOW.md` is the
map: pipeline stages, rerun semantics (unchanged issues keep their notes; changes go to each
note's history), the fragment shape (`<div outputclass="release-note">` inside group
`<section>`s), and the chat tools. Backend entry points: `app/services/release_notes_pipeline.py`
(stages), `workspace_service.py` (assembly, history, publishing, response shapes),
`workspace_chat.py` (agent tools), `topic_assembler.py` (fragment validation and chunking).
`tests/integration/test_pipeline_with_fakes.py` runs the whole pipeline against the local
Postgres with fake Jira and fake agents; keep it green when touching the stages.

**Instruction sets name agents by role** (`writer_agent_id`, `analysis_agent_id`), not an
ordered chain; the `instruction_set_agents` table is gone (migration
`add_collaborative_workflow` moved the first chain agent into the writer slot).

**A job is a "Release" in the UI, a `job` in the API.** The nav item, headings and copy all
say Releases, and the routes are `/releases`, `/releases/:id`, `/releases/:id/workspace` (the
old `/jobs/...` paths redirect). The REST API, the `Job` model and the service/table names are
deliberately unchanged — renaming them would be a breaking API change for no user-visible gain.

**A note's `notes` field is free text, and is never published.** It holds a person's own
context, open questions and links; URLs in it are linked on render. It replaced a structured
`release_note_item_references` table (migration `add_item_notes_drop_references` folded each
item's links into its notes, one per line, then dropped the table). Editing it records a
`notes_edited` history entry but deliberately does **not** reassemble topics — notes never
reach the assembled DITA.

**Three environment files, not interchangeable.** `backend/.env` for host runs (uvicorn,
celery, alembic — it carries localhost `DATABASE_URL`/`REDIS_URL`); the repository-root
`.env` for `docker compose` variable substitution; `.env.production` for production compose.
Each has a committed `.example` alongside it. `ENCRYPTION_KEY` derives the Fernet cipher for
stored credentials and **cannot be rotated** — changing it orphans every encrypted row.

**Start the stack.** `./install.sh` for first-time setup, `./dev.sh` afterwards (starts
Postgres/Redis/Mailpit in Docker and runs both servers with live reload). `./reset.sh` wipes
local state.

### Worked out the hard way — do not "fix" these back

- **Health lives outside `api_prefix`**, at `/health` and `/health/db`, mounted directly on
  the app rather than through `create_hop_app(extra_routers=...)`. Everything under the
  prefix expects authentication, and a probe has no credentials to offer.
- **`backend/Dockerfile` installs `git`.** The hop-core pin is a `git+https://` URL, so pip
  shells out to git at image build time. `python:3.11-slim` does not ship it.
- **One Celery worker.** No distributed lock; a second replica would double-run jobs.
- **Do not pass `temperature` to agents.** Several Anthropic models reject it with HTTP 400
  ("temperature is deprecated for this model"); the pipeline and the workspace chat leave it
  unset and take the provider default. `tests/unit/services/test_anthropic_temperature.py`
  covers the older adapter's fallback for the same reason.
- **The bundled DITA 1.3 DTD (hop-core `topic.dtd`) does not declare `<codeph>`, `<codeblock>`,
  `<uicontrol>` or `<filepath>`.** The writer's format rules (`pipeline_prompts.FRAGMENT_FORMAT`)
  list only elements that validate (`<tt>`, `<pre>`, `<note>`, `<dl>`, `<simpletable>`, …); a
  fragment that fails the DTD is retried once with the errors and then falls back to the plain
  summary, flagged for attention.
- **Jobs run in the API process via `BackgroundTasks` with their own session** (`JobOrchestrator()`
  without a `db`): a request-scoped session is closed before a background task runs on this
  FastAPI version's successor, so never hand one in from a route.
- **The alembic filter deliberately deviates from hop-core AGENTS.md §6.** The published
  recipe unions in bare `Table` objects found in the models namespace; here that would pull
  in hop-core's `user_organizations` association table (imported into
  `app/models/database.py`) and let autogenerate write migrations against a hop-core table.
  `backend/alembic/env.py` derives `OUR_TABLES` from mappers only. The reasoning is in a
  comment there — read it before changing the filter.
- **The `initial` bundle budget is deliberately 2 MB, not Angular's default 1 MB.** The real
  bundle is ~1.39 MB (was ~1.36 MB on v0.1.8 / Angular 22, ~1.14 MB on v0.1.4 / Angular 19),
  and nothing in this repo can shrink it: an eager `hopAuthInterceptor` import pins the whole
  flat `@heretto/hop-ui` bundle and its Angular Material tree into the initial chunk, and
  hop-ui has no secondary entry points to split it. At the default budget `ng build` — and so
  `docker compose build frontend`, since `ng build` defaults to the production configuration —
  failed outright, which blocked server deploys. The budget was raised rather than removed, so
  a genuine regression still trips it. Root cause is open upstream; drop the budget back when
  hop-ui ships entry points.
- **`frontend/Dockerfile` must stay on a Node that satisfies Angular 22** (`^22.22.3 ||
  ^24.15.0 || >=26`). It sat on `node:18-alpine` after the Angular 22 upgrade and every image
  build died with "The Angular CLI requires a minimum Node.js version of v22.22.3...". The
  `install.sh` check and `package.json` engines field do **not** cover the image build.
- **`npm audit` reports ~11 high findings in the frontend. Do NOT run `npm audit fix
  --force`** — it "fixes" them by installing `karma@4.0.0`, a two-major downgrade that breaks
  the test setup and resolves nothing real. Every package in the report is a
  `devDependency` (`karma*`, `jasmine*`, `@angular-devkit/build-angular`), so none of it
  reaches the shipped bundle. Both branches have one root, and it is tooling Angular 22 has
  already deprecated: `braces` → `chokidar` → **karma**, and `micromatch` →
  `http-proxy-middleware` → `webpack-dev-server` → **`@angular-devkit/build-angular`**. The
  real fix is the two optional Angular 22 migrations, deliberately deferred so the v0.1.8
  upgrade stayed reviewable — they delete the vulnerable subtrees rather than patching them:
  `ng update @angular/cli --name use-application-builder` (also clears the
  `@angular-devkit/build-angular:dev-server is deprecated` warning on every `dev.sh` run) and
  `ng update @angular/cli --name migrate-karma-to-vitest`.

## Upgrading hop-core

Resolve the current release (hop-core `AGENTS.md`, Step 0 — do not copy a version out of any
document, including this one), bump the Python requirement in `backend/requirements.txt` and
`backend/requirements-dev.txt` and the `@heretto/hop-ui` asset URL in `frontend/package.json`
**together**, regenerate the npm lock, **recreate `backend/venv`** (pip will not swap a git
URL in place on an existing install), rebuild, then re-run `hop-doctor`.
