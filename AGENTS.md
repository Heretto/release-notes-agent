# release-notes-agent — agent notes

Built on [hop-core](https://github.com/Heretto/hop-core), pinned at **v0.1.3**.

Automated DITA release-notes generation from Jira tickets: FastAPI backend, Angular 19
frontend, Celery workers, Postgres, Redis.

## Before changing anything

Run `hop-doctor` (installed with hop-core, via `backend/venv/bin/hop-doctor`). It audits this
project's hop-core integration and exits non-zero on real problems.

## hop-core references — a different repository, not loaded here

- Integration rules, failure modes, upgrade steps: hop-core [`AGENTS.md`](https://github.com/Heretto/hop-core/blob/main/AGENTS.md)
- Design system, components, tokens, app skeleton: hop-core [`DESIGN-SYSTEM.md`](https://github.com/Heretto/hop-core/blob/main/DESIGN-SYSTEM.md)

Read those instead of inferring from this project's code. Do not copy them here.

## What is specific to this project

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
- **The alembic filter deliberately deviates from hop-core AGENTS.md §6.** The published
  recipe unions in bare `Table` objects found in the models namespace; here that would pull
  in hop-core's `user_organizations` association table (imported into
  `app/models/database.py`) and let autogenerate write migrations against a hop-core table.
  `backend/alembic/env.py` derives `OUR_TABLES` from mappers only. The reasoning is in a
  comment there — read it before changing the filter.
- **The production frontend build fails its 1 MB `initial` bundle budget** (~1.14 MB). This
  is not caused by anything in this repo: an eager `hopAuthInterceptor` import pins the whole
  flat `@heretto/hop-ui` bundle and its Angular Material tree into the initial chunk, and
  hop-ui has no secondary entry points to split it. `docker compose build frontend` fails on
  this. Open upstream.

## Upgrading hop-core

Resolve the current release (hop-core `AGENTS.md`, Step 0 — do not copy a version out of any
document, including this one), bump the Python requirement in `backend/requirements.txt` and
`backend/requirements-dev.txt` and the `@heretto/hop-ui` asset URL in `frontend/package.json`
**together**, regenerate the npm lock, **recreate `backend/venv`** (pip will not swap a git
URL in place on an existing install), rebuild, then re-run `hop-doctor`.
