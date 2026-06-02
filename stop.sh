#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

stop_process() {
  local label="$1"
  local pattern="$2"
  local pids
  pids=$(pgrep -f "$pattern" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    echo "Stopping $label..."
    echo "$pids" | xargs kill 2>/dev/null || true
  fi
}

stop_process "backend"  "uvicorn app.main:app"
stop_process "frontend" "ng serve"

echo "Stopping infrastructure..."
cd "$ROOT_DIR"
docker compose stop postgres redis mailpit

echo "Done."
