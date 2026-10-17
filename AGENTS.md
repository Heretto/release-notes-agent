# release-notes-agent — agent notes

Built on [hop-core](https://github.com/Heretto/hop-core), pinned at **v0.1.16**.

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
note's history), the fragment shape (a note stores **content**, and assembly wraps it), and the chat tools. Backend entry points: `app/services/release_notes_pipeline.py`
(stages), `workspace_service.py` (assembly, history, publishing, response shapes),
`workspace_chat.py` (agent tools), `topic_assembler.py` (fragment validation and chunking).
`tests/integration/test_pipeline_with_fakes.py` runs the whole pipeline against the local
Postgres with fake Jira and fake agents; keep it green when touching the stages.

**Guidance reaches two stages, and only governs one note at a time.**
`organization_guidance` goes to the organize stage (group names and order) *and*, since the
writer is what actually writes the words, to the writer and the workspace chat agent via
`pipeline_prompts.house_style()`. It used to reach only the organize stage, so anyone who
wrote their house style in that box — note prefixes, tense, which elements to use — saw no
change in the output and reasonably reported the guidance as ignored. The block scopes
itself on the way in: the writer is told to follow every rule about **this note** and to
ignore rules about the topic around it. That is not politeness — a writer told to emit
`<title>`, `<shortdesc>` or `<ul>` wrappers returns a fragment that fails DTD validation and
the note silently falls back to its plain summary. Topic-level structure is `topic_assembler.build_topic_xml`, and it is
configured per instruction set by `instruction_sets.layout` (`schemas.TopicLayout`): a note
stores **content**, and the layout decides the element around it — a `<section>` with a
title or a bold paragraph per group, its notes loose or collected in a `<ul>`/`<ol>`, each
note a `<div>` or an `<li>`, and what the `<shortdesc>` does. `layout.mode` picks who owns the structure — **structured** (the
options above), **template** (a DITA topic the writer authors, with `outputclass="rn-group"`
marking what repeats per group and `rn-notes` marking where notes go; the notes host's tag
decides whether a note is an `<li>` or a `<div>`, and both markers are stripped from the
output), or **agent** (the structure described in words). Each mode keeps its own settings,
so switching back does not lose the other. Agent mode resolves to a template **once per
run** — `_settle_topic_structure` writes it to `jobs.topic_template` and every later
assembly of that release reuses it. That is deliberate: assembly also runs inside request
handlers (a topic-split change, a note edit), and nothing there may call a model. A release
assembled before its first run, or whose agent failed, falls back to the structured options
rather than producing no topic.
What a note *is* follows from what collects it and is not a free choice: a `<ul>`/`<ol>`
may only contain `<li>`, and an `<li>` may only live in a list. The editor offers only the
valid element, the schema refuses a mismatched pair, and `note_element_for()` derives the
element at assembly time rather than trusting the stored one — so a hand-edited row cannot
put a `<div>` inside a `<ul>` and fail every topic's DTD check. Whatever that element is, assembly
stamps it with the note's `fragment_id` and `outputclass="release-note"` — the workspace
preview maps rendered DITA back to a note through exactly that pair, so every layout mode
must keep doing it.

**Instruction sets name agents by role** (`writer_agent_id`, `analysis_agent_id`), not an
ordered chain; the `instruction_set_agents` table is gone (migration
`add_collaborative_workflow` moved the first chain agent into the writer slot).

**The instruction-set editor is a page, not a dialog** (`/instructions/new`,
`/instructions/:id`). It outgrew a modal once it carried the query and its variables, the
agents, two kinds of guidance and the topic layout. The page owns persistence — the list
used to save after the dialog closed, which cannot work for a route someone may open
directly — and a duplicate travels in navigation state rather than by id, because a copy
does not have one yet. The form is built empty and rebuilt when the set arrives, so any
rule that keeps controls in step belongs in `wireFormRules()`: a subscription made in
`ngOnInit` would attach to the form the load then replaces.

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

**Migrations run themselves, from a one-shot `migrate` service.** `docker compose up` starts
`backend` (and in dev `celery-worker`) only after `migrate` exits 0, so a deploy never needs a
manual `alembic upgrade head` and never serves traffic against a schema the code does not
match. The work is in `backend/scripts/startup_migrate.py` rather than an entrypoint because
those services share one image, and two containers running DDL at once half-applies a
migration. It handles three cases, mirroring `install.sh`: an empty database gets
`create_all()` + `stamp head` (this project's baseline schema is **not** built by Alembic —
the migrations are incremental patches on top, so replaying them over current-shape tables
fails); a stamped database gets `upgrade head`; a database with tables but no
`alembic_version` is **refused**, because neither stamping nor upgrading is safe to guess;
and an `alembic_version` holding several revisions when the graph has one head is
**refused** too — that table is corrupted, and Alembic's own message for it ("requested
revision X overlaps with other requested revisions Y") names neither the stale row nor the
fix. `dev.sh` runs the same script before starting uvicorn, so a host run migrates itself
as well. Running Alembic by hand (`backend/venv/bin/alembic upgrade head`) still works and
is the right tool for a repair, but is no longer a step anyone has to remember.

**`create_all()` runs on every backend start**, not just the first one — it is in hop-core's
`create_hop_app` lifespan. It creates a missing *table* and never alters an existing one, so
it silently re-creates a table a migration dropped while the model still exists, and it does
nothing at all for a column a migration adds. That is why a migration that creates a new ORM
table needs an "already there?" guard (`add_item_review`, `add_instruction_set_agents`) and
why the backend must not start before the migration has run.

**Three environment files, not interchangeable.** `backend/.env` for host runs (uvicorn,
celery, alembic — it carries localhost `DATABASE_URL`/`REDIS_URL`); the repository-root
`.env` for `docker compose` variable substitution; `.env.production` for production compose.
Each has a committed `.example` alongside it. `ENCRYPTION_KEY` derives the Fernet cipher for
stored credentials and **cannot be rotated** — changing it orphans every encrypted row.

**Start the stack.** `./install.sh` for first-time setup, `./dev.sh` afterwards (starts
Postgres/Redis/Mailpit in Docker and runs both servers with live reload). `./reset.sh` wipes
local state.

**Credentials are entirely hop-core's.** `register_builtin_types("jira", "heretto",
"anthropic", "openai", "gemini")` in `app/models/database.py` is the whole registration: it
brings the field specs the generic UI renders forms from, the connection testers behind the
Test button, and the `AiProviderRegistry` generators `AgentRunner` needs. The API is
hop-core's generic `/credentials` router (`include_credentials_router` left at its default)
and the page is `HopCredentialsComponent`. Do not add a per-type route or dialog back: this
app used to carry ~3,400 lines of both, and the duplication is what let the AI dialog offer a
`custom` provider the backend's regex rejected. `core/services/credentials.service.ts` is a
thin adapter over `HopCredentialService` for the one picker that lives outside that page (an
instruction set's Jira connection); it holds no CRUD. Payload keys match hop-core's specs
(`api_key`/`model`, `server_url`/`email`/`api_token`, `server_url`/`username`/`token`), so
credentials stored by the old routes keep working.

### Worked out the hard way — do not "fix" these back

- **Health lives outside `api_prefix`**, at `/health` and `/health/db`, mounted directly on
  the app rather than through `create_hop_app(extra_routers=...)`. Everything under the
  prefix expects authentication, and a probe has no credentials to offer.
- **`backend/Dockerfile` installs `git`.** The hop-core pin is a `git+https://` URL, so pip
  shells out to git at image build time. `python:3.11-slim` does not ship it.
- **One Celery worker.** No distributed lock; a second replica would double-run jobs.
- **A Jira webhook is addressed to one configuration and signed with that configuration's
  own secret** (`POST /webhooks/jira/{config_id}`). `webhook_configs.secret_token` had been
  generated and returned since the feature shipped but never actually verified: the old
  shared `/webhooks/jira` checked one deployment-wide secret and then fanned the event out
  to **every** organization's active configurations, so one secret could start runs — and
  spend credentials — in an organization its holder had no account in. That endpoint still
  exists for single-organization deployments mid-migration and **refuses outright once a
  second organization has an active configuration**. The issue key in a webhook body is
  checked against Jira's key shape and injected as a quoted literal, like every other
  untrusted value that reaches JQL; it used to be interpolated raw.
- **An instruction set has two sources, and only one of its query fields is required.**
  `source_mode = 'jql'` means `jql_query` is the template; `source_mode = 'releases'` means
  the query is built per Jira fix version from `jira_project` and `extra_jql` and
  `jql_query` is unused (stored as `''`). The requirement moves with the mode — enforced by
  a model validator in `InstructionSetBase` and by swapping the Angular validators in
  `instruction-dialog.component.ts` — so do not put `min_length=1` back on `jql_query`.
  Release lists are read live from Jira (`GET /instructions/{id}/releases`), never stored:
  a cached list would offer a version that no longer exists. That endpoint is paginated
  (`start_at`/`max_results`, five then ten at a time) and goes to Jira's **`/project/{key}/version`**
  — singular, paginated. Its unpaginated `/versions` sibling accepts `expand=issuesstatus`
  but does not reliably return the counts, which is why every release once read "0 issues";
  `_fill_issue_counts` falls back to `/version/{id}/relatedIssueCounts` per version, which
  is only affordable because the list is a page.
- **Review is a separate axis from `status`, not a stage of it.** `status` (draft → review →
  approved) is where a note sits in the writer's flow; `reviewer_id`/`reviewed` are one
  person's answer to "have you read this?". A note can be approved with nobody having
  reviewed it, or reviewed while still a draft — do not collapse the two. Review access is
  "signed in and in this organization", enforced by the API on every call; `/releases/:id/review`
  is a plain route with no token, so the Share-for-review link is just that URL.
  `PATCH /jobs/{id}/items/{item}` skips the idle check when the only fields sent are
  `reviewer_id`/`reviewed`, and commenting and resolving a comment skip it too: none of
  them touch anything a run writes, and refusing them would break the review page every
  time the writer reruns. **Approving is not in that set** — it is a status change, and the
  pipeline writes `status` too, so it still needs an idle job.
  `approved_by_id`/`approved_at` travel with the status: set on the way into `approved`,
  cleared on the way out, since "approved by X" about a note that is now a draft is a lie.
  Notes approved before those columns existed show a plain "Approved" with no name.
  **Resolving is not deleting** —
  the comment stays readable, so what was asked for survives next to the change that
  answered it. "Ask the agent" in the Details pane hands a comment to the writer agent by
  sending it into the workspace chat (`chatPending` → the chat's `pendingMessage`), rather
  than calling the agent behind the scenes, so what was asked and what the agent did sit in
  one transcript the person can read and undo.
- **A rerun re-reads the instruction set, including its query.** Everything the pipeline
  needs — agents, guidance, the Jira credential, publish settings — it already loads live
  from `job.instruction_set`, so an edit to the set reaches the next run on its own. The
  one exception was `jobs.jql_query`, resolved once when the release was started;
  `_queue_run` now rebuilds it through `jql_variables.query_for_job`. That deliberately
  leaves the stored query alone in three cases: `uses_instruction_query` is false (the
  caller supplied its own query — the column exists exactly to protect it, and the
  migration backfilled it by comparing each job's query with its set's template rather
  than guessing a default), the set is gone, or the template now needs a variable the
  release has no value for. The last is where **Edit release** comes in — it is the only
  place a started release's variables, release choice, filename, topic split, cap and
  publish settings can be changed, and it is refused while a run is in progress.
- **JQL variables resolve on the server, never in the browser.** An instruction set's
  `jql_query` is a template whose `{name}` tokens a release fills in. The browser splits the
  template only to *display* it (`frontend/src/app/core/jql-variables.ts`); the query that
  runs is built by `backend/app/services/jql_variables.py`, which injects every value as one
  quoted JQL literal. That is what stops a value like `1.0" OR project = "SECRET` from
  rewriting the query and reading another project's issues — a plain string replace, which is
  what the design prototype does, does not. The start dialog and the test dialog both send
  values and let the server substitute; neither sends a built query.
- **Do not pass `temperature` to agents.** Several Anthropic models reject it with HTTP 400
  ("temperature is deprecated for this model"); the pipeline and the workspace chat leave it
  unset and take the provider default. `tests/unit/services/test_anthropic_temperature.py`
  covers the older adapter's fallback for the same reason.
- **hop-core's Heretto browser picks a *file*; publishing needs a *folder*.**
  `openHerettoFileBrowser` only ever returns a `HerettoFile`, so
  `shared/heretto-folder-picker.component.ts` navigates with the same `HopHerettoService`
  and types and returns the folder you are standing in. It is ours only because hop-core
  has no folder mode — if one appears, delete this and use it. The picker needs
  `include_heretto_router` (hop-core's default, on).
  A folder chosen when publishing from the workspace applies to **that publish only** and
  is never stored: a one-off destination that quietly became the default is how notes end
  up somewhere nobody expects on the next run.
- **An organization can bring its own DITA grammar, and this app validates against it.**
  `create_hop_app(include_dtd_sets_router=True)` mounts `/dtd-sets`; hop-ui's admin page
  already contains the DTD sets section and **probes that endpoint to decide whether to show
  itself**, so leaving the router off (its default) silently hides the feature rather than
  erroring. Uploads live in the database, so there is nothing to configure. Validation then
  has to *use* the set: every validator comes from `hop_core.dtd_sets.validator_for(db,
  organization_id, agent_id)`, which resolves the agent's choice, then the organization
  default, then the bundled OASIS grammar — a bare `DitaValidator()` ignores an uploaded set
  and silently validates against the wrong grammar. Request handlers resolve it per request
  (`jobs._validator_for`), because an admin can change the set between two saves.
- **DITA validates against the full technicalContent shells as of hop-core v0.1.16** —
  `hop_core/dita/grammar.py` maps `topic` to `dtd/technicalContent/dtd/topic.dtd` and gives
  xmllint a catalog and an entity-amplification profile. Until v0.1.14 a `<topic>` was
  validated against the *base* DTD, which declares none of the technical-content domains, so
  `<codeph>`, `<codeblock>`, `<uicontrol>` and `<filepath>` were rejected as invalid and
  `pipeline_prompts.FRAGMENT_FORMAT` told the writer to avoid them. They validate now.
  A fragment that still fails the DTD is retried once with the errors and then falls back to
  the plain summary, flagged for attention.
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

Pinned at **v0.1.16**. v0.1.16 removed `DitaValidator._XMLLINT_DTD_FILES` (the grammar moved
to `hop_core/dita/grammar.py`), so anything that subclassed it to redirect a DTD breaks at
import — check for that before upgrading again.

Resolve the current release (hop-core `AGENTS.md`, Step 0 — do not copy a version out of any
document, including this one), bump the Python requirement in `backend/requirements.txt` and
`backend/requirements-dev.txt` and the `@heretto/hop-ui` asset URL in `frontend/package.json`
**together**, regenerate the npm lock, **recreate `backend/venv`** (pip will not swap a git
URL in place on an existing install), rebuild, then re-run `hop-doctor`.
