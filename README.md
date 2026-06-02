# AI Release Notes Agent

An intelligent system for automating the creation of DITA-formatted release notes from Jira tickets using AI, with seamless integration to Heretto CCMS.

## Features

- **Automated Release Notes Generation** — Extract Jira tickets and generate professional release notes
- **Multi-Provider AI Support** — Works with Anthropic Claude, OpenAI GPT, and Google Gemini
- **DITA Format Support** — Generate valid DITA 1.3 XML topics with DTD validation and auto-correction
- **Heretto CCMS Integration** — Direct publishing to your documentation platform
- **Secure Credential Management** — Encrypted storage for all API credentials, scoped per organization
- **Webhook Support** — Automated triggers from Jira events
- **Real-time Monitoring** — Track job progress with live updates
- **Modern Angular UI** — Intuitive interface built with Angular 17 and Material Design
- **SSO Support** — Google and Microsoft OAuth login

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Angular 17     │────▶│  FastAPI        │────▶│  PostgreSQL     │
│  Frontend       │     │  Backend        │     │  Database       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ├────▶ Redis (Queue)
                               ├────▶ Celery (Async Tasks)
                               ├────▶ Jira API
                               ├────▶ Anthropic / OpenAI / Gemini
                               └────▶ Heretto CCMS
```

## Prerequisites

- Docker and Docker Compose (for infrastructure)
- Python 3.12+ (for local backend development)
- Node.js 18+ and npm (for local frontend development)
- At least one AI provider API key (Anthropic, OpenAI, or Google Gemini)
- Jira instance with API access

## Local Development

The recommended way to run the application locally is `dev.sh`. It starts PostgreSQL, Redis, and Mailpit in Docker, then runs the backend and frontend directly on your machine (so you get hot-reload for both).

### 1. Clone and configure

```bash
git clone https://github.com/pboz/release-notes-agent.git
cd release-notes-agent

# Copy and fill in backend environment
cp backend/.env.example backend/.env
# Edit backend/.env — at minimum set:
#   APP_SECRET_KEY, JWT_SECRET_KEY, ENCRYPTION_KEY (any random strings for dev)
#   DATABASE_URL (already correct for the Docker Compose Postgres)
#   GOOGLE_AI_API_KEY, ANTHROPIC_API_KEY, or similar AI key
```

### 2. Set up the backend virtualenv

```bash
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 3. Run database migrations

```bash
cd backend
venv/bin/alembic upgrade head
```

> Run this once after cloning, and again whenever new migrations are added.

### 4. Set up the frontend

```bash
cd frontend
npm install
```

### 5. Start everything

```bash
# From the repo root:
./dev.sh
```

`dev.sh` starts the Docker infrastructure (Postgres, Redis, Mailpit), syncs backend dependencies, and launches both servers with live reload:

| Service  | URL                          |
|----------|------------------------------|
| Frontend | http://localhost:4200        |
| Backend  | http://localhost:8000        |
| API docs | http://localhost:8000/docs   |
| Mailpit  | http://localhost:8025        |

To stop everything: `./stop.sh` (or Ctrl+C in the `dev.sh` terminal).

### 6. Create your first user

Navigate to http://localhost:4200 and register an account.

---

## Configuration

### Environment Variables

Key variables in `backend/.env` (see `backend/.env.example` for the full list):

```env
# Application
APP_ENV=development
APP_SECRET_KEY=<random string>
JWT_SECRET_KEY=<random string>
ENCRYPTION_KEY=<random string, min 16 chars>

# Database (matches Docker Compose defaults)
DATABASE_URL=postgresql://user:password@localhost:5432/release_notes_db
REDIS_URL=redis://:devpassword@localhost:6379/0

# AI providers — add whichever you have
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_AI_API_KEY=...
# OpenAI credentials are configured per-user in the UI, not via .env

# SMTP — pre-configured for local Mailpit (no changes needed for dev)
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USE_TLS=false
SMTP_FROM_EMAIL=noreply@release-notes.local
FRONTEND_BASE_URL=http://localhost:4200
```

### Email / SMTP

In **development**, Mailpit is bundled automatically — emails (password resets, invitations) are captured at http://localhost:8025 with no external service needed.

For **production**, configure a real SMTP provider:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_USE_TLS=true
FRONTEND_BASE_URL=https://yourdomain.com
```

| Provider | SMTP Host | Port | Notes |
|---|---|---|---|
| Gmail / Google Workspace | `smtp.gmail.com` | 587 | Requires an [App Password](https://myaccount.google.com/apppasswords) |
| SendGrid | `smtp.sendgrid.net` | 587 | API key as password, `apikey` as username |
| Mailgun | `smtp.mailgun.org` | 587 | Free tier: 5,000 emails/month |
| Amazon SES | `email-smtp.us-east-1.amazonaws.com` | 587 | Region-specific host |
| Microsoft 365 | `smtp.office365.com` | 587 | Requires authenticated user |

### Authentication Modes

The application supports several authentication and organization modes that can be combined to match your deployment requirements.

---

#### Standard Mode (default)

With no additional configuration, anyone can self-register. Each new user creates their own organization and becomes its administrator.

```env
# No special configuration required
```

---

#### SSO-Only Mode

Disables the email/password registration form entirely. Users must sign in through an SSO provider (Google or Microsoft). Existing accounts created before enabling this flag are unaffected and can still log in with their password.

```env
SSO_ONLY=true
```

When enabled, the "Create Account" button is hidden in the UI and `POST /auth/register` returns `403`.

---

#### Google Sign-In

Enables the Google Sign-In button on the login page. Uses the client-side Identity Services flow — no client secret is required.

```env
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

**Setup:**
1. In [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials, open your OAuth 2.0 Client ID.
2. Under **Authorized JavaScript origins**, add your domain (e.g. `https://app.example.com`). For local testing, add `http://localhost:4200`.
3. No redirect URI is needed for this flow.

---

#### Microsoft SSO

Enables a "Continue with Microsoft" button that uses a server-side authorization code flow.

```env
MICROSOFT_OAUTH_CLIENT_ID=your-client-id
MICROSOFT_OAUTH_CLIENT_SECRET=your-client-secret
MICROSOFT_OAUTH_TENANT_ID=common          # or your specific tenant ID
OAUTH_REDIRECT_BASE_URL=https://app.example.com
```

**Setup:**
1. In [Azure Portal](https://portal.azure.com) → App registrations → your app → Authentication.
2. Add a redirect URI (Web platform): `https://app.example.com/api/v1/auth/sso/microsoft/callback`.
3. For local testing: `http://localhost:8000/api/v1/auth/sso/microsoft/callback`.

`OAUTH_REDIRECT_BASE_URL` tells the backend which base URL to use when constructing the callback URL. It must match the origin registered in Azure.

---

#### Single-Organization Mode (recommended for production use)

Routes all new users into a single pre-existing organization instead of letting each user create their own. New users are added as **members** (not admins). Intended for company-internal deployments where there is one shared workspace.

```env
SINGLE_ORG_MODE=true
SINGLE_ORG_SLUG=your-org-slug
```

`SINGLE_ORG_SLUG` must match the `slug` column of an existing organization in the database. To find it:

```bash
docker compose -f docker-compose.production.yml exec postgres \
  psql -U produser -d release_notes_production \
  -c "SELECT slug, name FROM organizations;"
```

When enabled:
- The Organization Name field is hidden during registration (the user has no org to name).
- Both password registration and SSO new-user creation add the user to the default org.
- Users who already have accounts are unaffected.

---

#### Domain-Restricted Registration

Restricts new account creation to specific email domains. Applies to both password registration and SSO. Useful when combined with single-organization mode to ensure only company employees can join.

```env
ALLOWED_EMAIL_DOMAINS=example.com,contractor.io
```

- Multiple domains are separated by commas.
- The check is case-insensitive.
- Users with existing accounts can always log in regardless of their domain.
- If unset or empty, all domains are permitted.

Returns `403` for registration attempts from non-listed domains.

---

#### Recommended Production Configurations

**Internal company tool (SSO + single org + domain lock):**
```env
SSO_ONLY=true
GOOGLE_OAUTH_CLIENT_ID=...
SINGLE_ORG_MODE=true
SINGLE_ORG_SLUG=acme-corp
ALLOWED_EMAIL_DOMAINS=acme.com
```

**SaaS / multi-tenant (default behaviour, no changes needed):**
```env
# Each user self-registers and creates their own organization.
```

**SSO-preferred but password login still allowed:**
```env
GOOGLE_OAUTH_CLIENT_ID=...
# SSO_ONLY is not set — password registration and login both still work.
```

---

### First-Time Setup (UI)

1. **Add Credentials** — Settings → Credentials → add Jira, AI provider, and optionally Heretto credentials
2. **Create Instruction Sets** — Settings → Instructions → define system prompts and JQL query templates
3. **Create Your First Job** — Jobs → New Job → enter a JQL query, select an instruction set, run

### Updating a Production System

When updating a production system running Docker behind Nginx (standard production setup), use the restart script:

```bash
git pull
sudo deployment/restart.sh
```

---

## Running Tests

Tests require the dev environment to be running (`./dev.sh`).

```bash
cd tests
python3 run_tests.py
```

To skip cleanup of test data:

```bash
python3 run_tests.py --no-cleanup
```

Integration tests (Jira, Heretto, AI providers) are skipped automatically if the corresponding credentials are absent from the root `.env`. See `tests/config.py` for the variable names.

**Running a specific test file:**

```bash
python3 run_tests.py --test api/test_credentials.py
```

**Running the pytest unit tests directly** (no running server needed):

```bash
cd backend
venv/bin/python -m pytest tests/unit/ -v
```

---

## API Documentation

The FastAPI backend provides automatic API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Key endpoints:
- `POST /api/v1/auth/login` — User authentication
- `POST /api/v1/jobs` — Create release notes job
- `GET /api/v1/jobs/{id}` — Get job status
- `POST /api/v1/webhooks/jira` — Jira webhook receiver

## Webhook Configuration

### Setting up Jira Webhooks

1. In Jira, go to System → Webhooks
2. Create a new webhook with URL: `https://your-domain.com/api/v1/webhooks/jira`
3. Select events to trigger (e.g., "Version Released")
4. Copy the webhook secret to your application settings

All incoming webhooks are verified using HMAC signatures.

---

## Deployment

### Production Deployment with Docker

1. Copy and configure the production environment file:
   ```bash
   cp .env.production.example .env.production
   # Edit .env.production with your secrets and SMTP configuration
   ```

2. Deploy using the provided script:
   ```bash
   ./deployment/deploy.sh
   ```
   This builds Docker images, runs database migrations, and starts all services.

### Deploying to Google Cloud Platform

A full GCP deployment guide is available at [`deployment/GCP_DEPLOYMENT_GUIDE.md`](deployment/GCP_DEPLOYMENT_GUIDE.md).

**Automated setup:**

```bash
./deployment/quick-deploy-gcp.sh
```

This interactively creates a Compute Engine VM, firewall rules, and a static IP.

**Manual setup summary:**

1. Create a Compute Engine VM (e2-standard-2 recommended, ~$50/month)
2. SSH into the VM and clone the repository
3. Configure `.env.production` with your secrets (including `DOMAIN` and SMTP settings)
4. Run `./deployment/deploy.sh`

SSL is provisioned automatically during the first deploy — the script requests a Let's Encrypt certificate for the domain specified in `DOMAIN` and sets up auto-renewal via cron.

### Deployment Scripts

| Script | Purpose |
|--------|---------|
| `deploy.sh` | Build, migrate, and start all production services |
| `quick-deploy-gcp.sh` | Automated GCP VM provisioning |
| `setup-ssl.sh` | SSL/TLS certificate setup with Let's Encrypt |
| `backup.sh` | Database backup (retains 30, optional GCS upload) |
| `health-check.sh` | Container, disk, and memory monitoring with Slack/email alerts |
| `startup-script.sh` | GCP VM bootstrap (Docker, firewall, fail2ban, swap) |

---

## Troubleshooting

**Issue: `venv/bin/alembic upgrade head` fails with "connection refused"**
- Make sure Postgres is running: `docker compose up -d postgres`

**Issue: Backend starts but login returns 500**
- Postgres may not be running, or `DATABASE_URL` in `backend/.env` doesn't match the Docker Compose database config

**Issue: Password reset emails not arriving in Mailpit**
- Ensure `SMTP_HOST=localhost` and `SMTP_PORT=1025` are set in `backend/.env`

**Issue: Jobs failing with "No Jira credentials found"**
- Add Jira credentials in Settings → Credentials

**Issue: DITA validation errors in job output**
- Check the artifact content in the job detail view; the auto-correction loop will retry up to 3 times before failing

**Issue: 500 error when going to the application URL**
- Nginx may be disconnected from the frontend — in some cases this is an SSL certificate issue. Diagnose with `docker compose logs nginx` and check certificate expiry

**Viewing logs (Docker Compose production setup):**
```bash
docker compose logs backend
docker compose logs celery-worker
docker compose logs postgres
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes
4. Push to the branch and open a Pull Request

## License

This project is licensed under the MIT License — see the LICENSE file for details.
