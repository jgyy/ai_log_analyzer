#!/usr/bin/env bash
# Spin up the ai_log_analyzer backend (FastAPI/uvicorn) and frontend (Next.js)
# dev servers in a single tmux session so you don't have to remember the
# commands or juggle multiple terminals.
#
# Usage:
#   ./dev.sh          # start both servers in a tmux session named "ai-log-analyzer"
#   ./dev.sh stop      # kill the tmux session
#
# Backend:  http://localhost:8000
# Frontend: http://localhost:3000
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="ai-log-analyzer"

if [[ "${1:-}" == "stop" ]]; then
  tmux kill-session -t "$SESSION" 2>/dev/null && echo "Stopped $SESSION" || echo "$SESSION is not running"
  exit 0
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required. Install it (e.g. 'sudo pacman -S tmux') and re-run." >&2
  exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session '$SESSION' already running. Attach with: tmux attach -t $SESSION"
  exit 0
fi

# --- Backend setup -----------------------------------------------------
BACKEND_DIR="$ROOT_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Creating backend virtualenv..."
  if command -v uv >/dev/null 2>&1; then
    (cd "$BACKEND_DIR" && uv venv --python 3.12 venv)
  else
    (cd "$BACKEND_DIR" && python3 -m venv venv)
  fi
fi

echo "Installing backend dependencies..."
if command -v uv >/dev/null 2>&1; then
  (cd "$BACKEND_DIR" && uv pip install --python venv/bin/python -q -r requirements.txt)
else
  (cd "$BACKEND_DIR" && venv/bin/python -m pip install -q -r requirements.txt)
fi

if [[ ! -f "$BACKEND_DIR/.env" && -f "$BACKEND_DIR/.env.example" ]]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  echo "Created backend/.env from .env.example — fill in your API keys before analysis will work."
fi

# --- Frontend setup ------------------------------------------------------
FRONTEND_DIR="$ROOT_DIR/frontend"

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Installing frontend dependencies (npm install)..."
  (cd "$FRONTEND_DIR" && npm install)
fi

if [[ ! -f "$FRONTEND_DIR/.env.local" && -f "$FRONTEND_DIR/.env.example" ]]; then
  cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env.local"
  echo "Created frontend/.env.local from .env.example."
fi

# --- Launch tmux session ---------------------------------------------
tmux new-session -d -s "$SESSION" -n backend bash -c \
  "cd '$BACKEND_DIR' && ./venv/bin/python -m uvicorn main:app --reload --port 8000; exec bash"

tmux new-window -t "$SESSION" -n frontend bash -c \
  "cd '$FRONTEND_DIR' && npm run dev; exec bash"

tmux select-window -t "$SESSION:backend"

echo "Started tmux session '$SESSION' with windows: backend (http://localhost:8000), frontend (http://localhost:3000)"
echo "Attach with:  tmux attach -t $SESSION"
echo "Stop with:    ./dev.sh stop"
