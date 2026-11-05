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

# ─── 3. Predefined demo mission ───────────────────────────────────────────
curl -s -m 5 -L -X POST http://127.0.0.1:8000/api/v1/missions \
  -H "X-Fleet-API-Key: dev-only-key" \
  -H "Content-Type: application/json" \
  -d '{"robot_count":5,"task_count":20,"seed":42,"policy":"nearest","time_limit_s":600}' \
  >/dev/null && echo "Mission started: 5 robots / 20 tasks / seed 42 / policy=nearest"

# ─── 4. Live FleetPay event (real telemetry -> agent payment) ─────────────
# 20s into the mission we inject a navigation failure into robot_2. The live
# payment bridge sees the FAILED state in real telemetry, the agent quotes a
# maintenance provider, the policy gate approves it, and a transaction is
# persisted — the dashboard's FleetPay panel then shows a payment that came
# from the actual mission, not from the canned demo scenario.
( sleep 20
  curl -s -m 5 -X POST http://127.0.0.1:8000/api/v1/robots/robot_2/fail \
    -H "X-Fleet-API-Key: dev-only-key" \
    -H "Content-Type: application/json" \
    -d '{"failure_type":"navigation_failure"}' \
    >/dev/null 2>&1
) >/dev/null 2>&1 &
echo "FleetPay live event scheduled: navigation_failure on robot_2 at t+20s"

# ─── 5. Frontend dashboard ────────────────────────────────────────────────
if [ -d frontend/node_modules ]; then
  if curl -s -m 2 http://127.0.0.1:3014/ >/dev/null 2>&1; then
    echo "Dashboard already running on :3014"
  else
    echo "Starting dashboard on :3014 ..."
    (cd frontend && setsid npm run dev -- --port 3014 --host 127.0.0.1 \
      > /tmp/fleet_demo_frontend.log 2>&1 < /dev/null &)
    sleep 5
  fi
  echo "Dashboard: http://127.0.0.1:3014"
else
  echo "Frontend dependencies missing — run: cd frontend && npm install"
fi

echo ""
echo "Demo running. The mission completes in roughly 3-4 minutes."
echo "Open http://127.0.0.1:3014 to watch the fleet (live PoPW score, policy, energy chart)."
echo "The FleetPay panel shows live mission-driven payments (plus MOCK/DEMO settlement)."
