#!/usr/bin/env bash
set -euo pipefail

# Simple launcher for development: starts backend and frontend in background
# Usage: ./scripts/start.sh

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_CMD="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_CMD" ]; then
  echo "Error: python3 not found on PATH. Install Python or set PATH." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Warning: npm not found. Frontend will not be started." >&2
fi

# Backend
BACKEND_PORT="${PORT:-8000}"
BACKEND_LOG="/tmp/real-estate-ai-backend.log"
BACKEND_PIDFILE="/tmp/real-estate-ai-backend.pid"

if [ -f "$BACKEND_PIDFILE" ] && kill -0 "$(cat "$BACKEND_PIDFILE")" >/dev/null 2>&1; then
  echo "Backend appears to be already running (pid=$(cat $BACKEND_PIDFILE))." 
else
  echo "Starting backend on port $BACKEND_PORT -> logs: $BACKEND_LOG"
  nohup env PORT="$BACKEND_PORT" "$PYTHON_CMD" run_app.py --skip-init --backend-only > "$BACKEND_LOG" 2>&1 &
  echo $! > "$BACKEND_PIDFILE"
  sleep 1
fi

# Frontend
FRONTEND_LOG="/tmp/real-estate-ai-frontend.log"
FRONTEND_PIDFILE="/tmp/real-estate-ai-frontend.pid"

if command -v npm >/dev/null 2>&1; then
  if [ -f "$FRONTEND_PIDFILE" ] && kill -0 "$(cat "$FRONTEND_PIDFILE")" >/dev/null 2>&1; then
    echo "Frontend appears to be already running (pid=$(cat $FRONTEND_PIDFILE))."
  else
    echo "Starting frontend (Vite) -> logs: $FRONTEND_LOG"
    nohup npm --prefix frontend run dev > "$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PIDFILE"
    sleep 1
  fi
else
  echo "Skipping frontend start: npm not available." 
fi

echo
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:${BACKEND_PORT}"
echo "Health:   http://localhost:${BACKEND_PORT}/health"

echo "To stop: ./scripts/stop.sh"
