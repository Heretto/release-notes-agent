#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "Shutting down..."
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  docker compose stop postgres redis mailpit 2>/dev/null || true
  exit 0
}

trap cleanup SIGINT SIGTERM

# ── Clear any leftover processes from a previous run ─────────────────────────
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "ng serve" 2>/dev/null || true

# ── Infrastructure ────────────────────────────────────────────────────────────
echo "Starting infrastructure (postgres, redis, mailpit)..."
docker compose up -d --wait postgres redis mailpit

# ── Backend ───────────────────────────────────────────────────────────────────
if [[ ! -f "$BACKEND_DIR/venv/bin/activate" ]]; then
  echo "ERROR: backend venv not found at $BACKEND_DIR/venv — run: python -m venv backend/venv && backend/venv/bin/pip install -r backend/requirements.txt"
  exit 1
fi

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  echo "WARNING: $BACKEND_DIR/.env not found — copying from .env.example"
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
fi

echo "Syncing backend dependencies..."
"$BACKEND_DIR/venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"

echo "Starting backend..."
(
  cd "$BACKEND_DIR"
  source venv/bin/activate
  uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
) &
BACKEND_PID=$!

# ── Frontend ──────────────────────────────────────────────────────────────────
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install)
fi

echo "Starting frontend..."
(cd "$FRONTEND_DIR" && NG_CLI_ANALYTICS=false npm start) &
FRONTEND_PID=$!

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "Dev environment running:"
echo "  Frontend  → http://localhost:4200"
echo "  Backend   → http://localhost:8000"
echo "  API docs  → http://localhost:8000/docs"
echo "  Mailpit   → http://localhost:8025"
echo ""
echo "Press Ctrl+C to stop all services."

wait
