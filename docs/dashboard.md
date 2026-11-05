# Dashboard — Frontend Design & Operations (Phase 9)

> Status: COMPLETE (Phase 9). Contract sources: AGENTS.md §1 (Frontend Design Skills), TESTING_PLAN.md §15.
> The dashboard shows **actual simulator/backend data only** — never mocked robots or fabricated charts (AGENTS.md §1.6, Law 1).

---

## 1. What It Is

A React 18 + TypeScript 5 + Vite 5 + TailwindCSS 3 operational dashboard that lets a non-engineer understand the fleet in under 60 seconds:

```
┌─────────────────────────────────────────────────────────────────┐
│ Konnex Fleet Intelligence                    ● LIVE  Policy: MAPPO │
├────────────────────────────────────────────────────────────────-┤
│ SIDEBAR              │ WAREHOUSE MAP (3D)      │ METRICS         │
│ 🤖 Robot 1  MOVING  │   🤖──────►              │ PoPW Score      │
│ 🤖 Robot 2  DELIVER │        🤖                │   94.2 / 100    │
│ 🤖 Robot 3  IDLE    │ 📦  🤖    🤖             │ Tasks: 24/30    │
│ 🤖 Robot 4  CHARGE  │              🤖          │ Success: 96.7%  │
│ 🤖 Robot 5  FAILED  │                          │ Collisions: 0   │
│                      │                          │ Energy: 82%     │
│ Mission #1024        │                          │ Time: 04:31     │
│ 24/30 tasks done     │                          │ [Benchmark]     │
└──────────────────────┴──────────────────────────┴─────────────────┘
```

**Layout** (AGENTS.md §1.3): 3-column grid — `sidebar 280px | map flex-1 | metrics 320px`. Mobile collapses to a single column with a 2D top-down map.

---

## 2. Architecture

```
┌─────────────┐   REST /api/v1 (fetch)     ┌──────────────────┐
│  Frontend   │ ─────────────────────────▶ │ FastAPI backend  │
│  (Vite :3000)│ ◀───────────────────────── │  (uvicorn :8000) │
│             │   WebSocket /ws/fleet (10Hz)│                  │
└──────┬──────┘                            └────────▲─────────┘
       │                                            │ FleetState
       ▼                                            ▼
  Zustand fleetStore ◀───────────── useFleetSocket   FleetOrchestrator
       │                                            (headless sim)
       ▼
  React components (map, cards, charts)
```

- **No layer coupling:** the frontend only knows the typed WS/REST contract. It never talks to Gazebo or ROS directly (AGENTS.md Law 2).
- **State:** Zustand (`src/store/fleetStore.ts`) holds live robot states + mission snapshot; React Query is used where REST polling fits (evaluations, benchmark).
- **Data path:** WebSocket for live telemetry; REST for evaluations/benchmarks.

---

## 3. WebSocket Contract (`ws://localhost:8000/ws/fleet`)

Auth: `?api_key=<FLEET_API_KEY>` query param (browsers can't set WS headers). Dev default `dev-only-key`.

| Event | Payload (JSON) | Frequency |
|---|---|---|
| `ROBOT_STATE_UPDATE` | `{type, robot_id, state: {id, position:{x,y}, orientation, velocity, battery_pct, current_task_id, nav_state, in_collision, comm_state, timestamp, distance_traveled}}` | ~10 Hz |
| `MISSION_UPDATE` | `{type, mission_id, status, policy, completed_tasks, total_tasks, collision_count, failure_count, elapsed_seconds, energy_consumed, popw_score, timestamp}` | ~10 Hz |

`MISSION_UPDATE.policy` is the **real policy name** driving the fleet (e.g.
`nearest`, `hungarian`, `cost_optimizer`) — shown in the header. `popw_score`
is the **live provisional PoPW score**: the broadcaster computes it every tick
from the current mission state with the same `PoPWScoringEngine` + weights the
validator uses, so it converges to the final evaluation score at mission end
(no number on the dashboard ever contradicts an evaluation artifact).
| `TASK_COMPLETED` | `{type, task_id, timestamp}` | on event |
| `COLLISION_DETECTED` | `{type, robot_id, near_miss, timestamp}` | on event |
| `SIMULATOR_OFFLINE` | `{type, reason, timestamp}` | when no mission |

Client also sends `ping` → backend replies `pong` (keep-alive).

`nav_state` values: `idle | moving | blocked | charging | failed` · `comm_state`: `online | degraded | offline`.

Backend implementation: `backend/api/ws/fleet.py` (FleetConnectionManager + FleetBroadcaster).

---

## 4. REST API Used

| Endpoint | Purpose | Client function |
|---|---|---|
| `GET /api/v1/robots` | Snapshot of all robot states | `api.getRobots()` |
| `POST /api/v1/missions` | Configure + start a live mission (Phase 10 demo) | — |
| `GET /api/v1/missions/{id}` | Current mission state (status, score) | — |
| `GET /api/v1/evaluations/{id}` | Evaluation result | `api.getEvaluation()` |
| `POST /api/v1/robots/{id}/fail` | Inject failure (Phase 5) | `api.failRobot()` |
| `GET /api/v1/health` | Liveness probe | `api.getHealth()` |

All calls go through `src/services/api.ts` — no raw `fetch()` in components (AGENTS.md §1.6).

---

## 5. Components

```
src/
├── App.tsx                    # Layout composition + socket bootstrap
├── hooks/
│   ├── useFleetSocket.ts      # WS connect/reconnect/dispatch
│   └── useFleetState.ts       # Derived selectors from the store
├── store/fleetStore.ts        # Zustand: robots, mission, online flag
├── services/api.ts            # Typed REST client
├── types/index.ts             # Contract types
└── components/
    ├── fleet/WarehouseMap.tsx   # Three.js (R3F) 3D warehouse
    ├── fleet/RobotCard.tsx      # Sidebar per-robot status
    ├── fleet/FleetSummary.tsx   # Aggregate fleet stats
    ├── metrics/MetricsDashboard.tsx
    ├── metrics/ScoreGauge.tsx   # PoPW score (animates on change)
    ├── metrics/EnergyChart.tsx  # Energy consumption over time (Recharts, 1 Hz)
    ├── mission/MissionPanel.tsx # Active mission + progress
    ├── validator/EvaluationCard.tsx
    ├── benchmark/BenchmarkTable.tsx
    └── shared/{OfflineIndicator, ErrorBoundary, StatusBadge, LoadingSpinner}.tsx
```

### Live data rules (non-negotiable, AGENTS.md §1.6)

1. **No mock/static data.** When the WS is down or no mission exists, the map shows `OfflineIndicator` ("Simulator offline — no live data"). It never shows fake robots.
2. **No fake zeros.** Charts show "No data yet" when the series is empty.
3. **Score gauge animates only on change** — no idle animations implying activity.
4. **Positions update ≤100 ms** via the 10 Hz WS stream (smooth interpolation allowed).

### Accessibility

- Every interactive element has `aria-label`.
- Color is never the *only* state indicator — status always renders color + icon + text (e.g., `🚨 Failed`, `🔋 Charging`).
- Keyboard navigation works on all controls (focus-visible rings, natural tab order).

---

## 6. How to Run

```bash
# 1. Backend (serves REST + WS)
cd backend && uvicorn main:app --reload --port 8000
#   or from repo root: make backend (if defined)

# 2. Frontend
cd frontend
npm install
npm run dev          # Vite on :3000, proxies /api and /ws to :8000
```

Vite dev proxy (vite.config.ts):
- `/api` → `http://localhost:8000`
- `/ws` → `ws://localhost:8000` (WebSocket upgrade)

Environment: `VITE_API_URL` / `VITE_WS_URL` override the defaults
(`http://localhost:8000`, `ws://localhost:8000/ws/fleet?api_key=dev-only-key`).

### What you should see with the backend up

1. Header badge `● LIVE` and the **real policy name** (e.g. `nearest`).
2. 3D warehouse map with 5 robots moving between pickup/delivery markers.
3. Robot cards updating battery/task/state.
4. Mission panel: progress bar `completed/total`, collisions, elapsed time.
5. **Score gauge streams the live PoPW score** — it moves as tasks complete,
   collisions/energy accrue, and time passes, converging to the final score at
   mission end (no more `No data yet` during a live mission).
6. Energy panel: area chart of energy consumed over time (1 sample/second).

### With the backend down

Header badge `OFFLINE`, map shows "Simulator offline — no live data",
robot sidebar and metrics show "No data yet" (no zeros, no fakes).

---

## 7. Quality Gates

```bash
cd frontend
npm run lint         # ESLint zero errors
npm run type-check   # tsc --noEmit zero errors
npm run test:unit    # Vitest + Testing Library passes
```

Every major panel is wrapped in `ErrorBoundary` — one crashing panel never
takes down the dashboard (AGENTS.md §1.6).
