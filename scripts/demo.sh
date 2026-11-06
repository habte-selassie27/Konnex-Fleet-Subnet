#!/bin/bash
# scripts/demo.sh — single-command full-stack demo (AGENTS.md §0.3 Law 3)
# Status: COMPLETE (Phase 10).
# Launches the backend (headless simulator + REST + WebSocket) and the React
# dashboard, then starts the predefined demo mission (5 robots / 20 tasks /
# seed 42 / nearest policy). Gazebo wiring is STUB (Phase 1) — the demo runs
# the deterministic headless simulator, which is the same execution path the
# validator's in-process executor and the benchmarks use.
set -euo pipefail

cd "$(dirname "$0")/.."

# ─── 1. Python environment ────────────────────────────────────────────────
# Select the first interpreter that can actually import the backend stack.
# An empty .venv used to shadow a working system Python and fail at import.
python_usable() {
  "$1" -c "import uvicorn, fastapi, sqlmodel, structlog" >/dev/null 2>&1
}

PY=""
for candidate in ".venv/bin/python" "/tmp/phase0-venv/bin/python" "python3"; do
  if [ -x "$candidate" ] || command -v "$candidate" >/dev/null 2>&1; then
    if python_usable "$candidate"; then
      PY="$candidate"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "No Python interpreter with the project dependencies was found."
  echo "Run: make setup   (or: ./.venv/bin/pip install -r requirements-dev.txt)"
  exit 1
fi
echo "Using Python: $PY"

# ─── 2. Backend ───────────────────────────────────────────────────────────
if curl -s -m 2 http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1; then
  echo "Backend already running on :8000"
else
  echo "Starting backend on :8000 ..."
  (setsid "$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 \
    > /tmp/fleet_demo_backend.log 2>&1 < /dev/null &)
  for _ in $(seq 1 30); do
    curl -s -m 1 http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1 && break
    sleep 1
  done
fi
curl -s -m 2 http://127.0.0.1:8000/api/v1/health >/dev/null \
  || { echo "Backend failed to start — see /tmp/fleet_demo_backend.log"; exit 1; }
echo "Backend healthy: http://127.0.0.1:8000"

# ─── 3. Frontend dashboard ────────────────────────────────────────────────
# No demo mission is auto-started. Start one from the dashboard's Policy Runner
# or via POST /api/v1/missions/ with your chosen seed/policy.
DASH_PORT=3014
DASH_URL="http://127.0.0.1:${DASH_PORT}"

# A dev server answering on the port is not enough: it must also proxy
# /api to the backend. A stale Vite process (started before vite.config.ts
# gained the proxy) answers /api/v1/health with index.html, which surfaces in
# the UI as "Unexpected token '<' ... is not valid JSON" and a permanent
# OFFLINE state. Verify the proxy, not just the page.
dashboard_wired() {
  curl -s -m 2 "${DASH_URL}/api/v1/health" 2>/dev/null \
    | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'
}

stop_dashboard_port() {
  local pids
  pids="$(lsof -ti "tcp:${DASH_PORT}" 2>/dev/null || true)"
  if [ -z "$pids" ]; then
    pids="$(ss -ltnp 2>/dev/null \
      | awk -v port=":${DASH_PORT}" '$4 ~ port' \
      | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p')"
  fi
  if [ -n "$pids" ]; then
    echo "Stopping stale dashboard process(es): $(echo "$pids" | tr '\n' ' ')"
    kill $pids 2>/dev/null || true
    for _ in $(seq 1 10); do
      lsof -ti "tcp:${DASH_PORT}" >/dev/null 2>&1 || break
      sleep 0.5
    done
    # Still bound after a graceful stop — force it.
    pids="$(lsof -ti "tcp:${DASH_PORT}" 2>/dev/null || true)"
    [ -z "$pids" ] || kill -9 $pids 2>/dev/null || true
  fi
}

if [ -d frontend/node_modules ]; then
  if dashboard_wired; then
    echo "Dashboard already running on :${DASH_PORT} (proxy healthy)"
  else
    if curl -s -m 2 "${DASH_URL}/" >/dev/null 2>&1; then
      echo "Dashboard on :${DASH_PORT} is stale (no working /api proxy) — restarting"
      stop_dashboard_port
    fi
    echo "Starting dashboard on :${DASH_PORT} ..."
    (cd frontend && setsid npm run dev -- --port "${DASH_PORT}" --host 127.0.0.1 \
      > /tmp/fleet_demo_frontend.log 2>&1 < /dev/null &)
    for _ in $(seq 1 30); do
      dashboard_wired && break
      sleep 1
    done
    dashboard_wired \
      || { echo "Dashboard failed to proxy /api — see /tmp/fleet_demo_frontend.log"; exit 1; }
  fi
  echo "Dashboard: ${DASH_URL}"
else
  echo "Frontend dependencies missing — run: cd frontend && npm install"
fi

echo ""
echo "Demo running. Start a mission from the Policy Runner panel at http://127.0.0.1:3014 (or POST /api/v1/missions/) to watch the fleet and live PoPW score."
