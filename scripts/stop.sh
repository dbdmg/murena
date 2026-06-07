#!/usr/bin/env bash
set -euo pipefail

# Stop backend/frontend started by `scripts/start.sh`
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_PIDFILE="/tmp/real-estate-ai-backend.pid"
FRONTEND_PIDFILE="/tmp/real-estate-ai-frontend.pid"

if [ -f "$BACKEND_PIDFILE" ]; then
  PID=$(cat "$BACKEND_PIDFILE")
  if kill -0 "$PID" >/dev/null 2>&1; then
    echo "Stopping backend pid $PID"
    kill "$PID" || true
    sleep 1
  fi
  rm -f "$BACKEND_PIDFILE"
else
  echo "No backend pidfile found. Backend may not be running."
fi

if [ -f "$FRONTEND_PIDFILE" ]; then
  PID=$(cat "$FRONTEND_PIDFILE")
  if kill -0 "$PID" >/dev/null 2>&1; then
    echo "Stopping frontend pid $PID"
    kill "$PID" || true
    sleep 1
  fi
  rm -f "$FRONTEND_PIDFILE"
else
  echo "No frontend pidfile found. Frontend may not be running."
fi

echo "Stopped. Check logs in /tmp/real-estate-ai-*.log if needed."
