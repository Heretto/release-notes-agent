#!/usr/bin/env bash
# reset.sh — wipe all application data and re-apply migrations from scratch.
#
# Drops and recreates the PostgreSQL database, flushes Redis, and clears
# Mailpit messages. Leaves Docker containers running so you can immediately
# restart the app with a clean slate.
#
# Usage: ./reset.sh [--yes]
#   --yes   Skip the confirmation prompt (useful in scripts)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

COMPOSE="docker compose"
PYTHON="$BACKEND_DIR/venv/bin/python"
ALEMBIC="$BACKEND_DIR/venv/bin/alembic"

# ── Postgres connection details (must match docker-compose.yml) ────────────────
DB_USER="user"
DB_PASS="password"
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="release_notes_db"
DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

# ── Confirmation ─────────────────────────────────────────────────────────────
if [[ "${1:-}" != "--yes" ]]; then
  echo "⚠️  This will permanently delete ALL application data:"
  echo "   • PostgreSQL database '$DB_NAME' (all tables, all rows)"
  echo "   • Redis cache / queue"
  echo "   • Mailpit captured emails"
  echo ""
  read -rp "Type 'reset' to confirm: " answer
  if [[ "$answer" != "reset" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

echo ""
echo "Resetting application data..."

# ── Ensure infrastructure is running ─────────────────────────────────────────
echo "Starting infrastructure (postgres, redis, mailpit)..."
$COMPOSE up -d --wait postgres redis mailpit 2>&1 \
  | grep -v "level=warning" | grep -v "obsolete" || true

# ── Drop and recreate the database ───────────────────────────────────────────
echo "Dropping database '$DB_NAME'..."
# Terminate any open connections before dropping (backend may be running)
docker exec release-notes-db \
  psql -U "$DB_USER" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS $DB_NAME;" \
  -c "CREATE DATABASE $DB_NAME;" > /dev/null
echo "  ✓ Database recreated"

# ── Flush Redis ───────────────────────────────────────────────────────────────
echo "Flushing Redis..."
docker exec release-notes-redis \
  redis-cli -a devpassword --no-auth-warning FLUSHALL > /dev/null
echo "  ✓ Redis flushed"

# ── Clear Mailpit messages ────────────────────────────────────────────────────
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8025/api/v1/messages \
    | grep -q "200"; then
  curl -s -X DELETE http://localhost:8025/api/v1/messages > /dev/null
  echo "  ✓ Mailpit messages cleared"
fi

# ── Recreate schema ───────────────────────────────────────────────────────────
# The alembic migrations were layered on top of a pre-existing schema, so
# running them from scratch on an empty database fails. Instead, we create all
# tables directly from the SQLAlchemy models (which always reflect the current
# schema) and then stamp alembic at head so it won't try to re-run migrations.
if [[ ! -x "$PYTHON" ]]; then
  echo "⚠️  backend venv not found at $BACKEND_DIR/venv — skipping schema creation."
  echo "   Run: cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt"
  echo "   Then: cd backend && venv/bin/python -c \"from app.models.database import Base, get_engine; Base.metadata.create_all(bind=get_engine())\""
else
  echo "Creating database schema from models..."
  (cd "$BACKEND_DIR" && "$PYTHON" -c "
from hop_core.db import init_engine
from app.models.database import Base, get_engine
init_engine('$DATABASE_URL')
Base.metadata.create_all(bind=get_engine())
")
  echo "  ✓ Schema created"

  echo "Stamping alembic at head..."
  (cd "$BACKEND_DIR" && "$ALEMBIC" stamp head --purge 2>/dev/null || "$ALEMBIC" stamp head)
  echo "  ✓ Alembic stamped"
fi

echo ""
echo "✅ Reset complete. Run ./dev.sh to start the application."
