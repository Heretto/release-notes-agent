#!/usr/bin/env bash
# install.sh — first-time local development setup.
#
# Safe to re-run: skips steps that are already complete.
#
# What this does:
#   1. Checks prerequisites (Docker, Python 3.12+, Node 18+)
#   2. Creates backend/.env with secure random keys
#   3. Creates the backend Python virtualenv and installs dependencies
#   4. Starts Docker infrastructure (Postgres, Redis, Mailpit)
#   5. Creates the database schema and stamps Alembic
#   6. Installs frontend npm dependencies
#   7. Offers to launch dev.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

# ── Helpers ───────────────────────────────────────────────────────────────────
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
step()   { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }

fail() { red "✗ $*"; exit 1; }

# ── 1. Prerequisites ──────────────────────────────────────────────────────────
step "Checking prerequisites"

# Docker
if ! command -v docker &>/dev/null; then
  fail "Docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
fi
if ! docker info &>/dev/null; then
  fail "Docker daemon is not running. Start Docker Desktop and try again."
fi
green "  ✓ Docker $(docker --version | awk '{print $3}' | tr -d ',')"

# Python 3.12+
PYTHON=""
for candidate in python3.13 python3.12 python3; do
  if command -v "$candidate" &>/dev/null; then
    ver=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    major="${ver%%.*}"
    minor="${ver##*.}"
    if [[ "$major" -ge 3 && "$minor" -ge 12 ]]; then
      PYTHON="$candidate"
      break
    fi
  fi
done
if [[ -z "$PYTHON" ]]; then
  fail "Python 3.12+ not found. Install from https://www.python.org/downloads/"
fi
green "  ✓ Python $($PYTHON --version)"

# Node 18+
if ! command -v node &>/dev/null; then
  fail "Node.js not found. Install from https://nodejs.org/ (v18 or later)"
fi
node_major=$(node --version | tr -d 'v' | cut -d. -f1)
if [[ "$node_major" -lt 18 ]]; then
  fail "Node.js 18+ required (found $(node --version)). Upgrade at https://nodejs.org/"
fi
green "  ✓ Node $(node --version)"

# hop-core (sibling repo)
HOP_CORE_DIR="$(dirname "$ROOT_DIR")/hop-core"
if [[ ! -d "$HOP_CORE_DIR" ]]; then
  fail "hop-core not found at $HOP_CORE_DIR
  Clone it first: git clone https://github.com/heretto/hop-core.git \"$HOP_CORE_DIR\""
fi
green "  ✓ hop-core found at $HOP_CORE_DIR"

# ── 2. backend/.env ───────────────────────────────────────────────────────────
step "Configuring backend environment"

ENV_FILE="$BACKEND_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  yellow "  ↩ backend/.env already exists — skipping"
else
  cp "$BACKEND_DIR/.env.example" "$ENV_FILE"

  # Generate secure random keys
  APP_SECRET=$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe(32))")
  JWT_SECRET=$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe(32))")
  ENC_KEY=$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe(32))")

  # Replace placeholder values in .env
  sed -i.bak \
    -e "s|your-secret-key-change-in-production|$APP_SECRET|" \
    -e "s|your-jwt-secret-key-change-in-production|$JWT_SECRET|" \
    -e "s|your-encryption-key-change-in-production|$ENC_KEY|" \
    "$ENV_FILE"
  rm -f "$ENV_FILE.bak"

  green "  ✓ backend/.env created with generated secret keys"
  yellow ""
  yellow "  ┌─────────────────────────────────────────────────────────────┐"
  yellow "  │  Optional: add your AI API key(s) to backend/.env now       │"
  yellow "  │                                                             │"
  yellow "  │  ANTHROPIC_API_KEY=sk-ant-...                               │"
  yellow "  │  GOOGLE_AI_API_KEY=...                                      │"
  yellow "  │                                                             │"
  yellow "  │  You can also add them later via Settings → Credentials.   │"
  yellow "  └─────────────────────────────────────────────────────────────┘"
fi

# ── 3. Backend virtualenv ─────────────────────────────────────────────────────
step "Setting up backend Python environment"

VENV_DIR="$BACKEND_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python"

if [[ -f "$VENV_PYTHON" ]]; then
  yellow "  ↩ venv already exists — syncing dependencies"
else
  "$PYTHON" -m venv "$VENV_DIR"
  green "  ✓ Virtualenv created"
fi

"$VENV_DIR/bin/pip" install -q --disable-pip-version-check -r "$BACKEND_DIR/requirements.txt"
green "  ✓ Backend dependencies installed"

# ── 4. Docker infrastructure ──────────────────────────────────────────────────
step "Starting Docker infrastructure"

docker compose -f "$ROOT_DIR/docker-compose.yml" up -d --wait postgres redis mailpit \
  2>&1 | grep -v "level=warning" | grep -v "obsolete" || true

green "  ✓ Postgres, Redis, and Mailpit are running"

# ── 5. Database schema ────────────────────────────────────────────────────────
step "Initialising database"

# Check if schema already exists
TABLE_COUNT=$(docker exec release-notes-db \
  psql -U user -d release_notes_db -tAc \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name != 'alembic_version';" \
  2>/dev/null || echo "0")

if [[ "$TABLE_COUNT" -gt 0 ]]; then
  yellow "  ↩ Database already has tables — skipping schema creation"
  yellow "    (run ./reset.sh to wipe and start fresh)"
else
  (cd "$BACKEND_DIR" && "$VENV_PYTHON" -c "
from app.models.database import Base, engine
Base.metadata.create_all(bind=engine)
print('  ✓ Schema created')
")

  # Stamp alembic so incremental migrations work going forward
  (cd "$BACKEND_DIR" && "$VENV_DIR/bin/alembic" stamp head 2>/dev/null)
  green "  ✓ Alembic stamped at head"
fi

# ── 6. Frontend dependencies ──────────────────────────────────────────────────
step "Installing frontend dependencies"

if [[ -d "$FRONTEND_DIR/node_modules" ]]; then
  yellow "  ↩ node_modules already exists — skipping"
else
  (cd "$FRONTEND_DIR" && npm install --silent)
  green "  ✓ Frontend dependencies installed"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
printf '\n'
green "════════════════════════════════════════════════════"
green "  Installation complete!"
green "════════════════════════════════════════════════════"
printf '\n'
echo "  Frontend  → http://localhost:4200"
echo "  Backend   → http://localhost:8000"
echo "  API docs  → http://localhost:8000/docs"
echo "  Mailpit   → http://localhost:8025"
printf '\n'

read -rp "Start the development environment now? [Y/n] " start_now
start_now="${start_now:-Y}"
if [[ "$start_now" =~ ^[Yy]$ ]]; then
  exec "$ROOT_DIR/dev.sh"
else
  echo ""
  echo "Run ./dev.sh when you're ready."
fi
