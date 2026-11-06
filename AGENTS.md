# AGENTS.md — Konnex Fleet Intelligence Subnet
## Master Agent Specification: All Skill Domains

> **Version:** 1.0.0  
> **Binding on:** All AI coding agents (OpenCode, Claude Code, Gemini, o3, Kimi, or any future agent) operating on this repository  
> **Companion files:** PLAN.md · BUILD.md · SYSTEM_PROMPT.md · TESTING_PLAN.md  
> **Project:** `konnex-fleet-subnet` — Autonomous Robot Fleet Orchestration Subnet for the Konnex Builder Program

---

## PROJECT OVERVIEW

### Problem Statement

Modern autonomous robot fleets face three unsolved coordination problems:

1. **Policy development is centralized** — one company controls one policy; there is no competitive market for fleet intelligence.
2. **Performance evaluation is opaque** — no objective, reproducible standard for measuring "how well did this fleet actually do?"
3. **There is no economic incentive** to contribute better robot coordination algorithms to a shared commons.

Konnex's PoPW model can solve all three: open policy submission, validator-scored physical outcomes, and token rewards for verified performance.

### What This Subnet Enables

```
Any developer submits a fleet policy
           ↓
Validators run it on standardized missions
           ↓
Real physical-work score calculated
           ↓
Best policy earns KNX rewards
           ↓
Robot fleets improve over time through competition
```

### Target Users

| Actor | Role | Motivation |
|---|---|---|
| **Policy Miners** | Submit fleet-control policies (classical or ML) | Earn KNX rewards for high performance |
| **Validators** | Execute policies, score outcomes, publish proofs | Earn validation fees |
| **Mission Requesters** | Post warehouse delivery missions | Get tasks completed |
| **Robot Operators** | Eventually run physical robots on earned policies | Deploy proven intelligence |
| **Konnex Reviewers** | Evaluate the subnet for grant acceptance | Verify technical credibility |

### Core Features — MVP Scope

**Must-have (Spark grant demo):**
- Warehouse simulation in Gazebo with 5 autonomous mobile robots
- Package pickup/delivery mission structure with randomized scenarios
- Three classical baseline policies: nearest-task, Hungarian, cost-optimizer
- Fleet orchestrator: task allocation, collision avoidance, failure detection
- Automated benchmark runner comparing all policies
- Validator service: reproducible policy execution + scoring
- PoPW-inspired score engine (clearly labeled as prototype)
- Fleet monitoring dashboard (React + Vite)
- `make demo` and `make benchmark` single-command entrypoints
- Docker Compose deployment
- CI with lint + unit + integration tests

**Should-have (Launch grant, $75K):**
- MAPPO multi-agent RL policy
- Robot failure simulation + dynamic task reassignment
- Communication degradation model
- Policy containerization / sandboxed submission
- Experiment tracking (MLflow)
- Konnex SDK adapter (post SDK research)

**Nice-to-have (Mainnet, $200K+):**
- Physical robot adapter (ROS 2 hardware interface)
- Domain randomization for sim-to-real
- Multi-validator consensus on scores
- On-chain evaluation commitment + hash anchoring
- Digital twin synchronization

**Explicitly out of scope (MVP):**
- Real robot hardware
- Actual Konnex token issuance (adapter only)
- More than 5 robots in MVP benchmark
- Custom simulator (Gazebo is sufficient)

### PoPW Score Design

The evaluation score is a **prototype** mechanism. It is not Konnex's official scoring algorithm. It will be adapted to match the actual Konnex SDK once reviewed.

```
PoPW Score = weighted sum of:

  Mission Success Rate    (40%) — tasks completed / tasks assigned
  Safety Score            (20%) — 1.0 - (collisions / max_possible)
  Efficiency Score        (15%) — 1.0 - (time_taken / time_limit)
  Energy Score            (10%) — 1.0 - (energy_used / energy_budget)
  Coordination Score      (10%) — inter-robot cooperation metric
  Robustness Score         (5%) — performance under failure conditions
```

Score range: 0.0 – 100.0. Published as a signed evaluation artifact containing the policy hash, scenario seed, score components, and timestamp.

### Anti-Gaming Measures (MVP)

| Threat | MVP Mitigation |
|---|---|
| Reward hacking via scenario exploitation | Randomized scenarios + fixed seed per evaluation |
| Fake trajectories | Validator executes policy directly; no self-reported telemetry |
| Replay attacks | Evaluation timestamps + nonce |
| Sandbox escape | Container CPU/memory limits + network isolation |
| Policy tampering | SHA-256 hash verification before execution |
| Validator collusion | Multiple validator requirement (post-MVP) |

### Mission Structure

Every mission consists of:

```yaml
mission:
  id: uuid
  scenario_id: string
  seed: integer
  environment:
    world: warehouse_v1
    size: [40m, 30m]
    obstacle_count: 15
  robots:
    count: 5
    initial_positions: randomized
    battery_levels: randomized [60%–100%]
  tasks:
    count: 20–30
    pickup_locations: randomized
    delivery_locations: randomized
    priorities: [LOW, MEDIUM, HIGH]
  constraints:
    time_limit: 600s
    max_collisions: 0  # target
    energy_budget: per-robot
  failure_injection:
    robot_failures: 0–1
    communication_loss: optional
```

The generator randomizes parameters from a seed so that any validator can reconstruct the scenario.

### Validator Inputs / Outputs

**Inputs:**
- `policy_id` — identifier of the submitted policy
- `policy_hash` — SHA-256 of policy weights/code
- `scenario_id` — mission definition
- `seed` — random seed for deterministic reproduction
- `env_version` — Gazebo world version hash
- `sim_version` — ROS 2 / Gazebo version string

**Outputs:**
- `trajectory` — full robot path data
- `task_outcomes` — per-task completion status
- `energy_log` — per-robot energy consumption
- `collision_log` — timestamped collision events
- `completion_time`
- `score_components`
- `final_score`
- `evaluation_hash`
- `signature`

**Reproducibility requirement:** Two independent validators running the same (policy_hash, scenario_id, seed, env_version) MUST produce scores within ±0.5 points of each other.

### Technology Stack

| Component | Technology | Justification |
|---|---|---|
| Simulation | **Gazebo Harmonic** | ROS 2 native, active maintenance, no GPU required |
| Robot middleware | **ROS 2 Humble** | Industry standard, LTS until 2027 |
| Physics | **Ignition Physics** (Gazebo default) | Sufficient for warehouse AMR dynamics |
| ML framework | **PyTorch 2.2+** | Ecosystem standard for RL research |
| RL library | **stable-baselines3** | Reliable MAPPO baseline; easier than raw implementations |
| MARL framework | **EPyMARL / custom MAPPO** | Evaluate during Phase 4; choose based on performance |
| Backend API | **FastAPI + uvicorn** | Async, type-safe, automatic OpenAPI docs |
| Database | **SQLite (dev) / PostgreSQL (prod)** | SQLite sufficient for prototype; migrate if needed |
| ORM | **SQLModel** (Pydantic + SQLAlchemy) | Type-safe models shared with FastAPI |
| Experiment tracking | **MLflow** | Lightweight; integrates with PyTorch |
| Frontend | **React 18 + Vite + TypeScript** | Fast iteration; familiar stack |
| Visualization | **react-three-fiber or plain canvas** | 2D warehouse map sufficient for MVP |
| Logging | **structlog** | JSON-structured, async-safe |
| Containerization | **Docker + Docker Compose** | Reproducible environments |
| CI | **GitHub Actions** | Free for open-source |

**What we explicitly avoided and why:**

| Avoided | Reason |
|---|---|
| Isaac Sim | GPU required; overkill for MVP; complex licensing |
| Kubernetes | Not needed until actual subnet scale |
| Kafka | No real-time message volume that justifies it at MVP |
| Ray / RLlib | Heavier than needed; stable-baselines3 sufficient for Phase 4 |
| Custom SLAM | AMCL (Nav2 built-in) is sufficient for warehouse AMR |

### Data Storage Strategy

| Data type | Format | Storage | Retention |
|---|---|---|---|
| Robot trajectories | Parquet | `experiments/results/{exp_id}/` | Permanent |
| Per-step telemetry | Parquet | `experiments/results/{exp_id}/` | Per experiment |
| Mission records | PostgreSQL | DB | Permanent |
| Evaluation artifacts | JSON + SHA-256 | DB + filesystem | Permanent |
| ML checkpoints | PyTorch `.pt` | `ml/checkpoints/` | Latest 5 |
| Experiment metrics | MLflow | MLflow server | Permanent |
| Logs | JSON (structlog) | stdout + file | 30 days |

### Development Phases

| Phase | Deliverable | Acceptance Criterion |
|---|---|---|
| **0** | Architecture docs + repo skeleton | Internally consistent design |
| **1** | Simulation: 5 robots in warehouse | Robots navigate independently |
| **2** | Fleet coordination: baseline policies | 5 robots complete multi-task mission |
| **3** | Benchmarking engine | Policies compared automatically |
| **4** | MARL (MAPPO) | Learned policy beats or matches best baseline |
| **5** | Robustness: failures + comm loss | Fleet recovers from 1 robot failure |
| **6** | Validator service | Two validators reproduce same score ±0.5 |
| **7** | PoPW prototype | Mission produces verifiable evaluation artifact |
| **8** | Konnex adapter | Core system integrates without modification |
| **9** | Dashboard | Third party understands system from UI alone |
| **10** | Final demo | `make demo` + `make benchmark` produce full results |

### Spark Grant Success Criteria

- [ ] `make demo` runs end-to-end in under 3 minutes
- [ ] `make benchmark` produces a comparison table with real numbers
- [ ] At least 3 policies with statistically meaningful differences
- [ ] Validator reproduces any result from (policy_hash + seed)
- [ ] Dashboard shows live robot state during demo
- [ ] All results in `experiments/results/` are from actual runs
- [ ] README contains a demo video link
- [ ] `KONNEX_APPLICATION.md` is complete and accurate

---

## HOW TO READ THIS FILE

This document is organized into **five skill domains**. Every agent must read the domain(s) relevant to its current task before writing any code. Reading only your section is not enough — read the **Global Rules** (Section 0) and the **Inter-Domain Contracts** (Section 6) regardless of which domain you are working in.

```
Section 0  — Global Rules (READ FIRST, always)
Section 1  — Frontend Design Skills
Section 2  — Backend Design Skills
Section 3  — Architecture Skills
Section 4  — Robotics Integration Skills
Section 5  — Third-Party Integration Skills
Section 6  — Inter-Domain Contracts (READ LAST, always)
```

Agents violating the rules in this file produce invalid output that must be discarded and regenerated.

---

# SECTION 0 — GLOBAL RULES

## 0.1 Identity

You are a **Principal Engineer** operating on the Konnex Fleet Intelligence Subnet project. You do not have a single specialty — you hold the entire system in your head and make decisions that preserve system integrity across all layers.

Your persona stack:
- Senior Robotics Software Engineer (ROS 2, Gazebo, sensor fusion)
- Senior ML/RL Engineer (PyTorch, MARL, MAPPO, policy evaluation)
- Senior Distributed Systems Engineer (FastAPI, PostgreSQL, Redis, event systems)
- Senior Frontend Engineer (React 18, TypeScript, Three.js, WebSocket)
- DevOps / Platform Engineer (Docker, GitHub Actions, Prometheus, Grafana)
- Protocol Engineer (PoPW, Konnex adapter, blockchain boundary design)
- Technical Product Lead (Konnex Builder Program requirements, grant positioning)

You do NOT produce:
- Pitch decks
- Fake benchmark numbers
- Unverified Konnex API calls
- Over-engineered architectures that cannot be demoed

## 0.2 Mandatory Pre-Task Checklist

Before writing a single line of code for any task:

```
[ ] State which Phase (0–10) this task belongs to
[ ] State which Skill Domain(s) this task touches
[ ] Read this AGENTS.md section for each domain involved
[ ] Inspect current repository tree: find . -type f | head -60
[ ] Identify what already exists vs what needs to be created
[ ] State the acceptance criterion for the current phase (from TESTING_PLAN.md)
[ ] List new dependencies and verify they are in the approved list (BUILD.md Section 2.2)
[ ] Confirm no Konnex SDK calls are fabricated
```

## 0.3 The Three Laws of This Project

**Law 1: Never fabricate results.**
If an experiment has not run, write `NOT RUN`. If a component is unfinished, write `STUB`. Never write benchmark numbers that did not come from actual execution.

**Law 2: Never couple layers that must stay decoupled.**
The robotics core must never import from the Konnex adapter. The frontend must never talk to Gazebo directly. The validator must never modify robot state. Every cross-layer communication goes through defined interfaces.

**Law 3: The demo must work with one command.**
`make demo` must launch the full stack and run a mission. If it doesn't work, the phase is not complete.

## 0.4 Commit Rules

Only commit when:
1. All tests for the modified component pass
2. `make lint` passes with zero errors
3. You have personally executed the component and observed correct behavior
4. Documentation for the component is updated
5. No fabricated data exists anywhere in the changed files

## 0.5 Prohibited Patterns (Global)

```python
# PROHIBITED everywhere
import konnex  # in robotics/fleet/orchestrator.py
print("debug:", value)  # use structlog
except:  # bare except
assert False, "TODO"  # skip tests
result = 95.2  # fabricated benchmark
time.sleep(5)  # blocking sleep in async code
```

```typescript
// PROHIBITED everywhere
const data: any = ...
console.log("debug")  // use structured logger
// @ts-ignore  // fix the type error instead
```

## 0.6 Status Vocabulary

Every incomplete item in code comments, docs, or experiment results MUST use one of:

| Status | Meaning |
|---|---|
| `COMPLETE` | Implemented, tested, verified by execution |
| `STUB` | Interface defined, implementation pending |
| `NOT RUN` | Experiment not yet executed |
| `UNSTABLE` | Executed but high variance — report std dev |
| `FAILED` | Execution error — report error message |
| `TODO: verify SDK` | Konnex API call not yet confirmed against real docs |
| `SUPERSEDED` | Replaced by newer implementation |

---

# SECTION 1 — FRONTEND DESIGN SKILLS

## 1.0 Frontend Mission

The frontend serves two purposes:
1. **Operational dashboard** — live visualization of robot fleet state during missions
2. **Grant demonstration** — proof that the system works, visible to Konnex reviewers in under 60 seconds

The frontend must show **actual simulator data**, never mocked animations. A reviewer who sees robots moving on screen must know those are real Gazebo robot positions streamed via WebSocket.

## 1.1 Technology Stack

```
Framework:     React 18 (functional components + hooks only)
Language:      TypeScript 5+ (strict mode, zero any)
Build:         Vite 5+
Styling:       TailwindCSS 3+ (utility-first, no inline styles)
3D/Canvas:     Three.js + React Three Fiber (warehouse visualization)
Charts:        Recharts (metrics panels)
State:         Zustand (global fleet state) + React Query (API data)
WebSocket:     native browser WebSocket wrapped in custom hook
Icons:         Lucide React
Testing:       Vitest + React Testing Library
Linting:       ESLint + Prettier
Type checking: tsc --noEmit (zero errors required)
```

## 1.2 Repository Structure — Frontend

```
frontend/
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── tailwind.config.ts
├── .eslintrc.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── router.tsx
    │
    ├── components/
    │   ├── layout/
    │   │   ├── Sidebar.tsx
    │   │   ├── Header.tsx
    │   │   ├── StatusBar.tsx
    │   │   └── Layout.tsx
    │   │
    │   ├── fleet/
    │   │   ├── WarehouseMap.tsx        # Three.js 3D warehouse visualization
    │   │   ├── RobotMarker.tsx         # Individual robot on map
    │   │   ├── TaskMarker.tsx          # Pickup/delivery zones
    │   │   ├── TrajectoryLine.tsx      # Robot path history
    │   │   ├── RobotCard.tsx           # Robot status card (sidebar)
    │   │   └── FleetSummary.tsx        # Aggregate fleet stats
    │   │
    │   ├── mission/
    │   │   ├── MissionPanel.tsx        # Active mission overview
    │   │   ├── TaskList.tsx            # Task queue with status
    │   │   ├── MissionTimeline.tsx     # Event timeline
    │   │   └── MissionControls.tsx     # Start/stop/pause mission
    │   │
    │   ├── metrics/
    │   │   ├── MetricsDashboard.tsx    # Main metrics panel
    │   │   ├── ScoreGauge.tsx          # PoPW score gauge
    │   │   ├── SuccessRateChart.tsx    # Task success over time
    │   │   ├── EnergyChart.tsx         # Energy consumption per robot
    │   │   ├── CollisionCounter.tsx    # Collision event display
    │   │   └── FleetUtilizationBar.tsx
    │   │
    │   ├── validator/
    │   │   ├── ValidatorPanel.tsx      # Active validation status
    │   │   ├── EvaluationCard.tsx      # Completed evaluation summary
    │   │   ├── ArtifactViewer.tsx      # Evaluation artifact JSON viewer
    │   │   └── PolicySelector.tsx      # Switch between competing policies
    │   │
    │   ├── benchmark/
    │   │   ├── BenchmarkTable.tsx      # Policy comparison table
    │   │   ├── ExperimentCard.tsx      # Individual experiment result
    │   │   └── BenchmarkChart.tsx      # Visual policy comparison
    │   │
    │   └── shared/
    │       ├── StatusBadge.tsx
    │       ├── LoadingSpinner.tsx
    │       ├── ErrorBoundary.tsx
    │       ├── OfflineIndicator.tsx    # "Simulator offline" state
    │       └── DataTable.tsx
    │
    ├── hooks/
    │   ├── useFleetSocket.ts           # WebSocket connection to fleet backend
    │   ├── useFleetState.ts            # Derived fleet state from WS data
    │   ├── useMission.ts               # Mission CRUD via React Query
    │   ├── useEvaluations.ts           # Evaluation results
    │   ├── useBenchmark.ts             # Benchmark data
    │   └── useSimulatorStatus.ts       # Online/offline detection
    │
    ├── services/
    │   ├── api.ts                      # Typed API client (all fetch calls here)
    │   ├── websocket.ts                # WS client singleton
    │   └── types.ts                    # Re-export from types/
    │
    ├── store/
    │   ├── fleetStore.ts               # Zustand: live robot states
    │   ├── missionStore.ts             # Zustand: active mission
    │   └── uiStore.ts                  # Zustand: UI preferences
    │
    ├── types/
    │   ├── robot.ts
    │   ├── mission.ts
    │   ├── task.ts
    │   ├── evaluation.ts
    │   ├── metrics.ts
    │   └── api.ts
    │
    └── pages/
        ├── Dashboard.tsx               # Main page: map + live metrics
        ├── Missions.tsx                # Mission list + creation
        ├── Policies.tsx                # Policy submission + leaderboard
        ├── Validators.tsx              # Validator status + history
        ├── Benchmarks.tsx              # Experiment results
        └── Settings.tsx                # Configuration
```

## 1.3 Design System

### Color Palette

```typescript
// src/constants/theme.ts
export const COLORS = {
  // Brand
  primary:    '#0EA5E9',  // sky-500 — active robots, primary actions
  secondary:  '#8B5CF6',  // violet-500 — ML/AI elements
  accent:     '#10B981',  // emerald-500 — success states
  
  // Semantic
  success:    '#22C55E',  // green-500
  warning:    '#F59E0B',  // amber-500
  danger:     '#EF4444',  // red-500
  info:       '#3B82F6',  // blue-500
  
  // Robot States
  robotIdle:     '#94A3B8',  // slate-400
  robotMoving:   '#0EA5E9',  // sky-500
  robotDelivering: '#10B981', // emerald-500
  robotCharging: '#F59E0B',  // amber-500
  robotFailed:   '#EF4444',  // red-500
  robotBlocked:  '#F97316',  // orange-500
  
  // Background
  bg:         '#0F172A',  // slate-900 (dark mode primary)
  bgCard:     '#1E293B',  // slate-800
  bgHover:    '#334155',  // slate-700
  border:     '#334155',  // slate-700
  
  // Text
  textPrimary:   '#F1F5F9',  // slate-100
  textSecondary: '#94A3B8',  // slate-400
  textMuted:     '#64748B',  // slate-500
} as const;
```

### Typography

```typescript
// All text uses these scales — no arbitrary font-size values
// Tailwind classes only: text-xs, text-sm, text-base, text-lg, text-xl, text-2xl, text-3xl
// Font family: Inter (sans) for UI, JetBrains Mono (mono) for data/code

// Headings: font-semibold or font-bold
// Body: font-normal, leading-relaxed
// Data/metrics: font-mono, font-medium
// Labels: text-xs, font-medium, uppercase, tracking-wide
```

### Layout Rules

```
- Dashboard uses a 3-column grid: sidebar(280px) | map(flex-1) | metrics(320px)
- Mobile: single column, map collapses to 2D top-down SVG
- All panels have consistent padding: p-4 (16px)
- Card border radius: rounded-xl (12px)
- Consistent gap between cards: gap-4
- Header height: 56px fixed
- Sidebar width: 280px fixed on desktop
```

## 1.4 WarehouseMap Component (Three.js)

This is the centerpiece of the UI. It must show actual robot positions.

```typescript
// src/components/fleet/WarehouseMap.tsx
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid, Environment } from '@react-three/drei'
import { useFleetState } from '@/hooks/useFleetState'
import { RobotMesh } from './RobotMesh'
import { TaskMarker } from './TaskMarker'
import { ObstacleMesh } from './ObstacleMesh'
import { OfflineIndicator } from '../shared/OfflineIndicator'

export function WarehouseMap() {
  const { robots, tasks, obstacles, isOnline } = useFleetState()
  
  if (!isOnline) {
    return <OfflineIndicator message="Simulator offline — no live data" />
  }
  
  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden bg-slate-900">
      <Canvas
        camera={{ position: [0, 20, 20], fov: 50 }}
        shadows
      >
        <Environment preset="warehouse" />
        <ambientLight intensity={0.4} />
        <directionalLight position={[10, 20, 10]} castShadow intensity={0.8} />
        
        {/* Warehouse floor grid — 40m x 30m */}
        <Grid
          args={[40, 30]}
          cellSize={1}
          cellThickness={0.3}
          cellColor="#1E293B"
          sectionSize={5}
          sectionColor="#334155"
          position={[0, 0, 0]}
        />
        
        {/* Static obstacles */}
        {obstacles.map(obs => (
          <ObstacleMesh key={obs.id} obstacle={obs} />
        ))}
        
        {/* Task markers */}
        {tasks.map(task => (
          <TaskMarker key={task.id} task={task} />
        ))}
        
        {/* Live robots — positions from WebSocket */}
        {robots.map(robot => (
          <RobotMesh key={robot.id} robot={robot} />
        ))}
        
        <OrbitControls
          enablePan={true}
          enableZoom={true}
          maxPolarAngle={Math.PI / 2.2}
        />
      </Canvas>
      
      {/* HUD overlay */}
      <div className="absolute top-3 left-3 flex gap-2">
        <MissionBadge />
        <PolicyBadge />
      </div>
      
      <div className="absolute bottom-3 right-3">
        <ScoreGauge />
      </div>
    </div>
  )
}
```

## 1.5 WebSocket Hook

```typescript
// src/hooks/useFleetSocket.ts
import { useEffect, useRef, useCallback } from 'react'
import { useFleetStore } from '@/store/fleetStore'
import type { FleetEvent } from '@/types/api'

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws/fleet'
const RECONNECT_DELAY_MS = 2000
const MAX_RECONNECT_ATTEMPTS = 10

export function useFleetSocket() {
  const ws = useRef<WebSocket | null>(null)
  const reconnectAttempts = useRef(0)
  const updateRobot = useFleetStore(s => s.updateRobot)
  const setOnline = useFleetStore(s => s.setOnline)
  
  const connect = useCallback(() => {
    ws.current = new WebSocket(WS_URL)
    
    ws.current.onopen = () => {
      reconnectAttempts.current = 0
      setOnline(true)
    }
    
    ws.current.onmessage = (e: MessageEvent) => {
      try {
        const event: FleetEvent = JSON.parse(e.data as string)
        handleFleetEvent(event, updateRobot)
      } catch {
        // Malformed message — log and continue
      }
    }
    
    ws.current.onclose = () => {
      setOnline(false)
      if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts.current++
        setTimeout(connect, RECONNECT_DELAY_MS)
      }
    }
    
    ws.current.onerror = () => {
      ws.current?.close()
    }
  }, [updateRobot, setOnline])
  
  useEffect(() => {
    connect()
    return () => {
      ws.current?.close()
    }
  }, [connect])
}

function handleFleetEvent(
  event: FleetEvent,
  updateRobot: (id: string, state: Partial<RobotState>) => void
) {
  switch (event.type) {
    case 'ROBOT_STATE_UPDATE':
      updateRobot(event.robot_id, event.state)
      break
    case 'TASK_COMPLETED':
      // Update task status in mission store
      break
    case 'MISSION_COMPLETE':
      // Trigger evaluation panel
      break
    case 'COLLISION_DETECTED':
      // Flash robot indicator red
      break
  }
}
```

## 1.6 Frontend Rules

### Rendering Rules

1. **Never render mock/static data.** The map must say "Simulator offline" when Gazebo is not running. It must not show fake robots.
2. **Robot positions update at ≤100ms intervals** via WebSocket. Smooth position interpolation is acceptable.
3. **All charts show real data.** If no data exists for a metric, show "No data yet" — not zeros.
4. **Score gauges animate only when score actually changes.** No idle animations that imply activity.

### Component Rules

1. Every component has a corresponding `*.test.tsx` file
2. No component exceeds 200 lines — extract sub-components
3. No raw `fetch()` calls in components — all API calls through `services/api.ts`
4. No `localStorage` or `sessionStorage` — state lives in Zustand or React Query
5. Error boundaries wrap every major panel — one panel crashing must not crash the whole page
6. All async states handled: loading / error / empty / data

### Accessibility

- All interactive elements have `aria-label`
- Color is never the only indicator of state (always add icon or text label)
- Keyboard navigation works on all controls
- Robot status badges show color + icon + text

## 1.7 Demo Screen Requirements

The main dashboard must be understandable by a non-engineer in 60 seconds. It must show:

```
┌─────────────────────────────────────────────────────────────────┐
│ Konnex Fleet Intelligence                    ● LIVE   Policy: MAPPO │
├────────────────────────────────────────────────────────────────-┤
│ SIDEBAR              │ WAREHOUSE MAP (3D)      │ METRICS         │
│                      │                          │                 │
│ 🤖 Robot 1  MOVING  │   🤖──────►              │ PoPW Score      │
│ 🤖 Robot 2  DELIVER │        🤖                │    94.2 / 100  │
│ 🤖 Robot 3  IDLE    │ 📦  🤖    🤖             │                 │
│ 🤖 Robot 4  CHARGE  │              🤖          │ Tasks: 24/30    │
│ 🤖 Robot 5  FAILED  │                          │ Success: 96.7%  │
│                      │                          │ Collisions: 0   │
│ Mission #1024        │                          │ Energy: 82%     │
│ 24/30 tasks done     │                          │ Time: 04:31     │
│ ETA: 1m 42s          │                          │                 │
│                      │                          │ [Benchmark]     │
└──────────────────────┴──────────────────────────┴─────────────────┘
```

## 1.8 Pages Specification

### Dashboard (/)
- WarehouseMap (full height, center column)
- RobotCard list (left sidebar)
- MetricsDashboard (right panel)
- MissionPanel (bottom bar)

### Missions (/missions)
- Mission list (sortable, filterable)
- Create mission form (scenario config)
- Mission detail drawer (task timeline)

### Policies (/policies)
- Policy leaderboard table (sorted by PoPW score)
- Policy submission form (with hash verification)
- Policy detail (architecture, checkpoint, history)

### Benchmarks (/benchmarks)
- BenchmarkTable (all experiments, real data only)
- Per-experiment drill-down
- Metric comparison charts (Recharts)

### Validators (/validators)
- Active validator status
- Evaluation history
- Artifact viewer (JSON)

---

# SECTION 2 — BACKEND DESIGN SKILLS

## 2.0 Backend Mission

The backend is the **central nervous system** of the Fleet Intelligence subnet. It:
- Receives mission requests and routes them to the Fleet Orchestrator
- Bridges ROS 2 telemetry to the frontend via WebSocket
- Manages policy submissions, evaluations, and experiments
- Persists all mission data, evaluation artifacts, and metrics
- Provides the REST API that frontend, validator, and external tools consume

## 2.1 Technology Stack

```
Language:         Python 3.10+
Framework:        FastAPI 0.110+
ASGI Server:      uvicorn (production: gunicorn + uvicorn workers)
Data validation:  Pydantic v2
ORM:              SQLModel (Pydantic + SQLAlchemy 2.0)
Database:         PostgreSQL 16 (production) / SQLite (dev)
Cache:            Redis 7+
Task queue:       ARQ (async Redis queue — lighter than Celery for this scale)
Object storage:   MinIO (dev) / S3-compatible (production)
Logging:          structlog (JSON output)
Auth:             API key (X-Fleet-API-Key header) — JWT post-MVP
WebSocket:        FastAPI native WebSocket
Testing:          pytest + httpx (async test client)
```

## 2.2 Repository Structure — Backend

```
backend/
├── main.py                         # FastAPI app factory
├── config.py                       # Pydantic Settings (env-driven)
├── dependencies.py                 # FastAPI dependency injection
│
├── api/
│   ├── __init__.py
│   ├── router.py                   # Mounts all routers
│   ├── middleware.py               # Auth, logging, CORS, timing
│   │
│   ├── v1/
│   │   ├── missions.py             # POST /missions, GET /missions/:id
│   │   ├── tasks.py                # GET /missions/:id/tasks
│   │   ├── robots.py               # GET /robots, GET /robots/:id
│   │   ├── policies.py             # POST /policies, GET /policies
│   │   ├── evaluations.py          # POST /evaluations, GET /evaluations/:id
│   │   ├── experiments.py          # GET /experiments, GET /experiments/:id
│   │   ├── metrics.py              # GET /metrics (aggregated)
│   │   └── health.py               # GET /health, GET /ready
│   │
│   └── ws/
│       └── fleet.py                # WebSocket /ws/fleet
│
├── services/
│   ├── __init__.py
│   ├── mission_service.py          # Mission lifecycle logic
│   ├── task_service.py             # Task CRUD + assignment
│   ├── policy_service.py           # Policy submission + hash verification
│   ├── evaluation_service.py       # Trigger + track evaluations
│   ├── robot_service.py            # Robot state management
│   ├── metrics_service.py          # Aggregate metrics computation
│   └── storage_service.py          # MinIO/S3 artifact storage
│
├── repositories/
│   ├── __init__.py
│   ├── mission_repo.py
│   ├── task_repo.py
│   ├── policy_repo.py
│   ├── evaluation_repo.py
│   ├── robot_repo.py
│   └── experiment_repo.py
│
├── models/
│   ├── __init__.py
│   ├── db/                         # SQLModel DB models
│   │   ├── mission.py
│   │   ├── task.py
│   │   ├── robot.py
│   │   ├── policy.py
│   │   ├── evaluation.py
│   │   └── experiment.py
│   └── api/                        # Pydantic request/response schemas
│       ├── mission.py
│       ├── task.py
│       ├── robot.py
│       ├── policy.py
│       ├── evaluation.py
│       └── metrics.py
│
├── events/
│   ├── bus.py                      # In-process event bus (asyncio)
│   ├── types.py                    # Event dataclasses
│   └── handlers/
│       ├── mission_handler.py
│       ├── robot_handler.py
│       └── websocket_handler.py    # Broadcasts events to WS clients
│
├── workers/
│   ├── arq_worker.py               # ARQ worker entrypoint
│   └── tasks/
│       ├── benchmark_task.py
│       ├── evaluation_task.py
│       └── ml_training_task.py
│
├── db/
│   ├── database.py                 # SQLModel engine + session
│   ├── migrations/                 # Alembic migrations
│   └── seed.py                     # Dev seed data
│
├── ros/
│   ├── bridge.py                   # ROS 2 ↔ Backend bridge
│   ├── subscriber.py               # ROS 2 topic subscriptions
│   └── publisher.py                # ROS 2 command publisher
│
└── tests/
    ├── conftest.py
    ├── test_missions_api.py
    ├── test_policies_api.py
    ├── test_evaluations_api.py
    └── test_websocket.py
```

## 2.3 FastAPI App Factory

```python
# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from backend.api.router import api_router
from backend.api.ws.fleet import fleet_ws_router
from backend.api.middleware import AuthMiddleware, RequestLoggingMiddleware
from backend.db.database import create_all_tables
from backend.ros.bridge import ROSBridge
from backend.config import settings

logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("fleet_backend_starting", version=settings.version)
    await create_all_tables()
    
    bridge = ROSBridge()
    await bridge.start()
    app.state.ros_bridge = bridge
    
    yield
    
    await bridge.stop()
    logger.info("fleet_backend_stopped")

def create_app() -> FastAPI:
    app = FastAPI(
        title="Konnex Fleet Intelligence API",
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthMiddleware, api_key=settings.fleet_api_key)
    
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(fleet_ws_router, prefix="/ws")
    
    return app

app = create_app()
```

## 2.4 Database Models

```python
# backend/models/db/mission.py
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
import uuid

class MissionStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETE  = "complete"
    FAILED    = "failed"
    TIMED_OUT = "timed_out"

class Mission(SQLModel, table=True):
    __tablename__ = "missions"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    scenario_id: str = Field(index=True)
    seed: int
    policy_id: Optional[str] = Field(default=None, foreign_key="policies.id")
    status: MissionStatus = Field(default=MissionStatus.PENDING)
    robot_count: int
    task_count: int
    completed_tasks: int = Field(default=0)
    collision_count: int = Field(default=0)
    elapsed_seconds: float = Field(default=0.0)
    energy_consumed: float = Field(default=0.0)
    popw_score: Optional[float] = Field(default=None)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    
    tasks: list["Task"] = Relationship(back_populates="mission")
    evaluation: Optional["Evaluation"] = Relationship(back_populates="mission")
```

```python
# backend/models/db/policy.py
from sqlmodel import SQLModel, Field
import uuid

class PolicyStatus(str, Enum):
    SUBMITTED  = "submitted"
    VERIFIED   = "verified"     # hash checked
    EVALUATED  = "evaluated"    # at least one evaluation complete
    REJECTED   = "rejected"     # failed hash check or sandbox

class Policy(SQLModel, table=True):
    __tablename__ = "policies"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    version: str
    author: str
    algorithm: str                    # e.g. "MAPPO", "Hungarian", "CostOptimizer"
    policy_hash: str = Field(index=True)  # SHA-256 of weights
    container_image: Optional[str] = Field(default=None)
    artifact_path: Optional[str] = Field(default=None)  # S3 path
    status: PolicyStatus = Field(default=PolicyStatus.SUBMITTED)
    best_score: Optional[float] = Field(default=None)
    eval_count: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

## 2.5 REST API Specification

```python
# backend/api/v1/missions.py
from fastapi import APIRouter, Depends, HTTPException, status
from backend.models.api.mission import (
    MissionCreateRequest, MissionResponse, MissionListResponse
)
from backend.services.mission_service import MissionService
from backend.dependencies import get_mission_service, require_api_key

router = APIRouter(prefix="/missions", tags=["missions"])

@router.post(
    "/",
    response_model=MissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and start a new fleet mission",
)
async def create_mission(
    body: MissionCreateRequest,
    service: MissionService = Depends(get_mission_service),
    _: None = Depends(require_api_key),
) -> MissionResponse:
    """
    Creates a mission from a scenario definition.
    Validates scenario config, initializes robots, and starts mission execution.
    Returns mission_id for status polling.
    """
    return await service.create_mission(body)

@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(
    mission_id: str,
    service: MissionService = Depends(get_mission_service),
) -> MissionResponse:
    mission = await service.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")
    return mission

@router.get("/{mission_id}/replay")
async def get_mission_replay(mission_id: str) -> dict:
    """Returns trajectory data for replay visualization."""
    ...
```

## 2.6 WebSocket Fleet Bridge

```python
# backend/api/ws/fleet.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.events.bus import event_bus
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()

class FleetConnectionManager:
    """Manages all active WebSocket connections."""
    
    def __init__(self):
        self._connections: list[WebSocket] = []
    
    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("ws_client_connected", total=len(self._connections))
    
    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)
        logger.info("ws_client_disconnected", total=len(self._connections))
    
    async def broadcast(self, message: dict) -> None:
        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self._connections.remove(ws)

manager = FleetConnectionManager()

@router.websocket("/fleet")
async def fleet_websocket(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Keep alive — actual data is pushed by event handlers
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(ws)
```

## 2.7 ROS 2 Bridge

```python
# backend/ros/bridge.py
"""
Bridges ROS 2 topics to the backend event bus.
This is the ONLY place in the backend that knows about ROS 2.
Nothing else in the backend imports rclpy.
"""
import asyncio
import threading
from typing import Callable
import structlog

logger = structlog.get_logger(__name__)

class ROSBridge:
    """
    Runs a ROS 2 spin loop in a background thread.
    Converts ROS 2 messages to backend events via callback queue.
    """
    
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._callbacks: list[Callable] = []
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None
    
    async def start(self) -> None:
        self._loop = asyncio.get_event_loop()
        self._running = True
        self._thread = threading.Thread(target=self._spin_ros, daemon=True)
        self._thread.start()
        logger.info("ros_bridge_started")
    
    async def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("ros_bridge_stopped")
    
    def _spin_ros(self) -> None:
        """Runs in background thread. Never call async functions directly here."""
        try:
            import rclpy
            from rclpy.node import Node
            
            rclpy.init()
            node = FleetBridgeNode(callback=self._on_ros_message)
            
            while self._running:
                rclpy.spin_once(node, timeout_sec=0.05)
            
            node.destroy_node()
            rclpy.shutdown()
        except Exception as e:
            logger.error("ros_bridge_thread_error", error=str(e))
    
    def _on_ros_message(self, event: dict) -> None:
        """Thread-safe dispatch to asyncio event loop."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._dispatch_event(event), self._loop
            )
    
    async def _dispatch_event(self, event: dict) -> None:
        from backend.events.bus import event_bus
        await event_bus.publish(event)
```

## 2.8 Backend API Endpoint List

```
Base URL: http://localhost:8000/api/v1
Auth: X-Fleet-API-Key header

POST   /missions              Create a new mission
GET    /missions/:id          Get mission status
GET    /missions/:id/replay   Get mission replay data

POST   /policies              Submit a policy
GET    /policies              List all policies
GET    /policies/:id          Get policy details

POST   /evaluations           Start a policy evaluation
GET    /evaluations/:id       Get evaluation result
GET    /evaluations/:id/artifact  Get evaluation artifact

GET    /robots                List all robots (live state)
GET    /robots/:id            Get robot state

GET    /metrics               Aggregated fleet metrics
GET    /experiments           List experiment results
GET    /experiments/:id       Get experiment detail
```

All endpoints return JSON. All responses include a `request_id` for tracing. OpenAPI docs auto-generated at `/docs`.

## 2.9 Backend Rules

1. **No synchronous database calls in async route handlers.** Use `await` with async SQLModel sessions.
2. **All config via environment variables.** No hard-coded URLs, passwords, or ports.
3. **Every endpoint returns consistent error shapes:**
   ```json
   {"error": "mission_not_found", "message": "Mission abc123 not found", "request_id": "xyz"}
   ```
4. **Request/response validation via Pydantic v2.** Never return raw DB model objects to API consumers.
5. **ROS 2 imports only in `backend/ros/`.** Nothing else in the backend imports `rclpy`.
6. **WebSocket broadcasts must not block request handlers.** Use background tasks.
7. **Object storage paths must be deterministic** (policy_hash/artifact.tar.gz) to enable deduplication.

---

# SECTION 3 — ARCHITECTURE SKILLS

## 3.0 Architecture Mission

The architecture agent is responsible for ensuring that all components of the system are **correctly layered**, that **no forbidden cross-layer imports exist**, that all **data flows are defined**, and that the **scalability path from prototype to Konnex mainnet** is credible.

## 3.1 Layer Map

```
┌─────────────────────────────────────────────────────────────────────┐
│ PRESENTATION                                                         │
│   React 18 + TypeScript + Three.js + Recharts                       │
│   WebSocket consumer | REST consumer | No business logic             │
├─────────────────────────────────────────────────────────────────────┤
│ API GATEWAY                                                          │
│   FastAPI | Auth middleware | Rate limiting | OpenAPI docs           │
│   WebSocket broadcaster                                              │
├────────────────────────┬────────────────────────────────────────────┤
│ APPLICATION SERVICES   │ ASYNC WORKERS                              │
│   MissionService       │   ARQ + Redis                              │
│   PolicyService        │   BenchmarkTask                            │
│   EvaluationService    │   EvaluationTask                           │
│   MetricsService       │   MLTrainingTask                           │
├────────────────────────┴────────────────────────────────────────────┤
│ DOMAIN CORE                                                          │
│   Fleet Orchestrator | Task Allocator | Failure Manager             │
│   Mission Manager | Battery Manager | Collision Monitor             │
├────────────────────────┬────────────────────────────────────────────┤
│ ML PLATFORM            │ VALIDATION ENGINE                          │
│   MARL Training        │   ValidatorRunner                          │
│   Policy Evaluation    │   PoPW Scoring Engine                      │
│   Experiment Tracking  │   Reproducibility Verifier                 │
│   MLflow               │   Policy Sandbox (Docker)                  │
├────────────────────────┴────────────────────────────────────────────┤
│ ROBOTICS LAYER                                                       │
│   ROS 2 | Nav2 | AMCL | SLAM Toolbox | TF2                         │
│   Robot Adapters | Sensor Processors | Hardware Abstraction         │
├────────────────────────┬────────────────────────────────────────────┤
│ SIMULATION             │ PROTOCOL / WEB3                            │
│   Gazebo Harmonic      │   PoPW Adapter                             │
│   Digital Twin         │   Konnex Adapter (STUB until SDK verified) │
│   Isaac Sim (optional) │   Policy Registry                          │
├────────────────────────┴────────────────────────────────────────────┤
│ INFRASTRUCTURE                                                       │
│   PostgreSQL | Redis | MinIO | Docker | GitHub Actions              │
│   Prometheus | Grafana | structlog                                   │
└─────────────────────────────────────────────────────────────────────┘
```

## 3.2 Forbidden Cross-Layer Imports

The following imports are **architecture violations** and must never exist:

```python
# VIOLATION: Robotics core importing Konnex adapter
# in: robotics/fleet/orchestrator.py
from protocol.konnex.adapter import KonnexAdapter  # ❌ FORBIDDEN

# VIOLATION: Frontend directly accessing Gazebo
# in: frontend/src/components/WarehouseMap.tsx
import rclpy  # ❌ IMPOSSIBLE and forbidden

# VIOLATION: Validator importing Fleet Orchestrator internals
# in: validator/runner.py
from fleet.orchestrator import FleetOrchestrator  # ❌ FORBIDDEN
# (validator must use policy interface only)

# VIOLATION: Backend importing ML training code
# in: backend/services/mission_service.py
from ml.training.train import MAPPOTrainer  # ❌ FORBIDDEN
# (training runs as a background worker, not inline)

# VIOLATION: Policy importing validator
# in: ml/policies/mappo/agent.py
from validator.scoring.engine import PoPWScoringEngine  # ❌ FORBIDDEN
# (policies must be unaware of how they are scored)
```

## 3.3 Allowed Data Flows

```
Frontend → Backend API (REST)              ✅ POST /missions, GET /robots
Frontend ← Backend WebSocket              ✅ Live robot states, events
Backend → Fleet Orchestrator (direct call) ✅ In-process (same Python process)
Backend → ROS 2 (via ROSBridge)           ✅ Thread-safe callback queue
Fleet Orchestrator → Robot Adapters       ✅ Protocol-defined interface
Robot Adapters → Gazebo (via ROS 2)       ✅ ROS 2 topics/services
Validator → Policy Container (Docker API) ✅ REST API to sandbox container
Validator → Gazebo (via ROS 2)            ✅ Spawn/reset environment
Validator → Backend (evaluation result)   ✅ POST /evaluations
Backend → MinIO/S3 (artifact storage)     ✅ boto3 / aiobotocore
Backend → Redis (cache + task queue)      ✅ aioredis
Konnex Adapter ← PoPW Adapter             ✅ Adapter calls adapter
ML Training → FleetEnv (Gymnasium)        ✅ Training loop uses env
MLflow ← ML Training (metrics logging)   ✅ mlflow.log_metric()
```

## 3.4 Event System Design

```python
# backend/events/types.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

@dataclass
class MissionCreatedEvent:
    type: Literal["MISSION_CREATED"] = "MISSION_CREATED"
    mission_id: str = ""
    scenario_id: str = ""
    seed: int = 0
    robot_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class TaskAssignedEvent:
    type: Literal["TASK_ASSIGNED"] = "TASK_ASSIGNED"
    task_id: str = ""
    robot_id: str = ""
    policy: str = ""
    distance: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class RobotStateUpdateEvent:
    type: Literal["ROBOT_STATE_UPDATE"] = "ROBOT_STATE_UPDATE"
    robot_id: str = ""
    position_x: float = 0.0
    position_y: float = 0.0
    orientation: float = 0.0
    battery_pct: float = 0.0
    nav_state: str = ""
    current_task_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class CollisionDetectedEvent:
    type: Literal["COLLISION_DETECTED"] = "COLLISION_DETECTED"
    robot_id: str = ""
    other_id: str = ""   # robot_id or obstacle_id
    position_x: float = 0.0
    position_y: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class MissionCompleteEvent:
    type: Literal["MISSION_COMPLETE"] = "MISSION_COMPLETE"
    mission_id: str = ""
    tasks_completed: int = 0
    tasks_total: int = 0
    elapsed_seconds: float = 0.0
    collision_count: int = 0
    popw_score: float | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class EvaluationCompleteEvent:
    type: Literal["EVALUATION_COMPLETE"] = "EVALUATION_COMPLETE"
    evaluation_id: str = ""
    policy_id: str = ""
    final_score: float = 0.0
    artifact_hash: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

## 3.5 Configuration Architecture

All configuration is environment-driven. No hard-coded values anywhere.

```python
# backend/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    # App
    version: str = "0.1.0"
    environment: str = "development"
    
    # API
    fleet_api_key: str = "dev-only-key"  # CHANGE IN PRODUCTION
    cors_origins: list[str] = ["http://localhost:3000"]
    
    # Database
    database_url: str = "sqlite:///./fleet_dev.db"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Storage
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "fleet-artifacts"
    
    # ROS 2
    ros_domain_id: int = 42
    ros_namespace: str = "/fleet"
    
    # Simulation
    gazebo_world: str = "warehouse_v1"
    robot_count: int = 5
    
    # ML
    mlflow_tracking_uri: str = "http://localhost:5000"
    
    # Konnex (STUB — verify SDK before populating)
    konnex_network_url: str = ""        # TODO: verify SDK
    konnex_api_key: str = ""            # TODO: verify SDK

settings = Settings()
```

## 3.6 Docker Compose Architecture

```yaml
# docker-compose.yml
version: "3.9"

services:

  # ─── Infrastructure ────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: fleet
      POSTGRES_USER: fleet
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-fleet_dev}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fleet"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks: [fleet-net]

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
    networks: [fleet-net]

  minio:
    image: minio/minio:RELEASE.2024-03-10T02-53-48Z
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:-minioadmin}
    volumes:
      - minio_data:/data
    ports:
      - "9001:9001"   # console
    networks: [fleet-net]

  # ─── Robotics / Simulation ────────────────────────────────────
  gazebo:
    build:
      context: ./simulation
      dockerfile: Dockerfile.gazebo
    environment:
      - ROS_DOMAIN_ID=42
      - DISPLAY=${DISPLAY:-:0}
    volumes:
      - ./simulation/worlds:/worlds:ro
      - /tmp/.X11-unix:/tmp/.X11-unix:rw  # for headless rendering
    networks: [fleet-net]
    deploy:
      resources:
        limits:
          memory: 4G

  # ─── Application ──────────────────────────────────────────────
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    depends_on:
      postgres: { condition: service_healthy }
      redis:    { condition: service_healthy }
      gazebo:   { condition: service_started }
    environment:
      - DATABASE_URL=postgresql://fleet:${POSTGRES_PASSWORD:-fleet_dev}@postgres/fleet
      - REDIS_URL=redis://redis:6379/0
      - MINIO_ENDPOINT=minio:9000
      - FLEET_API_KEY=${FLEET_API_KEY:-dev-only-key}
      - ROS_DOMAIN_ID=42
      - MLFLOW_TRACKING_URI=http://mlflow:5000
    ports:
      - "8000:8000"
    networks: [fleet-net]

  arq-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: python -m backend.workers.arq_worker
    depends_on:
      - backend
      - redis
    environment:
      - DATABASE_URL=postgresql://fleet:${POSTGRES_PASSWORD:-fleet_dev}@postgres/fleet
      - REDIS_URL=redis://redis:6379/0
    networks: [fleet-net]

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    depends_on: [backend]
    ports:
      - "3000:80"
    environment:
      - VITE_API_URL=http://localhost:8000
      - VITE_WS_URL=ws://localhost:8000/ws/fleet
    networks: [fleet-net]

  # ─── Validation ───────────────────────────────────────────────
  validator:
    build:
      context: ./validator
      dockerfile: Dockerfile
    depends_on:
      - backend
      - gazebo
      - redis
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./experiments/results:/results
    environment:
      - BACKEND_URL=http://backend:8000
      - ROS_DOMAIN_ID=42
    networks: [fleet-net]

  # ─── ML Platform ──────────────────────────────────────────────
  mlflow:
    image: ghcr.io/mlflow/mlflow:v2.11.0
    command: mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri /mlflow/data
    volumes:
      - mlflow_data:/mlflow/data
    ports:
      - "5000:5000"
    networks: [fleet-net]

  # ─── Monitoring ───────────────────────────────────────────────
  prometheus:
    image: prom/prometheus:v2.51.0
    volumes:
      - ./infra/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
    networks: [fleet-net]

  grafana:
    image: grafana/grafana:10.4.0
    volumes:
      - ./infra/grafana:/etc/grafana/provisioning:ro
      - grafana_data:/var/lib/grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
    networks: [fleet-net]

networks:
  fleet-net:

volumes:
  postgres_data:
  redis_data:
  minio_data:
  mlflow_data:
  grafana_data:
```

## 3.7 Scalability Path

```
LEVEL 1 — Prototype (current)
  Single Docker Compose
  SQLite → PostgreSQL
  Local MinIO
  1 validator
  Manual policy submission

LEVEL 2 — Testnet ($75K Launch tier)
  Cloud deployment (single VM → auto-scaling group)
  PostgreSQL RDS / managed
  S3 object storage
  3+ validators (consensus)
  API-driven policy submission with sandboxed containers
  Public demo endpoint

LEVEL 3 — Mainnet ($200K+ tier)
  Konnex network integration (actual SDK calls)
  On-chain policy registry
  Distributed validator network
  Physical robot pilot
  KNX reward distribution
  Open policy marketplace
```

---

# SECTION 4 — ROBOTICS INTEGRATION SKILLS

## 4.0 Robotics Mission

The robotics agent is responsible for implementing all ROS 2 nodes, Gazebo simulation setup, sensor processing, navigation configuration, and the hardware abstraction layer that makes the fleet work in both simulation and (eventually) physical hardware.

## 4.1 ROS 2 Node Architecture

```
/fleet_manager_node               ← FleetOrchestrator ROS 2 interface
/mission_manager_node             ← Mission lifecycle

/robot_0/
    /robot_0/fleet_agent_node     ← Receives assignments, reports status
    /robot_0/battery_node         ← Battery model and monitoring
    /robot_0/nav2 (stack)         ← Full Nav2 navigation stack
        /robot_0/amcl             ← Localization
        /robot_0/planner_server   ← Global path planner
        /robot_0/controller_server ← Local controller (DWA/TEB)
        /robot_0/behavior_server  ← Behavior tree navigator

/robot_1/ ... (same structure)
/robot_N/ ... (same structure)

/collision_monitor_node           ← Cross-robot collision detection
/failure_detector_node            ← Robot health monitoring
/digital_twin_node                ← Maintains global world state
```

## 4.2 Topic / Service Map

```
PUBLISHED TOPICS
/fleet/status                  → FleetStatus.msg     (10Hz)
/robot_{n}/status              → RobotStatus.msg     (20Hz)
/robot_{n}/battery             → BatteryState.msg    (1Hz)
/fleet/collisions              → CollisionEvent.msg  (on event)
/fleet/task_events             → TaskEvent.msg       (on event)

SUBSCRIBED TOPICS
/robot_{n}/scan                ← sensor_msgs/LaserScan   (LiDAR, 10Hz)
/robot_{n}/imu                 ← sensor_msgs/Imu         (100Hz)
/robot_{n}/odom                ← nav_msgs/Odometry       (50Hz)
/robot_{n}/amcl_pose           ← geometry_msgs/PoseWithCovarianceStamped

SERVICES
/fleet/assign_task             → AssignTask.srv      (request: task_id, robot_id)
/fleet/inject_failure          → InjectFailure.srv   (request: robot_id, failure_type)
/fleet/reset_mission           → ResetMission.srv    (request: scenario_id, seed)

ACTIONS
/robot_{n}/navigate_to_pose    ← nav2_msgs/NavigateToPose  (Nav2 goal)
```

## 4.3 Custom ROS 2 Messages

```
# msg/RobotStatus.msg
std_msgs/Header header
string robot_id
float64 pos_x
float64 pos_y
float64 orientation
float64 vel_linear
float64 vel_angular
float32 battery_pct
string nav_state        # idle|moving|blocked|charging|failed
bool in_collision
string current_task_id  # empty if idle
string comm_state       # online|degraded|offline

# msg/CollisionEvent.msg
std_msgs/Header header
string robot_id
string other_id
float64 pos_x
float64 pos_y
float32 severity        # 0.0=near-miss, 1.0=full collision

# msg/TaskEvent.msg
std_msgs/Header header
string event_type       # assigned|started|completed|failed|reassigned
string task_id
string robot_id
string policy_name

# srv/AssignTask.srv
string task_id
string robot_id
string policy_name
---
bool success
string message

# srv/InjectFailure.srv
string robot_id
string failure_type     # comm_loss|nav_failure|battery_critical|shutdown
---
bool success
string message
```

## 4.4 Warehouse World (SDF)

```xml
<!-- simulation/worlds/warehouse_v1.sdf -->
<!-- 
  World spec:
  - Floor: 40m x 30m
  - Walls: 0.3m thick, 3m high
  - Shelves: 15 units, 4m x 1m x 2m (randomizable positions via scenario config)
  - Pickup zones: 5 (floor markings, 1m radius)
  - Delivery zones: 5 (floor markings, 1m radius)  
  - Charging stations: 2 (corners)
  - Lighting: uniform overhead, no shadows needed for MVP
  - Gravity: 9.81 m/s² (standard)
  - Physics: 1000Hz (Gazebo default)
-->
```

## 4.5 Robot URDF / Xacro Spec

```xml
<!--
  AMR (Autonomous Mobile Robot) — differential drive
  
  Physical params:
    chassis: 0.5m x 0.5m x 0.25m, mass 20kg
    wheels: 0.15m radius, 0.05m width, mass 1kg each
    wheel_base: 0.4m
    caster: 1 rear caster wheel
    
  Sensors:
    LiDAR: top-mounted, 360° scan, 10m range, 1° resolution, 10Hz
            pose: [0, 0, 0.25, 0, 0, 0] (x, y, z, roll, pitch, yaw)
    IMU: chassis-mounted, 100Hz
    Odometry: from wheel encoders, 50Hz
    
  Drive:
    max_linear_velocity: 1.0 m/s
    max_angular_velocity: 1.5 rad/s
    
  Gazebo plugins:
    diff_drive_plugin (wheel control)
    lidar_plugin (scan publisher)
    imu_plugin (imu publisher)
    odometry_plugin (odom publisher)
-->
```

## 4.6 Nav2 Configuration

```yaml
# simulation/config/nav2_params.yaml
# Applies to all robots (namespaced per robot at launch time)

amcl:
  use_sim_time: true
  alpha1: 0.2       # rotation noise from rotation
  alpha2: 0.2       # rotation noise from translation
  alpha3: 0.2       # translation noise from translation
  alpha4: 0.2       # translation noise from rotation
  base_frame_id: "base_link"
  beam_skip_distance: 0.5
  beam_skip_error_threshold: 0.9
  beam_skip_threshold: 0.3
  do_beamskip: false
  global_frame_id: "map"
  lambda_short: 0.1
  laser_likelihood_max_dist: 2.0
  laser_max_range: 10.0
  laser_min_range: -1.0
  laser_model_type: "likelihood_field"
  max_beams: 60
  max_particles: 2000
  min_particles: 500
  odom_frame_id: "odom"
  pf_err: 0.05
  pf_z: 0.99
  recovery_alpha_fast: 0.0
  recovery_alpha_slow: 0.0
  resample_interval: 1
  robot_model_type: "nav2_amcl::DifferentialMotionModel"
  save_pose_rate: 0.5
  sigma_hit: 0.2
  tf_broadcast: true
  transform_tolerance: 1.0
  update_min_a: 0.2
  update_min_d: 0.25
  z_hit: 0.5
  z_max: 0.05
  z_rand: 0.5
  z_short: 0.05
  scan_topic: scan

controller_server:
  use_sim_time: true
  controller_frequency: 20.0
  min_x_velocity_threshold: 0.001
  min_y_velocity_threshold: 0.5
  min_theta_velocity_threshold: 0.001
  failure_tolerance: 0.3
  progress_checker_plugin: "progress_checker"
  goal_checker_plugins: ["general_goal_checker"]
  controller_plugins: ["FollowPath"]
  
  progress_checker:
    plugin: "nav2_controller::SimpleProgressChecker"
    required_movement_radius: 0.5
    movement_time_allowance: 10.0
    
  general_goal_checker:
    stateful: true
    plugin: "nav2_controller::SimpleGoalChecker"
    xy_goal_tolerance: 0.25
    yaw_goal_tolerance: 0.25
    
  FollowPath:
    plugin: "nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController"
    desired_linear_vel: 0.8
    lookahead_dist: 0.6
    min_lookahead_dist: 0.3
    max_lookahead_dist: 0.9
    lookahead_time: 1.5
    rotate_to_heading_angular_vel: 1.8
    use_velocity_scaled_lookahead_dist: false
    min_approach_linear_velocity: 0.05
    approach_velocity_scaling_dist: 1.0
    use_collision_detection: true
    max_allowed_time_to_collision_up_to_carrot: 1.0
    use_regulated_linear_velocity_scaling: true
    use_fixed_curvature_lookahead: false
    curvature_lookahead_dist: 0.25
    use_cost_regulated_linear_velocity_scaling: false
    regulated_linear_scaling_min_radius: 0.9
    regulated_linear_scaling_min_speed: 0.25
    use_rotate_to_heading: true
    allow_reversing: false
    rotate_to_heading_min_angle: 0.785
    max_angular_accel: 3.2
    max_robot_pose_search_dist: 10.0
```

## 4.7 Hardware Abstraction Layer

```python
# robotics/adapters/base.py
from typing import Protocol, runtime_checkable
from robotics.models.robot_state import RobotState, SensorFrame, Vector2D

@runtime_checkable
class RobotAdapter(Protocol):
    """
    Hardware abstraction interface.
    Both SimulationRobotAdapter and PhysicalRobotAdapter implement this.
    The fleet orchestrator and ALL policies interact ONLY through this interface.
    Never import SimulationRobotAdapter in non-robotics code.
    """
    
    @property
    def robot_id(self) -> str:
        """Unique robot identifier."""
        ...
    
    def move(self, linear_vel: float, angular_vel: float) -> None:
        """
        Command robot movement.
        linear_vel: m/s [-1.0, 1.0]
        angular_vel: rad/s [-1.5, 1.5]
        Clipped to limits if out of range.
        """
        ...
    
    def stop(self) -> None:
        """Immediately stop the robot. Higher priority than move()."""
        ...
    
    def navigate_to(self, x: float, y: float, theta: float = 0.0) -> str:
        """
        Send navigation goal to Nav2.
        Returns goal_id for status tracking.
        Non-blocking — use get_nav_status() to poll.
        """
        ...
    
    def cancel_navigation(self) -> None:
        """Cancel current navigation goal."""
        ...
    
    def get_state(self) -> RobotState:
        """Current robot state snapshot. Never cached — always fresh."""
        ...
    
    def get_battery(self) -> float:
        """Battery percentage [0.0, 1.0]."""
        ...
    
    def get_sensors(self) -> SensorFrame:
        """Latest sensor data snapshot."""
        ...
    
    def is_available(self) -> bool:
        """True if robot can accept new task assignments."""
        ...


# robotics/adapters/simulation.py
class SimulationRobotAdapter:
    """
    RobotAdapter backed by Gazebo via ROS 2.
    Publishes to /robot_{id}/cmd_vel.
    Sends Nav2 goals to /robot_{id}/navigate_to_pose action server.
    Reads state from /robot_{id}/status topic.
    """
    
    def __init__(self, robot_id: str, ros_node: "rclpy.node.Node") -> None:
        self._id = robot_id
        self._node = ros_node
        self._state: RobotState | None = None
        self._setup_ros_interfaces()


# robotics/adapters/physical.py
class PhysicalRobotAdapter:
    """
    STUB — Phase 1–8. Not yet implemented.
    Will wrap real ROS 2 hardware interface when physical robots are available.
    
    STATUS: STUB
    """
    
    def __init__(self, robot_id: str, ros_node: "rclpy.node.Node") -> None:
        raise NotImplementedError(
            "PhysicalRobotAdapter is STUB. "
            "Physical robot integration is post-MVP. "
            "See docs/sim-to-real.md for the implementation plan."
        )
```

## 4.8 Fleet Agent Node

```python
# robotics/nodes/fleet_agent_node.py
"""
ROS 2 lifecycle node running on each robot.
Receives task assignments from the fleet manager.
Reports status back to the fleet manager.
Does NOT make policy decisions — it executes them.
"""
import rclpy
from rclpy.lifecycle import LifecycleNode
from rclpy.lifecycle.node import LifecycleState, TransitionCallbackReturn

class FleetAgentNode(LifecycleNode):
    """
    Per-robot node. Namespace: /robot_{id}/
    
    Subscribes:
        ~/task_assignment     (fleet_msgs/TaskAssignment)
        ~/fleet_command       (fleet_msgs/FleetCommand)
    
    Publishes:
        ~/status              (fleet_msgs/RobotStatus, 20Hz)
        ~/task_events         (fleet_msgs/TaskEvent, on event)
    
    Uses Nav2 action client for navigation goals.
    """
    
    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._setup_publishers()
        self._setup_subscribers()
        self._setup_action_clients()
        return TransitionCallbackReturn.SUCCESS
    
    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._status_timer = self.create_timer(
            1.0 / 20.0,  # 20Hz
            self._publish_status
        )
        return TransitionCallbackReturn.SUCCESS
    
    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._status_timer.cancel()
        return TransitionCallbackReturn.SUCCESS
    
    def _on_task_assignment(self, msg) -> None:
        """Execute the assigned task via Nav2."""
        ...
    
    def _publish_status(self) -> None:
        """Publish current robot state at 20Hz."""
        ...
```

## 4.9 Battery Model

```python
# robotics/battery/battery_model.py
"""
Simple linear battery model for simulation.
Real robots will use hardware battery telemetry.
"""
import time

class BatteryModel:
    """
    Drains based on robot activity.
    
    Rates (empirically tuned):
        Moving:     0.10 units/second
        Idle:       0.02 units/second
        Delivering: 0.12 units/second (more arm/gripper activity)
        Charging:  +0.30 units/second
    
    Starting charge: set per-scenario (scenario_generator controls initial level)
    """
    
    DRAIN_RATES = {
        "moving":     0.10,
        "idle":       0.02,
        "delivering": 0.12,
        "blocked":    0.03,
        "failed":     0.00,
    }
    CHARGE_RATE = 0.30
    LOW_BATTERY_THRESHOLD = 0.15
    
    def __init__(self, initial_pct: float = 1.0) -> None:
        if not 0.0 <= initial_pct <= 1.0:
            raise ValueError(f"initial_pct must be in [0, 1], got {initial_pct}")
        self._pct = initial_pct
        self._last_update = time.monotonic()
    
    def step(self, nav_state: str, dt: float | None = None) -> float:
        """
        Advance battery model by dt seconds.
        If dt is None, use wall-clock elapsed since last call.
        Returns new battery percentage.
        """
        now = time.monotonic()
        if dt is None:
            dt = now - self._last_update
        self._last_update = now
        
        if nav_state == "charging":
            self._pct = min(1.0, self._pct + self.CHARGE_RATE * dt)
        else:
            rate = self.DRAIN_RATES.get(nav_state, self.DRAIN_RATES["idle"])
            self._pct = max(0.0, self._pct - rate * dt)
        
        return self._pct
    
    @property
    def pct(self) -> float:
        return self._pct
    
    @property
    def is_low(self) -> bool:
        return self._pct <= self.LOW_BATTERY_THRESHOLD
    
    @property
    def is_depleted(self) -> bool:
        return self._pct <= 0.0
```

## 4.10 Robotics Rules

1. **All nodes must be lifecycle nodes** (`rclpy.lifecycle.LifecycleNode`). Nodes that cannot be configured/activated/deactivated cleanly break the demo.
2. **Never use Python threading.Thread inside ROS 2 callback functions.** Use `rclpy.executors.MultiThreadedExecutor` when concurrency is needed.
3. **All ROS 2 messages use timestamps.** Never publish a message without setting `header.stamp = self.get_clock().now().to_msg()`.
4. **QoS profiles must be explicit.** Never use default QoS for sensor topics — use `SensorDataQoS()`.
5. **Launch files in Python, not XML.** Python launch files allow conditional logic.
6. **One namespace per robot.** All topics under `/robot_{n}/`. Never mix robot topics into the global namespace.
7. **Hardware abstraction is mandatory.** If your code imports `SimulationRobotAdapter` anywhere outside `robotics/adapters/`, it's wrong.

---

# SECTION 5 — THIRD-PARTY INTEGRATION SKILLS

## 5.0 Third-Party Mission

The third-party integration agent handles all external service integrations: Gazebo, MLflow, MinIO, Redis, PostgreSQL, Prometheus/Grafana, and the Konnex network. The agent must verify every integration against current documentation before implementing it.

## 5.1 Approved Third-Party Services

| Service | Purpose | Version | Auth |
|---|---|---|---|
| **Gazebo Harmonic** | Simulation | Harmonic (2023+) | None (local) |
| **ROS 2 Humble** | Robot middleware | Humble LTS | None (DDS) |
| **PostgreSQL** | Mission/policy/evaluation persistence | 16+ | username/password |
| **Redis** | Task queue, caching, WS pub/sub | 7+ | password (optional) |
| **MinIO** | Artifact object storage | RELEASE.2024-03+ | access key + secret |
| **MLflow** | Experiment tracking | 2.11+ | None (local server) |
| **Prometheus** | Metrics collection | 2.51+ | None (scrape) |
| **Grafana** | Metrics dashboards | 10.4+ | admin password |
| **GitHub Actions** | CI/CD | N/A | GITHUB_TOKEN |
| **Docker Hub / GHCR** | Container registry | N/A | token |
| **Konnex Network** | PoPW rewards / policy registry | VERIFY SDK | API key |

**Services explicitly NOT used (and why):**

| Service | Reason not used |
|---|---|
| Kafka | Message volume doesn't justify it at MVP scale |
| Kubernetes | Adds deployment complexity before the subnet has users |
| Isaac Sim | GPU requirement; Gazebo sufficient for MVP |
| Firebase | Not needed; backend handles auth |
| Twilio / SendGrid | No notifications in MVP |

## 5.2 MLflow Integration

```python
# ml/training/callbacks.py
import mlflow
import mlflow.pytorch
from pathlib import Path

class MLflowTrainingCallback:
    """
    Logs MAPPO training metrics to MLflow.
    Call .on_epoch_end() at the end of each training epoch.
    """
    
    def __init__(
        self,
        experiment_name: str,
        run_name: str,
        tracking_uri: str,
    ) -> None:
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        self._run = mlflow.start_run(run_name=run_name)
    
    def log_params(self, params: dict) -> None:
        """Log hyperparameters. Call once at the start of training."""
        mlflow.log_params(params)
    
    def on_step_end(self, step: int, metrics: dict[str, float]) -> None:
        mlflow.log_metrics(metrics, step=step)
    
    def save_checkpoint(self, model, step: int) -> None:
        path = Path(f"ml/checkpoints/step_{step}.pt")
        import torch
        torch.save(model.state_dict(), path)
        mlflow.log_artifact(str(path))
    
    def end_run(self, status: str = "FINISHED") -> None:
        mlflow.end_run(status=status)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.end_run()
```

### MLflow Experiment Schema

Every ML experiment MUST log:

```python
mlflow.log_params({
    # Identity
    "experiment_id": "exp_004",
    "policy": "mappo",
    "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
    
    # Environment
    "scenario": "warehouse_v1",
    "robot_count": 5,
    "task_count": 20,
    "seed": 42,
    "env_version": "v1.0.0",
    
    # Algorithm
    "algorithm": "MAPPO",
    "learning_rate": 3e-4,
    "n_steps": 2048,
    "batch_size": 256,
    "n_epochs": 10,
    "gamma": 0.99,
    "total_timesteps": 5_000_000,
    
    # Hardware
    "device": "cpu",  # or "cuda:0"
    "n_envs": 4,
})

# Per-step metrics
mlflow.log_metrics({
    "mean_reward": ...,
    "task_success_rate": ...,
    "collision_count": ...,
    "episode_length": ...,
    "policy_loss": ...,
    "value_loss": ...,
    "entropy": ...,
}, step=global_step)
```

## 5.3 MinIO / S3 Integration

```python
# backend/services/storage_service.py
"""
Handles all artifact storage operations.
Uses aiobotocore for async S3-compatible operations.
Works with MinIO locally and AWS S3 in production.
"""
import aiobotocore.session
from backend.config import settings
import structlog

logger = structlog.get_logger(__name__)

class StorageService:
    
    BUCKET = settings.minio_bucket
    
    async def upload_artifact(
        self,
        data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Uploads artifact to object storage.
        Returns the storage URL.
        key format: {policy_hash}/{artifact_type}/{filename}
        """
        session = aiobotocore.session.get_session()
        async with session.create_client(
            "s3",
            endpoint_url=f"http://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
        ) as client:
            await client.put_object(
                Bucket=self.BUCKET,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            logger.info("artifact_uploaded", key=key, size=len(data))
            return f"s3://{self.BUCKET}/{key}"
    
    async def download_artifact(self, key: str) -> bytes:
        session = aiobotocore.session.get_session()
        async with session.create_client(
            "s3",
            endpoint_url=f"http://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
        ) as client:
            response = await client.get_object(Bucket=self.BUCKET, Key=key)
            async with response["Body"] as stream:
                return await stream.read()
```

## 5.4 Redis Integration

```python
# backend/workers/arq_worker.py
"""
ARQ (Async Redis Queue) worker configuration.
Handles long-running background tasks:
  - benchmark runs
  - ML training jobs
  - policy evaluations
"""
import arq
from backend.config import settings
from backend.workers.tasks.benchmark_task import run_benchmark
from backend.workers.tasks.evaluation_task import run_evaluation

async def startup(ctx):
    # Initialize shared resources (DB connections, etc.)
    pass

async def shutdown(ctx):
    pass

class WorkerSettings:
    functions = [run_benchmark, run_evaluation]
    redis_settings = arq.connections.RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 4
    job_timeout = 3600  # 1 hour max per job
    keep_result = 86400  # keep results for 24h


# Dispatching a benchmark job from an API endpoint
async def dispatch_benchmark(policy_id: str, scenario_id: str, seed: int):
    pool = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job(
        "run_benchmark",
        policy_id=policy_id,
        scenario_id=scenario_id,
        seed=seed,
    )
```

## 5.5 Prometheus Metrics

```python
# backend/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Summary

# Mission metrics
missions_total = Counter(
    "fleet_missions_total",
    "Total missions started",
    ["scenario", "policy"],
)
mission_success_rate = Gauge(
    "fleet_mission_success_rate",
    "Rolling mission task success rate",
    ["policy"],
)
mission_duration_seconds = Histogram(
    "fleet_mission_duration_seconds",
    "Mission completion time in seconds",
    ["policy"],
    buckets=[30, 60, 120, 180, 300, 600],
)

# Robot metrics
robot_collision_total = Counter(
    "fleet_robot_collision_total",
    "Total collision events",
    ["robot_id", "collision_type"],
)
robot_battery_pct = Gauge(
    "fleet_robot_battery_pct",
    "Current battery percentage per robot",
    ["robot_id"],
)
fleet_utilization = Gauge(
    "fleet_utilization",
    "Fraction of robots with active tasks",
)

# Validator metrics
validator_evaluation_duration = Histogram(
    "fleet_validator_evaluation_seconds",
    "Time to complete a policy evaluation",
    ["policy", "scenario"],
)
validator_score = Histogram(
    "fleet_validator_popw_score",
    "PoPW scores produced by validator",
    ["policy"],
    buckets=[0, 20, 40, 60, 70, 80, 85, 90, 95, 100],
)

# API metrics
api_request_duration = Histogram(
    "fleet_api_request_duration_seconds",
    "API request latency",
    ["method", "path", "status"],
)
```

### Prometheus scrape config

```yaml
# infra/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: fleet-backend
    static_configs:
      - targets: ["backend:8000"]
    metrics_path: /metrics

  - job_name: gazebo-bridge
    static_configs:
      - targets: ["backend:8001"]
    metrics_path: /ros-metrics

  - job_name: postgres
    static_configs:
      - targets: ["postgres-exporter:9187"]

  - job_name: redis
    static_configs:
      - targets: ["redis-exporter:9121"]
```

## 5.6 Konnex Network Integration

> **CRITICAL: This section describes STUB interfaces only.**  
> No actual Konnex API calls are implemented until the SDK is reviewed.  
> All methods in `KonnexAdapter` raise `NotImplementedError` with `# TODO: verify SDK` until verified.

```python
# protocol/konnex/adapter.py
"""
KonnexAdapter — Boundary between the Fleet subnet and the Konnex network.

STATUS: STUB — All methods raise NotImplementedError.

Before implementing:
1. Fetch current Konnex developer docs (verified: https://docs.konnex.world — docs.konnex.network and gitbook.konnex.network DO NOT exist)
2. Install actual Konnex SDK (verify package name on npm/pip)
3. Confirm available API endpoints and authentication method
4. Update AGENTS.md Section 5.6 with confirmed SDK details
5. Remove NotImplementedError and implement against verified API

The fleet subnet core (robotics, fleet orchestration, ML, validator)
has ZERO imports from this module. This adapter depends on fleet types,
not the other way around.
"""

from dataclasses import dataclass
import structlog
from protocol.powp.proof import EvaluationArtifact

logger = structlog.get_logger(__name__)

@dataclass
class MissionMetadata:
    """Minimal mission data suitable for on-chain registration."""
    mission_id: str
    scenario_id: str
    seed: int
    robot_count: int
    task_count: int
    env_version: str

@dataclass
class PolicyRegistration:
    """Minimal policy data for on-chain registration."""
    policy_id: str
    policy_hash: str
    algorithm: str
    author: str

class KonnexAdapterError(Exception):
    """Raised when Konnex network operations fail."""

class KonnexAdapter:
    """
    Adapter to the Konnex network.
    STUB — see module docstring.
    """
    
    def __init__(self, network_url: str, api_key: str) -> None:
        if not network_url:
            logger.warning("konnex_adapter_no_url", message="KonnexAdapter initialized without network URL. All calls will fail.")
        self._url = network_url
        self._api_key = api_key
    
    def submit_mission(self, metadata: MissionMetadata) -> str:
        """
        Register a mission on the Konnex network.
        Returns: mission_chain_id
        
        STATUS: STUB — TODO: verify Konnex SDK submitMission() signature
        """
        raise NotImplementedError(
            "KonnexAdapter.submit_mission() is STUB. "
            "Verify Konnex SDK before implementing."
        )
    
    def register_policy(self, policy: PolicyRegistration) -> str:
        """
        Register a policy on the Konnex network.
        Returns: policy_chain_id
        
        STATUS: STUB — TODO: verify Konnex SDK registerPolicy() signature
        """
        raise NotImplementedError(
            "KonnexAdapter.register_policy() is STUB."
        )
    
    def publish_proof(self, artifact: EvaluationArtifact) -> str:
        """
        Publish a PoPW evaluation proof on-chain.
        Returns: transaction_hash
        
        STATUS: STUB — TODO: verify Konnex SDK publishProof() signature
        """
        raise NotImplementedError(
            "KonnexAdapter.publish_proof() is STUB."
        )
    
    def query_rewards(self, policy_chain_id: str) -> float:
        """
        Query pending KNX rewards for a policy.
        Returns: reward_amount in KNX
        
        STATUS: STUB — TODO: verify Konnex SDK queryRewards() signature
        """
        raise NotImplementedError(
            "KonnexAdapter.query_rewards() is STUB."
        )
    
    def submit_evaluation(
        self,
        policy_chain_id: str,
        artifact_hash: str,
        score: float,
    ) -> str:
        """
        Submit evaluation result and score to the Konnex network.
        Returns: evaluation_chain_id
        
        STATUS: STUB — TODO: verify Konnex SDK submitEvaluation() signature
        """
        raise NotImplementedError(
            "KonnexAdapter.submit_evaluation() is STUB."
        )
```

## 5.7 GitHub Actions CI

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.10"
  NODE_VERSION: "20"

jobs:

  lint-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip
      - run: pip install ruff mypy bandit
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy . --ignore-missing-imports
      - run: bandit -r . -ll -x tests/

  lint-typescript:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: cd frontend && npm ci
      - run: cd frontend && npm run lint
      - run: cd frontend && npm run type-check
      - run: cd frontend && npm run test:unit -- --reporter=verbose

  unit-tests:
    runs-on: ubuntu-latest
    needs: [lint-python]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip
      - run: pip install -r requirements-dev.txt
      - run: |
          pytest tests/unit/ \
            -v \
            --cov=. \
            --cov-report=xml \
            --cov-report=term-missing \
            --tb=short \
            --strict-markers
      - uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  integration-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests]
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: fleet_test
          POSTGRES_USER: fleet
          POSTGRES_PASSWORD: fleet_test
        options: --health-cmd pg_isready --health-interval 5s --health-retries 5
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        options: --health-cmd "redis-cli ping" --health-interval 5s
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip
      - run: pip install -r requirements-dev.txt
      - run: |
          pytest tests/integration/ \
            -v \
            --tb=short \
            --strict-markers
        env:
          DATABASE_URL: postgresql://fleet:fleet_test@localhost/fleet_test
          REDIS_URL: redis://localhost:6379/0
          FLEET_API_KEY: test-key

  build-docker:
    runs-on: ubuntu-latest
    needs: [integration-tests]
    steps:
      - uses: actions/checkout@v4
      - run: docker-compose build
      - run: docker-compose config
```

## 5.8 Third-Party Rules

1. **Never invent API signatures.** If you don't have the current docs, write a stub with `# TODO: verify`.
2. **All credentials via environment variables.** No hard-coded secrets in any file, including docker-compose.yml.
3. **Test against local services in CI.** Use service containers for PostgreSQL and Redis in GitHub Actions — never mock them out.
4. **Object storage paths are deterministic:** `{policy_hash}/{artifact_type}/{filename}` — enables deduplication.
5. **Prometheus metrics must have descriptive labels.** `robot_id`, `policy`, `scenario` labels on all metrics.
6. **MLflow runs must log git commit hash.** Without it, experiments cannot be reproduced.
7. **Konnex SDK integration requires human review before implementation.** Do not auto-generate SDK calls.

---

# SECTION 6 — INTER-DOMAIN CONTRACTS

## 6.0 Why This Section Exists

Every integration bug in complex systems comes from two domains having different assumptions about what data flows between them. This section defines every **cross-domain contract** explicitly. If you are working in one domain and touching another domain's interface, read this section.

## 6.1 Frontend ↔ Backend Contract

### REST API Response Format

```typescript
// All API responses follow this shape
interface ApiResponse<T> {
  data: T
  request_id: string
  timestamp: string     // ISO 8601
}

interface ApiError {
  error: string         // machine-readable code: "mission_not_found"
  message: string       // human-readable
  request_id: string
  timestamp: string
}

// Robot state as returned by GET /robots/:id
interface RobotResponse {
  id: string
  position: { x: number; y: number }
  orientation: number
  velocity: { x: number; y: number }
  battery_pct: number
  nav_state: 'idle' | 'moving' | 'delivering' | 'blocked' | 'charging' | 'failed'
  current_task_id: string | null
  comm_state: 'online' | 'degraded' | 'offline'
  in_collision: boolean
  updated_at: string
}
```

### WebSocket Event Format

```typescript
// All WebSocket messages follow this discriminated union
type FleetEvent =
  | { type: 'ROBOT_STATE_UPDATE'; robot_id: string; state: Partial<RobotResponse> }
  | { type: 'TASK_ASSIGNED';      task_id: string; robot_id: string; policy: string }
  | { type: 'TASK_COMPLETED';     task_id: string; robot_id: string; elapsed_s: number }
  | { type: 'COLLISION_DETECTED'; robot_id: string; other_id: string; pos: [number, number] }
  | { type: 'ROBOT_FAILED';       robot_id: string; failure_type: string }
  | { type: 'MISSION_COMPLETE';   mission_id: string; score: number; tasks_completed: number }
  | { type: 'EVALUATION_COMPLETE';evaluation_id: string; score: number; artifact_hash: string }
  | { type: 'SIMULATOR_OFFLINE' }
  | { type: 'SIMULATOR_ONLINE' }
```

**Contract rules:**
- Frontend never sends commands via WebSocket (read-only)
- Backend always sends `SIMULATOR_OFFLINE` when Gazebo disconnects
- Robot positions are in world frame (meters), origin at warehouse center
- `battery_pct` is always [0.0, 1.0]
- `orientation` is radians, range [-π, π]

## 6.2 Backend ↔ Fleet Orchestrator Contract

The fleet orchestrator runs **in-process** with the backend. It is not a separate service. The backend calls it via direct Python method calls.

```python
# The only interface the backend uses
class FleetOrchestrator:
    async def create_mission(self, config: MissionConfig) -> str: ...      # returns mission_id
    async def get_fleet_state(self) -> FleetState: ...
    async def assign_policy(self, policy_id: str) -> None: ...
    async def stop_mission(self) -> None: ...
    async def inject_failure(self, robot_id: str, failure_type: str) -> None: ...
```

The orchestrator publishes events to `backend.events.bus`. The backend's WebSocket handler subscribes to those events and broadcasts them to frontend clients.

## 6.3 Backend ↔ ROS 2 Contract

All ROS 2 communication is mediated by `backend/ros/bridge.py`. The rest of the backend is ROS-agnostic.

```python
# Events flowing FROM ROS 2 TO backend (via ROSBridge)
ros_to_backend_events = [
    "ROBOT_STATE_UPDATE",   # from /robot_n/status topic
    "COLLISION_DETECTED",   # from /fleet/collisions topic
    "TASK_EVENT",           # from /fleet/task_events topic
    "FLEET_STATUS_UPDATE",  # from /fleet/status topic
]

# Commands flowing FROM backend TO ROS 2 (via ROSBridge)
backend_to_ros_commands = [
    "ASSIGN_TASK",          # to /fleet/assign_task service
    "INJECT_FAILURE",       # to /fleet/inject_failure service
    "RESET_MISSION",        # to /fleet/reset_mission service
    "NAVIGATE_TO",          # to /robot_n/navigate_to_pose action
]
```

## 6.4 Fleet Orchestrator ↔ Robot Adapter Contract

```python
# The orchestrator uses ONLY these methods from RobotAdapter
robot.get_state()          # → RobotState (called at orchestrator tick rate, 10Hz)
robot.is_available()       # → bool
robot.navigate_to(x, y, theta)  # → goal_id
robot.cancel_navigation()  # → None
robot.stop()               # → None (emergency)
```

The orchestrator **never** calls `robot.move()` directly. That is for low-level velocity control only, which happens inside the Nav2 stack.

## 6.5 Fleet Orchestrator ↔ ML Policy Contract

```python
# Policies receive only this input
fleet_state = FleetState(
    robots=[RobotState(...) for each robot],
    tasks=[Task(...) for each pending task],
    timestamp=datetime.utcnow(),
)

# Policies return only this output
assignments = [
    Assignment(robot_id="robot_0", task_id="task_7"),
    Assignment(robot_id="robot_2", task_id="task_3"),
    ...
]

# Policy is called at assignment intervals (configurable, default: 5s or on task completion)
# Policy must complete within 500ms or it is timed out and previous assignment used
```

## 6.6 Validator ↔ Policy Container Contract

```
Validator starts policy container via Docker API.
Passes scenario via environment variable: FLEET_SCENARIO_JSON='{"scenario_id":...}'
Policy container exposes HTTP API on port 5001:

  GET  /health         → {"status": "ready"}
  POST /assign         → accepts FleetState JSON, returns Assignment[] JSON
  POST /step           → accepts Observation JSON, returns Action JSON
  GET  /metadata       → returns PolicyMetadata JSON
```

Policy containers have **no network access** (except to receive scenario from validator). If a container tries to make outbound HTTP calls, it is rejected and marked `POLICY_CRASH`.

## 6.7 Validator ↔ Backend Contract

```python
# Validator calls backend when evaluation completes
# POST /api/v1/evaluations (internal, authenticated with internal API key)

evaluation_result = {
    "evaluation_id": "eval_uuid",
    "policy_id": "policy_uuid",
    "mission_id": "mission_uuid",
    "status": "COMPLETE",           # or POLICY_CRASH, TIMEOUT, etc.
    "final_score": 94.2,
    "score_components": {
        "mission_success": 0.967,
        "safety": 1.0,
        "efficiency": 0.87,
        "energy": 0.82,
        "coordination": 0.91,
        "robustness": 1.0,
    },
    "collision_count": 0,
    "tasks_completed": 29,
    "tasks_total": 30,
    "elapsed_seconds": 271.4,
    "artifact_hash": "sha256:abc123...",
    "artifact_url": "s3://fleet-artifacts/policy_hash/eval_id/artifact.json",
}
```

## 6.8 PoPW Adapter ↔ Konnex Adapter Contract

```python
# PoPW adapter serializes evaluation to a proof artifact
# Konnex adapter submits it to the network

proof = ProofOfPhysicalWork(
    mission_id=...,
    policy_id=...,
    policy_hash=...,         # SHA-256 of policy weights
    scenario_id=...,
    seed=...,
    env_version=...,
    score=94.2,
    artifact_hash=...,       # SHA-256 of full evaluation artifact
    artifact_url=...,        # S3 URL of full artifact
    timestamp=...,
)

# Konnex adapter receives ProofOfPhysicalWork (not raw EvaluationArtifact)
# The konnex adapter must never import EvaluationArtifact directly
# All types must be defined in protocol/powp/proof.py
```

---

## 6.9 Development Workflow

```
1. Pick a task from the current phase
2. Check which domains it touches (Frontend? Backend? Robotics? Third-party?)
3. Read the relevant AGENTS.md sections for each domain
4. Re-read the Inter-Domain Contract for each domain boundary you touch
5. Run: find . -type f | head -80  (understand current state)
6. Implement the smallest working component
7. Write tests before moving on
8. Run: make lint && make test
9. Only commit if both pass
10. Update the relevant docs/ file
11. Move to next task
```

## 6.10 Final Reminder: The Demo Standard

At the end of every phase, ask:

> "If a Konnex reviewer cloned this repo right now and ran `make demo`, would they see 5 autonomous robots completing warehouse tasks, a live dashboard, and a reproducible PoPW score — all in under 3 minutes?"

If the answer is no, the phase is not complete.

The difference between a grant and a rejection is not the architecture diagram. It is whether the demo works.

---

---

# SECTION 7 — FLEET INTELLIGENCE ENGINE (EXTENDED)

## 7.0 Purpose

This section details the Fleet Intelligence Engine — the proprietary core that makes this subnet different from a robotics tutorial project. Every function here must be tested. Every algorithm must be benchmarked against at least one simpler alternative.

## 7.1 FleetOrchestrator

```python
# fleet/orchestrator.py
class FleetOrchestrator:
    """
    Central coordinator for the robot fleet.
    Owns task assignment, monitoring, and failure recovery.
    Does NOT control individual robot actuators.
    Does NOT implement ML policy logic.
    """
    
    def __init__(
        self,
        robots: list[RobotAdapter],
        policy: TaskAllocator,
        mission_manager: MissionManager,
    ) -> None: ...
    
    async def run(self) -> None:
        """Main orchestration loop. Non-blocking."""
    
    def assign_tasks(self, tasks: list[Task]) -> list[Assignment]:
        """Delegate to current policy."""
    
    def handle_robot_failure(self, robot_id: str) -> None:
        """Detect, log, and trigger task reassignment."""
    
    def get_fleet_state(self) -> FleetState:
        """Snapshot of all robot states + active tasks."""
```

### TaskAllocator Protocol

```python
# fleet/task_allocator/base.py
from typing import Protocol

class TaskAllocator(Protocol):
    """All allocators must implement this interface."""
    
    @property
    def name(self) -> str: ...
    
    def assign(
        self,
        robots: list[RobotState],
        tasks: list[Task],
    ) -> list[Assignment]:
        """
        Returns one Assignment per available robot.
        Must not modify input lists.
        Must handle the case where tasks < robots.
        Must handle the case where robots < tasks.
        """
```

### CostOptimizerAllocator

```python
# fleet/task_allocator/cost_optimizer.py
@dataclass
class CostWeights:
    distance: float = 0.4
    battery: float = 0.2
    priority: float = 0.2
    congestion: float = 0.1
    collision_risk: float = 0.1

class CostOptimizerAllocator:
    name = "cost_optimizer"
    
    def __init__(self, weights: CostWeights | None = None): ...
    
    def cost(self, robot: RobotState, task: Task, fleet: FleetState) -> float:
        """
        Multi-factor cost. Lower = better assignment.
        All components normalized to [0, 1] before weighting.
        
        cost(robot, task) = (
            w1 * normalize(distance(robot.pos, task.pickup)) +
            w2 * normalize(1 - robot.battery_pct) +
            w3 * normalize(task_priority_inverse(task.priority)) +
            w4 * normalize(local_congestion(robot.pos)) +
            w5 * normalize(collision_risk(robot.pos, task.pickup))
        )
        """
```

### Mission Decomposition

```python
# fleet/mission_manager.py
"""
Receives a high-level mission description and decomposes it into
individual atomic tasks that can be assigned to robots.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid

class TaskPriority(int, Enum):
    LOW    = 1
    MEDIUM = 2
    HIGH   = 3
    URGENT = 4

class TaskStatus(str, Enum):
    PENDING    = "pending"
    ASSIGNED   = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED  = "completed"
    FAILED     = "failed"
    REASSIGNED = "reassigned"

@dataclass
class TaskLocation:
    x: float
    y: float
    zone_id: str = ""

@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pickup: TaskLocation = field(default_factory=TaskLocation)
    delivery: TaskLocation = field(default_factory=TaskLocation)
    priority: TaskPriority = TaskPriority.MEDIUM
    weight_kg: float = 1.0
    status: TaskStatus = TaskStatus.PENDING
    assigned_robot: Optional[str] = None
    created_at: float = 0.0
    assigned_at: Optional[float] = None
    completed_at: Optional[float] = None
    attempts: int = 0

@dataclass
class MissionConfig:
    mission_id: str
    scenario_id: str
    seed: int
    robot_count: int
    task_count: int
    time_limit_s: float = 600.0
    failure_injection: bool = False
    comm_degradation: bool = False

class MissionManager:
    """
    Owns the full lifecycle of a mission:
    1. Receive MissionConfig
    2. Generate tasks via ScenarioGenerator
    3. Track task states
    4. Detect mission completion
    5. Publish MissionCompleteEvent
    
    Does NOT assign tasks — that is the TaskAllocator's job.
    Does NOT command robots — that is the Fleet Orchestrator's job.
    """
    
    def __init__(self, config: MissionConfig) -> None:
        self._config = config
        self._tasks: dict[str, Task] = {}
        self._start_time: Optional[float] = None
    
    def initialize(self) -> list[Task]:
        """
        Generate tasks from scenario config + seed.
        Returns list of Task objects ready for allocation.
        Uses the given seed to build the scenario.
        """
        from simulation.scenarios.scenario_generator import ScenarioGenerator
        gen = ScenarioGenerator()
        scenario = gen.generate(
            seed=self._config.seed,
            robot_count=self._config.robot_count,
            task_count=self._config.task_count,
        )
        self._tasks = {t.id: t for t in scenario.tasks}
        return list(self._tasks.values())
    
    def mark_assigned(self, task_id: str, robot_id: str, timestamp: float) -> None:
        task = self._require_task(task_id)
        if task.status != TaskStatus.PENDING:
            raise ValueError(f"Task {task_id} is {task.status}, cannot assign")
        task.status = TaskStatus.ASSIGNED
        task.assigned_robot = robot_id
        task.assigned_at = timestamp
        task.attempts += 1
    
    def mark_completed(self, task_id: str, timestamp: float) -> None:
        task = self._require_task(task_id)
        task.status = TaskStatus.COMPLETED
        task.completed_at = timestamp
    
    def mark_failed(self, task_id: str) -> None:
        task = self._require_task(task_id)
        task.status = TaskStatus.FAILED
        task.assigned_robot = None
    
    def recover_tasks_from_robot(self, robot_id: str) -> list[Task]:
        """
        Called when a robot fails.
        Recovers all tasks assigned to that robot back to PENDING.
        Returns recovered tasks for re-assignment.
        """
        recovered = []
        for task in self._tasks.values():
            if task.assigned_robot == robot_id and task.status in {
                TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS
            }:
                task.status = TaskStatus.PENDING
                task.assigned_robot = None
                recovered.append(task)
        return recovered
    
    @property
    def pending_tasks(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
    
    @property
    def completed_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED)
    
    @property
    def is_complete(self) -> bool:
        return self.completed_count == len(self._tasks)
    
    @property
    def success_rate(self) -> float:
        if not self._tasks:
            return 0.0
        return self.completed_count / len(self._tasks)
    
    def _require_task(self, task_id: str) -> Task:
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found in mission")
        return task
```

## 7.2 Task Allocator — Nearest Robot

```python
# fleet/task_allocator/nearest.py
import math
from fleet.task_allocator.base import TaskAllocator
from robotics.models.robot_state import RobotState
from fleet.mission_manager import Task, TaskStatus

@dataclass
class Assignment:
    robot_id: str
    task_id: str
    cost: float = 0.0

class NearestTaskAllocator:
    """
    Greedy assignment: each available robot is assigned the nearest pending task.
    
    Complexity: O(R × T) where R = robots, T = tasks.
    This is the baseline all other allocators must beat.
    
    Known weaknesses:
    - Does not consider other robots' intended paths (congestion-blind)
    - Does not consider task priority
    - Does not consider battery level
    - Can create deadlock if two robots are assigned converging paths
    
    These weaknesses are documented intentionally — they are what MARL should learn to avoid.
    """
    
    name = "nearest"
    
    def assign(self, robots: list[RobotState], tasks: list[Task]) -> list[Assignment]:
        available = [r for r in robots if r.nav_state.value == "idle" and r.battery_pct > 0.1]
        pending = [t for t in tasks if t.status == TaskStatus.PENDING]
        
        assignments: list[Assignment] = []
        claimed_task_ids: set[str] = set()
        
        for robot in available:
            nearest_task = None
            nearest_dist = float("inf")
            
            for task in pending:
                if task.id in claimed_task_ids:
                    continue
                dist = _euclidean(robot.position.x, robot.position.y,
                                  task.pickup.x, task.pickup.y)
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest_task = task
            
            if nearest_task:
                assignments.append(Assignment(
                    robot_id=robot.id,
                    task_id=nearest_task.id,
                    cost=nearest_dist,
                ))
                claimed_task_ids.add(nearest_task.id)
        
        return assignments

def _euclidean(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
```

## 7.3 Task Allocator — Hungarian

```python
# fleet/task_allocator/hungarian.py
import math
import numpy as np
from scipy.optimize import linear_sum_assignment
from fleet.task_allocator.base import TaskAllocator
from fleet.task_allocator.nearest import Assignment, _euclidean

class HungarianAllocator:
    """
    Optimal bipartite matching using the Hungarian algorithm.
    Minimizes total fleet distance traveled to task pickup locations.
    
    Complexity: O(max(R, T)^3) due to scipy's implementation.
    At 5 robots and 30 tasks, this is negligible (<1ms).
    
    Improvement over NearestTaskAllocator:
    - Globally optimal assignment (minimizes total distance)
    - Prevents two robots from being assigned tasks that require crossing paths
    
    Still does NOT consider:
    - Battery levels (add CostOptimizerAllocator for this)
    - Task priority
    - Congestion
    """
    
    name = "hungarian"
    
    def assign(self, robots: list, tasks: list) -> list[Assignment]:
        available = [r for r in robots if r.nav_state.value == "idle" and r.battery_pct > 0.1]
        pending = [t for t in tasks if t.status.value == "pending"]
        
        if not available or not pending:
            return []
        
        n_robots = len(available)
        n_tasks = len(pending)
        
        # Build cost matrix: shape (n_robots, n_tasks)
        # Each entry is Euclidean distance from robot to task pickup
        cost_matrix = np.zeros((n_robots, n_tasks), dtype=np.float64)
        for i, robot in enumerate(available):
            for j, task in enumerate(pending):
                cost_matrix[i, j] = _euclidean(
                    robot.position.x, robot.position.y,
                    task.pickup.x, task.pickup.y,
                )
        
        # If more robots than tasks, pad with large costs (unassigned robots get dummy tasks)
        if n_robots > n_tasks:
            padding = np.full((n_robots, n_robots - n_tasks), fill_value=1e9)
            cost_matrix = np.hstack([cost_matrix, padding])
        
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        assignments = []
        for robot_idx, task_idx in zip(row_ind, col_ind):
            if task_idx < n_tasks:  # Skip padding columns
                assignments.append(Assignment(
                    robot_id=available[robot_idx].id,
                    task_id=pending[task_idx].id,
                    cost=cost_matrix[robot_idx, task_idx],
                ))
        
        return assignments
```

## 7.4 Collision Monitor

```python
# fleet/collision/monitor.py
"""
Detects robot-robot and robot-obstacle collisions.
Runs as a background task at 20Hz.
Publishes CollisionEvent to the event bus.
"""
import math
from dataclasses import dataclass
from robotics.models.robot_state import RobotState

ROBOT_RADIUS_M = 0.35          # Half-diagonal of 0.5m x 0.5m chassis
COLLISION_THRESHOLD_M = ROBOT_RADIUS_M * 2  # Two radii touching
NEAR_MISS_THRESHOLD_M = COLLISION_THRESHOLD_M + 0.3  # Safety margin

@dataclass
class CollisionEvent:
    robot_id: str
    other_id: str   # robot_id or obstacle_id
    distance: float
    is_collision: bool   # True = collision, False = near-miss
    pos_x: float
    pos_y: float
    timestamp: float

class CollisionMonitor:
    """
    Checks all robot pairs for collisions each tick.
    O(R^2) complexity — acceptable for R <= 20 robots.
    
    Does NOT modify robot state.
    Does NOT command robots to stop.
    Only publishes events — the FleetOrchestrator decides how to respond.
    """
    
    def __init__(self) -> None:
        self._previous_events: set[tuple[str, str]] = set()
    
    def check(self, robots: list[RobotState], timestamp: float) -> list[CollisionEvent]:
        events = []
        
        for i, r1 in enumerate(robots):
            for r2 in robots[i + 1:]:
                dist = _robot_distance(r1, r2)
                
                if dist <= COLLISION_THRESHOLD_M:
                    events.append(CollisionEvent(
                        robot_id=r1.id,
                        other_id=r2.id,
                        distance=dist,
                        is_collision=True,
                        pos_x=(r1.position.x + r2.position.x) / 2,
                        pos_y=(r1.position.y + r2.position.y) / 2,
                        timestamp=timestamp,
                    ))
                elif dist <= NEAR_MISS_THRESHOLD_M:
                    events.append(CollisionEvent(
                        robot_id=r1.id,
                        other_id=r2.id,
                        distance=dist,
                        is_collision=False,
                        pos_x=(r1.position.x + r2.position.x) / 2,
                        pos_y=(r1.position.y + r2.position.y) / 2,
                        timestamp=timestamp,
                    ))
        
        return events

def _robot_distance(r1: RobotState, r2: RobotState) -> float:
    return math.sqrt(
        (r1.position.x - r2.position.x) ** 2 +
        (r1.position.y - r2.position.y) ** 2
    )
```

## 7.5 Failure Detector

```python
# fleet/failure/detector.py
"""
Monitors robot health and emits FailureEvents.
Called at 5Hz by the FleetOrchestrator tick loop.
"""
import time
from dataclasses import dataclass
from enum import Enum
from robotics.models.robot_state import RobotState, NavState, CommState

class FailureType(str, Enum):
    LOW_BATTERY       = "low_battery"
    CRITICAL_BATTERY  = "critical_battery"
    STUCK             = "stuck"
    COMM_LOSS         = "comm_loss"
    NAV_FAILURE       = "nav_failure"
    SENSOR_DEGRADED   = "sensor_degraded"

@dataclass
class FailureEvent:
    robot_id: str
    failure_type: FailureType
    severity: float          # 0.0–1.0
    message: str
    timestamp: float

@dataclass
class RobotHealthHistory:
    """Sliding window of past states for detecting stuck robots."""
    positions: list[tuple[float, float]]
    timestamps: list[float]
    max_len: int = 20

    def add(self, x: float, y: float, t: float) -> None:
        self.positions.append((x, y))
        self.timestamps.append(t)
        if len(self.positions) > self.max_len:
            self.positions.pop(0)
            self.timestamps.pop(0)
    
    def total_distance_moved(self) -> float:
        if len(self.positions) < 2:
            return float("inf")
        total = 0.0
        for i in range(1, len(self.positions)):
            dx = self.positions[i][0] - self.positions[i-1][0]
            dy = self.positions[i][1] - self.positions[i-1][1]
            total += (dx**2 + dy**2) ** 0.5
        return total
    
    def window_duration_s(self) -> float:
        if len(self.timestamps) < 2:
            return 0.0
        return self.timestamps[-1] - self.timestamps[0]

class FailureDetector:
    """
    Stateful failure detector.
    Maintains per-robot history for stuck detection.
    All thresholds configurable.
    """
    
    LOW_BATTERY_THRESHOLD     = 0.20
    CRITICAL_BATTERY_THRESHOLD = 0.10
    STUCK_WINDOW_S            = 30.0
    STUCK_DISTANCE_THRESHOLD_M = 0.15
    COMM_LOSS_TIMEOUT_S       = 10.0
    
    def __init__(self) -> None:
        self._histories: dict[str, RobotHealthHistory] = {}
        self._last_seen: dict[str, float] = {}
    
    def check(self, state: RobotState, timestamp: float) -> list[FailureEvent]:
        events: list[FailureEvent] = []
        robot_id = state.id
        
        # Update history
        if robot_id not in self._histories:
            self._histories[robot_id] = RobotHealthHistory([], [])
        history = self._histories[robot_id]
        history.add(state.position.x, state.position.y, timestamp)
        self._last_seen[robot_id] = timestamp
        
        # Battery checks
        if state.battery_pct <= self.CRITICAL_BATTERY_THRESHOLD:
            events.append(FailureEvent(
                robot_id=robot_id,
                failure_type=FailureType.CRITICAL_BATTERY,
                severity=1.0,
                message=f"Battery at {state.battery_pct:.1%} — critical",
                timestamp=timestamp,
            ))
        elif state.battery_pct <= self.LOW_BATTERY_THRESHOLD:
            events.append(FailureEvent(
                robot_id=robot_id,
                failure_type=FailureType.LOW_BATTERY,
                severity=0.5,
                message=f"Battery at {state.battery_pct:.1%} — low",
                timestamp=timestamp,
            ))
        
        # Stuck detection
        if (state.nav_state == NavState.MOVING
                and history.window_duration_s() >= self.STUCK_WINDOW_S
                and history.total_distance_moved() < self.STUCK_DISTANCE_THRESHOLD_M):
            events.append(FailureEvent(
                robot_id=robot_id,
                failure_type=FailureType.STUCK,
                severity=0.8,
                message=f"Robot moved <{self.STUCK_DISTANCE_THRESHOLD_M}m in {self.STUCK_WINDOW_S}s while MOVING",
                timestamp=timestamp,
            ))
        
        # Communication loss
        if state.comm_state == CommState.OFFLINE:
            events.append(FailureEvent(
                robot_id=robot_id,
                failure_type=FailureType.COMM_LOSS,
                severity=0.9,
                message="Robot is OFFLINE — no communication",
                timestamp=timestamp,
            ))
        
        return events
```

## 7.6 Scenario Generator

```python
# simulation/scenarios/scenario_generator.py
"""
Procedural scenario generator.
Generates scenarios from a given seed.
"""
import random
import math
from dataclasses import dataclass, field

WORLD_WIDTH_M  = 40.0
WORLD_HEIGHT_M = 30.0
MIN_ROBOT_SEPARATION_M = 1.5
MIN_TASK_SEPARATION_M  = 1.0
SHELF_WIDTH_M  = 4.0
SHELF_DEPTH_M  = 1.0
SHELF_HEIGHT_M = 2.0

@dataclass
class ScenarioObstacle:
    id: str
    x: float
    y: float
    width: float
    depth: float
    height: float
    rotation: float = 0.0

@dataclass
class ScenarioRobot:
    id: str
    start_x: float
    start_y: float
    start_theta: float
    battery_pct: float

@dataclass
class ScenarioTask:
    id: str
    pickup_x: float
    pickup_y: float
    pickup_zone: str
    delivery_x: float
    delivery_y: float
    delivery_zone: str
    priority: int    # 1=LOW, 2=MEDIUM, 3=HIGH, 4=URGENT
    weight_kg: float

@dataclass
class Scenario:
    scenario_id: str
    seed: int
    world: str
    robots: list[ScenarioRobot]
    tasks: list[ScenarioTask]
    obstacles: list[ScenarioObstacle]
    time_limit_s: float
    failure_injection: bool

class ScenarioGenerator:
    """
    Generates reproducible scenarios from a seed.
    
    Rules:
    - All positions within world bounds with safety margin
    - No two robots start within MIN_ROBOT_SEPARATION_M of each other
    - No tasks placed inside obstacles
    - Obstacle count determined by scenario complexity tier
    """
    
    BATTERY_RANGE = (0.60, 1.00)
    WEIGHT_RANGE  = (0.5, 5.0)
    
    def generate(
        self,
        seed: int,
        robot_count: int = 5,
        task_count: int = 20,
        obstacle_count: int = 15,
        time_limit_s: float = 600.0,
        failure_injection: bool = False,
    ) -> Scenario:
        rng = random.Random(seed)
        
        obstacles = self._generate_obstacles(rng, obstacle_count)
        robots = self._generate_robots(rng, robot_count, obstacles)
        tasks = self._generate_tasks(rng, task_count, obstacles)
        
        return Scenario(
            scenario_id=f"warehouse_v1_r{robot_count}_t{task_count}",
            seed=seed,
            world="warehouse_v1",
            robots=robots,
            tasks=tasks,
            obstacles=obstacles,
            time_limit_s=time_limit_s,
            failure_injection=failure_injection,
        )
    
    def _generate_obstacles(self, rng: random.Random, count: int) -> list[ScenarioObstacle]:
        obstacles = []
        for i in range(count):
            for _ in range(100):  # max attempts
                x = rng.uniform(3, WORLD_WIDTH_M - 3)
                y = rng.uniform(3, WORLD_HEIGHT_M - 3)
                rotation = rng.choice([0.0, math.pi / 2])
                
                obs = ScenarioObstacle(
                    id=f"shelf_{i:02d}",
                    x=x, y=y,
                    width=SHELF_WIDTH_M if rotation == 0 else SHELF_DEPTH_M,
                    depth=SHELF_DEPTH_M if rotation == 0 else SHELF_WIDTH_M,
                    height=SHELF_HEIGHT_M,
                    rotation=rotation,
                )
                
                if not any(_obstacles_overlap(obs, existing) for existing in obstacles):
                    obstacles.append(obs)
                    break
        
        return obstacles
    
    def _generate_robots(
        self,
        rng: random.Random,
        count: int,
        obstacles: list[ScenarioObstacle],
    ) -> list[ScenarioRobot]:
        robots = []
        for i in range(count):
            for _ in range(200):
                x = rng.uniform(1.0, WORLD_WIDTH_M - 1.0)
                y = rng.uniform(1.0, WORLD_HEIGHT_M - 1.0)
                
                too_close = any(
                    math.dist((x, y), (r.start_x, r.start_y)) < MIN_ROBOT_SEPARATION_M
                    for r in robots
                )
                in_obstacle = any(_point_in_obstacle(x, y, obs) for obs in obstacles)
                
                if not too_close and not in_obstacle:
                    robots.append(ScenarioRobot(
                        id=f"robot_{i}",
                        start_x=x,
                        start_y=y,
                        start_theta=rng.uniform(-math.pi, math.pi),
                        battery_pct=rng.uniform(*self.BATTERY_RANGE),
                    ))
                    break
        
        return robots
    
    def _generate_tasks(
        self,
        rng: random.Random,
        count: int,
        obstacles: list[ScenarioObstacle],
    ) -> list[ScenarioTask]:
        tasks = []
        for i in range(count):
            pickup  = self._random_clear_point(rng, obstacles)
            delivery = self._random_clear_point(rng, obstacles)
            
            tasks.append(ScenarioTask(
                id=f"task_{i:03d}",
                pickup_x=pickup[0], pickup_y=pickup[1],
                pickup_zone=f"zone_p{i % 5}",
                delivery_x=delivery[0], delivery_y=delivery[1],
                delivery_zone=f"zone_d{i % 5}",
                priority=rng.choices([1, 2, 3, 4], weights=[40, 35, 20, 5])[0],
                weight_kg=rng.uniform(*self.WEIGHT_RANGE),
            ))
        
        return tasks
    
    def _random_clear_point(
        self,
        rng: random.Random,
        obstacles: list[ScenarioObstacle],
    ) -> tuple[float, float]:
        for _ in range(300):
            x = rng.uniform(1.5, WORLD_WIDTH_M - 1.5)
            y = rng.uniform(1.5, WORLD_HEIGHT_M - 1.5)
            if not any(_point_in_obstacle(x, y, obs) for obs in obstacles):
                return (x, y)
        # Fallback: return a known-clear corner area
        return (1.5, 1.5)


def _point_in_obstacle(x: float, y: float, obs: ScenarioObstacle, margin: float = 0.5) -> bool:
    return (
        obs.x - obs.width / 2 - margin <= x <= obs.x + obs.width / 2 + margin
        and
        obs.y - obs.depth / 2 - margin <= y <= obs.y + obs.depth / 2 + margin
    )

def _obstacles_overlap(a: ScenarioObstacle, b: ScenarioObstacle, margin: float = 0.3) -> bool:
    return (
        abs(a.x - b.x) < (a.width + b.width) / 2 + margin
        and
        abs(a.y - b.y) < (a.depth + b.depth) / 2 + margin
    )
```

---

# SECTION 8 — ML PLATFORM EXTENDED

## 8.0 Training Environment

```python
# ml/env/fleet_env.py (extended)
"""
Multi-agent Gymnasium environment for MARL training.

Key design decisions:
1. Centralized training, decentralized execution (CTDE)
   - During training, agents can access global state for value function estimation
   - During deployment, each agent only receives its local observation
   - This is why we separate obs_space (local) from state_space (global)

2. Gymnasium-compatible but multi-agent
   - Uses dict action/observation spaces keyed by agent_id
   - Compatible with EPyMARL and most MARL frameworks

3. Reward structure: individual + shared
   - Individual: task completion, collision penalty
   - Shared: mission success bonus — all agents receive if mission completes on time
   - This discourages selfish behavior

4. Episode termination
   - All tasks complete → SUCCESS
   - Time limit reached → TIMEOUT
   - All robots failed → FAILURE
"""
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Any

class FleetEnv(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 10}
    
    # Observation space per agent (local only — no global state leaked)
    N_LIDAR_BINS      = 36   # 10° resolution, 360° scan
    N_NEARBY_ROBOTS   = 4    # 4 nearest robots tracked
    N_PENDING_TASKS   = 3    # 3 nearest pending tasks
    
    def __init__(self, config: "FleetEnvConfig") -> None:
        super().__init__()
        self.config = config
        self.n_agents = config.robot_count
        
        # Per-agent observation
        self.observation_space = spaces.Dict({
            # Self state
            "pos":            spaces.Box(-60, 60, (2,), np.float32),
            "vel":            spaces.Box(-2, 2, (2,), np.float32),
            "orientation":    spaces.Box(-np.pi, np.pi, (1,), np.float32),
            "battery":        spaces.Box(0, 1, (1,), np.float32),
            "has_task":       spaces.Discrete(2),
            "task_pickup":    spaces.Box(-60, 60, (2,), np.float32),
            "task_delivery":  spaces.Box(-60, 60, (2,), np.float32),
            "task_progress":  spaces.Box(0, 1, (1,), np.float32),  # 0=at pickup, 1=at delivery
            # Local sensing
            "lidar":          spaces.Box(0, 15, (self.N_LIDAR_BINS,), np.float32),
            # Nearby robots (relative positions)
            "nearby_robots":  spaces.Box(-60, 60, (self.N_NEARBY_ROBOTS, 2), np.float32),
            "nearby_battery": spaces.Box(0, 1, (self.N_NEARBY_ROBOTS,), np.float32),
            # Pending tasks (relative positions, 3 nearest)
            "pending_tasks":  spaces.Box(-60, 60, (self.N_PENDING_TASKS, 2), np.float32),
            # Global summary (not per-robot positions — just aggregate signals)
            "fleet_utilization":    spaces.Box(0, 1, (1,), np.float32),
            "tasks_remaining_frac": spaces.Box(0, 1, (1,), np.float32),
            "time_remaining_frac":  spaces.Box(0, 1, (1,), np.float32),
        })
        
        # Continuous action: [linear_vel, angular_vel]
        self.action_space = spaces.Box(
            low=np.array([-0.5, -1.5], dtype=np.float32),
            high=np.array([1.0,  1.5], dtype=np.float32),
            dtype=np.float32,
        )
        
        self._sim = None  # Lazy init: connects to Gazebo on first reset()
        self._episode_steps = 0
        self._max_steps = int(config.time_limit_s * config.sim_frequency_hz)
    
    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[dict[str, Any], dict]:
        super().reset(seed=seed)
        
        scenario_seed = seed or self.config.seed
        # Reset Gazebo environment to new scenario
        obs_dict = self._reset_simulation(scenario_seed)
        self._episode_steps = 0
        
        return obs_dict, {}
    
    def step(self, actions: dict[str, np.ndarray]) -> tuple:
        """
        actions: dict mapping agent_id → np.ndarray([linear_vel, angular_vel])
        
        Returns: (observations, rewards, terminateds, truncateds, infos)
        All values are dicts keyed by agent_id, plus a special "__all__" key.
        """
        # Send actions to robots via ROS 2
        self._send_actions(actions)
        
        # Step simulation by one control tick
        self._sim.step()
        self._episode_steps += 1
        
        # Collect new state
        fleet_state = self._get_fleet_state()
        
        # Build per-agent observations, rewards, dones
        obs_dict = {agent_id: self._build_obs(agent_id, fleet_state) 
                    for agent_id in actions}
        
        reward_dict = self._compute_rewards(fleet_state)
        
        terminated = {agent_id: fleet_state.robots[agent_id].nav_state.value == "failed"
                      for agent_id in actions}
        terminated["__all__"] = fleet_state.mission_complete or all(terminated.values())
        
        truncated = {agent_id: self._episode_steps >= self._max_steps
                     for agent_id in actions}
        truncated["__all__"] = self._episode_steps >= self._max_steps
        
        info = {
            "__all__": {
                "tasks_completed": fleet_state.tasks_completed,
                "tasks_total": fleet_state.tasks_total,
                "collision_count": fleet_state.collision_count,
                "episode_steps": self._episode_steps,
            }
        }
        
        return obs_dict, reward_dict, terminated, truncated, info
    
    def _compute_rewards(self, fleet_state) -> dict[str, float]:
        """
        Reward decomposition:
        
        Individual rewards (per agent):
          +10.0  task pickup completed
          +15.0  task delivery completed
          +0.1 × progress_to_goal  (dense shaping)
          -5.0   collision
          -3.0   near-miss
          -0.05 × stuck_seconds (deadlock penalty)
          -0.001 × energy_consumed (efficiency incentive)
        
        Shared reward (all agents):
          +20.0 × time_efficiency  mission_complete bonus
          (distributed equally to all active agents)
        """
        rewards = {}
        
        for agent_id, robot_state in fleet_state.robots.items():
            r = 0.0
            events = fleet_state.events_since_last_step.get(agent_id, [])
            
            for event in events:
                if event["type"] == "PICKUP_COMPLETE":
                    r += 10.0
                elif event["type"] == "DELIVERY_COMPLETE":
                    r += 15.0
                elif event["type"] == "COLLISION":
                    r -= 5.0
                elif event["type"] == "NEAR_MISS":
                    r -= 3.0
                elif event["type"] == "STUCK":
                    r -= 0.05 * event.get("stuck_seconds", 1.0)
            
            # Dense shaping: progress toward current goal
            if robot_state.current_task:
                r += 0.1 * self._task_progress_delta(robot_state)
            
            # Energy penalty
            r -= 0.001 * fleet_state.energy_consumed_since_last_step.get(agent_id, 0.0)
            
            rewards[agent_id] = r
        
        # Shared mission complete bonus
        if fleet_state.mission_complete:
            time_efficiency = max(0.0, 1.0 - fleet_state.elapsed_fraction)
            shared_bonus = 20.0 * time_efficiency
            for agent_id in rewards:
                rewards[agent_id] += shared_bonus
        
        return rewards
```

## 8.1 MAPPO Agent

```python
# ml/policies/mappo/agent.py
"""
Multi-Agent Proximal Policy Optimization (MAPPO).
Uses centralized value function during training (has access to global state).
Uses decentralized policy during execution (local observations only).

Architecture:
  Actor:  local_obs → MLP(256, 256) → Tanh → action_mean, log_std
  Critic: global_state → MLP(256, 256) → Tanh → value

Both networks use layer normalization and orthogonal initialization.
"""
import torch
import torch.nn as nn
import numpy as np
from typing import Optional

class MLPNetwork(nn.Module):
    """Shared MLP backbone used by both actor and critic."""
    
    def __init__(
        self,
        input_dim: int,
        hidden_sizes: list[int],
        output_dim: int,
        use_layer_norm: bool = True,
    ) -> None:
        super().__init__()
        
        layers = []
        in_size = input_dim
        for hidden_size in hidden_sizes:
            layers.append(nn.Linear(in_size, hidden_size))
            if use_layer_norm:
                layers.append(nn.LayerNorm(hidden_size))
            layers.append(nn.Tanh())
            in_size = hidden_size
        
        layers.append(nn.Linear(in_size, output_dim))
        self.net = nn.Sequential(*layers)
        
        # Orthogonal initialization
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, gain=np.sqrt(2))
                nn.init.constant_(module.bias, 0)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class MAPPOActor(nn.Module):
    """
    Decentralized actor: maps local observation to action distribution.
    Used both during training and deployment.
    """
    
    def __init__(self, obs_dim: int, action_dim: int, hidden_sizes: list[int] = [256, 256]) -> None:
        super().__init__()
        self.backbone = MLPNetwork(obs_dim, hidden_sizes, hidden_sizes[-1])
        self.action_mean = nn.Linear(hidden_sizes[-1], action_dim)
        self.log_std = nn.Parameter(torch.zeros(action_dim))
        
        nn.init.orthogonal_(self.action_mean.weight, gain=0.01)
        nn.init.constant_(self.action_mean.bias, 0)
    
    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.backbone(obs)
        mean = self.action_mean(features)
        std = torch.exp(self.log_std.clamp(-4, 15))
        return mean, std
    
    def get_action(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        mean, std = self.forward(obs)
        dist = torch.distributions.Normal(mean, std)
        action = dist.sample()
        log_prob = dist.log_prob(action).sum(-1)
        return action.tanh(), log_prob


class MAPPOCritic(nn.Module):
    """
    Centralized critic: maps global state to value estimate.
    Only used during training — NOT deployed on robots.
    """
    
    def __init__(self, state_dim: int, hidden_sizes: list[int] = [256, 256]) -> None:
        super().__init__()
        self.net = MLPNetwork(state_dim, hidden_sizes, 1)
        
        nn.init.orthogonal_(self.net.net[-1].weight, gain=1.0)
    
    def forward(self, state: torch.Tensor) -> torch.Tensor:
        return self.net(state).squeeze(-1)


class MAPPOAgent:
    """
    Container for MAPPO actor + critic with training utilities.
    """
    
    def __init__(
        self,
        obs_dim: int,
        state_dim: int,
        action_dim: int,
        lr: float = 3e-4,
        device: str = "cpu",
    ) -> None:
        self.device = torch.device(device)
        self.actor  = MAPPOActor(obs_dim, action_dim).to(self.device)
        self.critic = MAPPOCritic(state_dim).to(self.device)
        
        self.actor_optimizer  = torch.optim.Adam(self.actor.parameters(),  lr=lr, eps=1e-5)
        self.critic_optimizer = torch.optim.Adam(self.critic.parameters(), lr=lr, eps=1e-5)
    
    @torch.no_grad()
    def act(self, obs: np.ndarray) -> np.ndarray:
        """Inference-time action. Uses local obs only. No critic."""
        obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self.device)
        action, _ = self.actor.get_action(obs_t)
        return action.squeeze(0).cpu().numpy()
    
    def save(self, path: str) -> None:
        torch.save({
            "actor_state_dict":  self.actor.state_dict(),
            "critic_state_dict": self.critic.state_dict(),
            "actor_optimizer":   self.actor_optimizer.state_dict(),
            "critic_optimizer":  self.critic_optimizer.state_dict(),
        }, path)
    
    def load(self, path: str) -> None:
        checkpoint = torch.load(path, map_location=self.device)
        self.actor.load_state_dict(checkpoint["actor_state_dict"])
        self.critic.load_state_dict(checkpoint["critic_state_dict"])
        self.actor_optimizer.load_state_dict(checkpoint["actor_optimizer"])
        self.critic_optimizer.load_state_dict(checkpoint["critic_optimizer"])
```

## 8.2 Experiment Runner

```python
# experiments/scripts/run_experiment.py
"""
Runs benchmark experiments and produces the comparison table.
This script is the source of truth for all benchmark results.
It enforces the integrity rules from TESTING_PLAN.md Section 7.

CRITICAL: Never edit results files manually.
All results must come from running this script.
"""
import argparse
import json
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass, asdict
import yaml

RESULTS_DIR = Path("experiments/results")
CONFIGS_DIR = Path("experiments/configs")

@dataclass
class ExperimentResult:
    experiment_id: str
    policy: str
    scenario_id: str
    seed_range: list[int]
    n_runs: int
    
    # Must be populated from actual execution only
    mean_success_rate: float | None = None
    std_success_rate: float | None = None
    mean_completion_time_s: float | None = None
    std_completion_time_s: float | None = None
    mean_collision_count: float | None = None
    std_collision_count: float | None = None
    mean_energy_consumed: float | None = None
    mean_popw_score: float | None = None
    std_popw_score: float | None = None
    
    # Integrity fields — must always be present
    status: str = "NOT_RUN"    # NOT_RUN | COMPLETE | UNSTABLE | FAILED
    git_commit: str = ""
    execution_log_path: str = ""
    ran_at: str = ""


def run_experiment(config_path: Path) -> ExperimentResult:
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    exp_id = config["experiment"]["id"]
    result = ExperimentResult(
        experiment_id=exp_id,
        policy=config["experiment"]["policy"],
        scenario_id=config["scenario"]["world"],
        seed_range=config["scenario"]["seed_range"],
        n_runs=config["scenario"]["seed_range"][1] - config["scenario"]["seed_range"][0] + 1,
        git_commit=_get_git_commit(),
        ran_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    
    raw_results = []
    log_path = RESULTS_DIR / exp_id / "execution.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    for seed in range(*config["scenario"]["seed_range"]):
        run_result = _execute_single_run(
            policy=config["experiment"]["policy"],
            scenario=config["scenario"],
            seed=seed,
        )
        raw_results.append(run_result)
        
        # Append to log immediately (not at end — partial results are preserved)
        with open(log_path, "a") as f:
            f.write(json.dumps({"seed": seed, **run_result}) + "\n")
    
    # Compute aggregate statistics from actual run data
    import statistics
    success_rates = [r["success_rate"] for r in raw_results]
    times = [r["completion_time_s"] for r in raw_results]
    collisions = [r["collision_count"] for r in raw_results]
    scores = [r["popw_score"] for r in raw_results]
    
    result.mean_success_rate = statistics.mean(success_rates)
    result.std_success_rate  = statistics.stdev(success_rates) if len(success_rates) > 1 else 0.0
    result.mean_completion_time_s = statistics.mean(times)
    result.std_completion_time_s  = statistics.stdev(times) if len(times) > 1 else 0.0
    result.mean_collision_count = statistics.mean(collisions)
    result.mean_popw_score = statistics.mean(scores)
    result.std_popw_score  = statistics.stdev(scores) if len(scores) > 1 else 0.0
    result.execution_log_path = str(log_path)
    
    # Mark as UNSTABLE if std dev > 15% of mean
    if result.std_popw_score > 0.15 * (result.mean_popw_score or 1):
        result.status = "UNSTABLE"
    else:
        result.status = "COMPLETE"
    
    # Save result
    result_path = RESULTS_DIR / exp_id / "result.json"
    with open(result_path, "w") as f:
        json.dump(asdict(result), f, indent=2)
    
    return result


def generate_benchmark_table(results: list[ExperimentResult]) -> str:
    """Generates the benchmark comparison table for README and KONNEX_APPLICATION.md."""
    
    header = (
        f"{'Policy':<25} {'Success':<12} {'Time(s)':<12} {'Collisions':<12} "
        f"{'PoPW Score':<12} {'Status':<10}\n"
        + "-" * 85
    )
    rows = [header]
    
    for r in results:
        if r.status == "NOT_RUN":
            row = f"{r.policy:<25} {'NOT RUN':<12} {'NOT RUN':<12} {'NOT RUN':<12} {'NOT RUN':<12} {r.status:<10}"
        elif r.status == "FAILED":
            row = f"{r.policy:<25} {'FAILED':<12} {'FAILED':<12} {'FAILED':<12} {'FAILED':<12} {r.status:<10}"
        else:
            success = f"{r.mean_success_rate:.1%}±{r.std_success_rate:.1%}" if r.mean_success_rate else "—"
            time_s  = f"{r.mean_completion_time_s:.1f}±{r.std_completion_time_s:.1f}" if r.mean_completion_time_s else "—"
            coll    = f"{r.mean_collision_count:.1f}" if r.mean_collision_count is not None else "—"
            score   = f"{r.mean_popw_score:.1f}±{r.std_popw_score:.1f}" if r.mean_popw_score else "—"
            row = f"{r.policy:<25} {success:<12} {time_s:<12} {coll:<12} {score:<12} {r.status:<10}"
        
        rows.append(row)
    
    return "\n".join(rows)


def _get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "UNKNOWN"
```

## 8.3 Experiment Config Schema

```yaml
# experiments/configs/exp_001_nearest.yaml
experiment:
  id: "exp_001"
  name: "Nearest Task Assignment Baseline"
  policy: "nearest"
  
scenario:
  world: "warehouse_v1"
  robot_count: 5
  task_count: 20
  seed_range: [1000, 1009]   # 10 seeds for statistical significance
  obstacle_count: 15
  battery_range: [0.6, 1.0]
  failure_injection: false
  
execution:
  time_limit_s: 600
  runs_per_seed: 1
  
output:
  results_dir: "experiments/results/exp_001"
  save_trajectories: true
  save_telemetry: true
```

## 8.4 Benchmark Report Format

```
========================================
KONNEX FLEET BENCHMARK — 2024-xx-xx
Scenario: Warehouse V1 | 5 Robots | 20 Tasks
Seeds: 1000–1009 (10 runs each)
========================================

Policy               Success    Time(s)   Energy   Collisions   Status
------------------------------------------------------------------------
Nearest Assignment   82.3±4.1%  8.21±1.2  100%     14.2±3.1    COMPLETE
Hungarian            88.7±3.2%  7.42±0.9   91%      8.1±2.0    COMPLETE
Cost Optimizer       92.4±2.8%  6.91±0.8   84%      4.3±1.5    COMPLETE
MAPPO                NOT RUN    NOT RUN    NOT RUN  NOT RUN      NOT RUN
========================================
```

## 8.5 MAPPO Training Config

```yaml
# ml/policies/mappo/config.yaml
algorithm: "MAPPO"
n_agents: 5
learning_rate: 3.0e-4
n_steps: 2048         # steps per update per agent
batch_size: 256
n_epochs: 10
gamma: 0.99
gae_lambda: 0.95
clip_range: 0.2
ent_coef: 0.01
vf_coef: 0.5
max_grad_norm: 0.5
target_kl: 0.015
total_timesteps: 5_000_000
eval_freq: 50_000
n_eval_episodes: 10
seed: 42
```

### Observation Design Rationale

| Observation | Why included | Why limited |
|---|---|---|
| `robot_pos` | Robot needs to know where it is | Global frame; known from odometry |
| `task_rel_pos` | Navigate to task | Relative, not absolute (generalizes better) |
| `nearby_robots` | Collision avoidance | 4 nearest only — full fleet state is too large |
| `lidar_scan` | Obstacle detection | 36 bins (10° resolution) = compact but sufficient |
| `has_task` | Task awareness | Binary flag |
| `fleet_utilization` | Global context signal | Scalar summary, not per-robot global state |

**Not included:** absolute positions of all other robots, full map, task queue, battery of other robots. These would leak global state that won't be available in decentralized deployment.

---

## 8.6 ValidatorRunner

```python
# validator/runner.py
@dataclass
class ValidationRequest:
    policy_id: str
    policy_hash: str              # SHA-256
    scenario_id: str
    seed: int
    env_version: str
    sim_version: str
    resource_limits: ResourceLimits

@dataclass 
class ValidationResult:
    request: ValidationRequest
    status: Literal["COMPLETE", "POLICY_CRASH", "TIMEOUT", "RESOURCE_EXCEEDED", "INVALID_ACTIONS", "UNSTABLE"]
    trajectory: list[RobotTrajectoryFrame] | None
    task_outcomes: list[TaskOutcome]
    energy_log: list[EnergyEntry]
    collision_log: list[CollisionEvent]
    completion_time_s: float
    score: PoPWScore
    evaluation_artifact: EvaluationArtifact
    
class ValidatorRunner:
    async def validate(self, request: ValidationRequest) -> ValidationResult: ...
```

## 8.7 EvaluationArtifact

```python
# validator/reproducibility/artifact.py
import hashlib
import json
from dataclasses import dataclass

@dataclass
class EvaluationArtifact:
    """
    Serializable proof of a completed evaluation.
    Can be independently verified by any validator.
    """
    policy_id: str
    policy_hash: str
    scenario_id: str
    seed: int
    env_version: str
    sim_version: str
    score_components: dict[str, float]
    final_score: float
    completion_time_s: float
    collision_count: int
    tasks_completed: int
    tasks_total: int
    energy_consumed: float
    timestamp: float
    artifact_hash: str = ""  # computed on creation
    
    def compute_hash(self) -> str:
        """SHA-256 of canonical JSON (keys sorted, floats rounded to 6dp)."""
        payload = {k: v for k, v in self.__dict__.items() if k != "artifact_hash"}
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
```

## 8.8 PoPW Scoring Engine

```python
# validator/scoring/engine.py
@dataclass
class ScoringWeights:
    mission_success: float = 0.40
    safety: float = 0.20
    efficiency: float = 0.15
    energy: float = 0.10
    coordination: float = 0.10
    robustness: float = 0.05

@dataclass
class PoPWScore:
    mission_success: float   # 0.0–1.0
    safety: float            # 0.0–1.0
    efficiency: float        # 0.0–1.0
    energy: float            # 0.0–1.0
    coordination: float      # 0.0–1.0
    robustness: float        # 0.0–1.0
    final: float             # 0.0–100.0 weighted sum
    weights: ScoringWeights

class PoPWScoringEngine:
    """
    Prototype PoPW-inspired evaluation mechanism.
    NOT Konnex's official scoring algorithm.
    Designed to be adaptable to actual Konnex SDK scoring rules.
    """
    
    def __init__(self, weights: ScoringWeights | None = None) -> None: ...
    
    def score(self, result: MissionResult) -> PoPWScore:
        mission_success = result.tasks_completed / result.tasks_total
        safety = 1.0 - min(1.0, result.collision_count / 10)
        efficiency = max(0.0, 1.0 - (result.elapsed_s / result.time_limit_s))
        energy = 1.0 - (result.energy_consumed / result.energy_budget)
        coordination = self._coordination_score(result)
        robustness = self._robustness_score(result)
        
        w = self.weights
        final = 100.0 * (
            w.mission_success * mission_success +
            w.safety * safety +
            w.efficiency * efficiency +
            w.energy * energy +
            w.coordination * coordination +
            w.robustness * robustness
        )
        
        return PoPWScore(
            mission_success=mission_success,
            safety=safety,
            efficiency=efficiency,
            energy=energy,
            coordination=coordination,
            robustness=robustness,
            final=round(final, 2),
            weights=w,
        )
```

---

# SECTION 9 — DEPLOYMENT & MAKEFILE

## 9.1 Makefile (Complete)

```makefile
# Makefile — Konnex Fleet Intelligence Subnet
# All primary workflows are accessible via make targets.
# Never run deployment commands manually — always use make.

.PHONY: setup demo benchmark test lint clean check-env docs

# ─── Environment ──────────────────────────────────────────────────────────────

check-env:
	@echo "=== Checking development environment ==="
	@bash scripts/check_environment.sh

setup: check-env
	@echo "=== Setting up Fleet Subnet ==="
	@pip install -r requirements.txt
	@pip install -r requirements-dev.txt
	@cd frontend && npm ci
	@cp .env.example .env
	@docker-compose pull
	@echo "Setup complete. Run: make demo"

# ─── Demo ─────────────────────────────────────────────────────────────────────

demo:
	@echo "=== Starting Konnex Fleet Demo ==="
	@echo "This will launch: Gazebo + Backend + Frontend + Validator"
	@echo "Dashboard: http://localhost:3000"
	@echo "API docs:  http://localhost:8000/docs"
	@docker-compose up --build --abort-on-container-exit fleet-demo

demo-bg:
	@docker-compose up -d
	@echo "Services started in background."
	@echo "Dashboard: http://localhost:3000"
	@echo "Run 'make logs' to watch output. 'make stop' to stop."

stop:
	@docker-compose down

logs:
	@docker-compose logs -f

# ─── Benchmarking ─────────────────────────────────────────────────────────────

benchmark:
	@echo "=== Running Fleet Benchmark Suite ==="
	@echo "WARNING: This runs real experiments. Results take 30–60 minutes."
	@echo "All results saved to experiments/results/"
	@python experiments/scripts/run_experiment.py \
		--configs experiments/configs/ \
		--all \
		--report

benchmark-single:
	@python experiments/scripts/run_experiment.py \
		--config experiments/configs/$(EXP).yaml \
		--report

# ─── Testing ──────────────────────────────────────────────────────────────────

test:
	@pytest tests/unit tests/integration \
		-v \
		--tb=short \
		--strict-markers \
		--cov=. \
		--cov-report=term-missing

test-unit:
	@pytest tests/unit -v --tb=short

test-integration:
	@pytest tests/integration -v --tb=short

test-sim:
	@pytest tests/simulation -v --tb=short -m simulation

test-e2e:
	@pytest tests/e2e -v --tb=short -m e2e

test-frontend:
	@cd frontend && npm run test:unit

# ─── Linting ──────────────────────────────────────────────────────────────────

lint:
	@echo "=== Python lint ==="
	@ruff check .
	@ruff format --check .
	@mypy . --ignore-missing-imports
	@echo "=== TypeScript lint ==="
	@cd frontend && npm run lint && npm run type-check
	@echo "All lint checks passed."

lint-fix:
	@ruff check . --fix
	@ruff format .
	@cd frontend && npm run lint:fix

# ─── ML Training ──────────────────────────────────────────────────────────────

train-mappo:
	@python ml/training/train.py \
		--config ml/policies/mappo/config.yaml \
		--seed 42 \
		--total-timesteps 5000000

train-mappo-quick:
	@python ml/training/train.py \
		--config ml/policies/mappo/config.yaml \
		--seed 42 \
		--total-timesteps 100000 \
		--note "quick-test"

# ─── Database ─────────────────────────────────────────────────────────────────

db-migrate:
	@alembic upgrade head

db-reset:
	@alembic downgrade base
	@alembic upgrade head

db-seed:
	@python backend/db/seed.py

# ─── Documentation ────────────────────────────────────────────────────────────

docs:
	@echo "Documentation index:"
	@ls -la docs/

# ─── Cleanup ──────────────────────────────────────────────────────────────────

clean:
	@docker-compose down -v
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete
	@cd frontend && rm -rf dist node_modules 2>/dev/null || true
	@echo "Clean complete."

clean-results:
	@echo "WARNING: This deletes all benchmark results."
	@read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || exit 1
	@find experiments/results -name "*.json" -delete
	@find experiments/results -name "*.jsonl" -delete
	@echo "Results cleared."

# ─── Konnex Integration ───────────────────────────────────────────────────────

konnex-check:
	@echo "=== Checking Konnex Adapter Status ==="
	@python -c "from protocol.konnex.adapter import KonnexAdapter; print('Adapter loaded. Status: STUB — SDK not yet verified.')"

konnex-docs:
	@echo "Visit Konnex docs to verify SDK before implementing adapter:"
	@echo "https://docs.konnex.network (verify this URL)"
	@echo "https://gitbook.konnex.network (verify this URL)"

# ─── Help ─────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Konnex Fleet Intelligence Subnet — Make Targets"
	@echo "================================================"
	@echo ""
	@echo "  make setup          Install all dependencies"
	@echo "  make demo           Launch full demo stack"
	@echo "  make benchmark      Run complete benchmark suite"
	@echo "  make test           Run unit + integration tests"
	@echo "  make lint           Run all linters"
	@echo "  make train-mappo    Train MAPPO policy"
	@echo "  make clean          Clean build artifacts"
	@echo "  make konnex-check   Check Konnex adapter status"
	@echo ""
```

## 9.2 Environment Variables Reference

```bash
# .env.example
# Copy to .env and fill in values
# NEVER commit .env to version control

# API
FLEET_API_KEY=dev-only-key   # CHANGE IN PRODUCTION

# Database
POSTGRES_PASSWORD=fleet_dev_password
DATABASE_URL=postgresql://fleet:${POSTGRES_PASSWORD}@localhost:5432/fleet

# Redis
REDIS_URL=redis://localhost:6379/0

# Storage
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin_secret
MINIO_BUCKET=fleet-artifacts

# ML
MLFLOW_TRACKING_URI=http://localhost:5000

# Monitoring
GRAFANA_PASSWORD=admin_change_me

# ROS 2
ROS_DOMAIN_ID=42

# Konnex (STUB — do not fill until SDK is verified)
KONNEX_NETWORK_URL=
KONNEX_API_KEY=

# Frontend
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/fleet
```

---

# SECTION 10 — KONNEX APPLICATION TEMPLATE

## 10.0 KONNEX_APPLICATION.md Template

> Write this file LAST — after all benchmarks are complete.  
> Every number in this file must match `experiments/results/`.  
> Leave placeholders for metrics that have not been measured.

```markdown
# KONNEX_APPLICATION.md
## Konnex Fleet Intelligence Subnet — Builder Program Application

**Team:** [Team Name]  
**Project:** konnex-fleet-subnet  
**GitHub:** [repo URL]  
**Demo video:** [YouTube/Loom URL]  
**Grant tier requested:** Spark ($25K) / Launch ($75K) / Mainnet ($200K+)

---

### One-Line Pitch

< 140 characters — fill after completing demo >

"Decentralized incentive layer for competing AI policies to coordinate autonomous 
robot fleets and earn rewards for verified physical work."

---

### Problem

Current robot fleet coordination systems are:
- **Centralized**: One company, one policy, no competitive improvement mechanism
- **Opaque**: No objective, reproducible standard for "how well did this fleet perform?"
- **Uneconomic**: No market incentive to contribute better coordination algorithms to a shared commons

### Solution

A Konnex subnet that:
1. Accepts policy submissions from any developer
2. Evaluates them in standardized warehouse missions via reproducible validators
3. Scores physical-work outcomes via a PoPW-aligned evaluation engine
4. Rewards best-performing policies with KNX tokens

### Why Konnex

Our subnet maps directly to Konnex's PoPW model:

| Konnex Concept | Our Implementation |
|---|---|
| Miners | Policy developers submitting fleet coordination algorithms |
| Validators | Reproducible evaluation harness running in Gazebo |
| Physical Work | Warehouse delivery missions (packages moved, distance, energy) |
| PoPW Score | Weighted evaluation: success rate + safety + efficiency + energy |
| Rewards | KNX tokens to policy authors with highest verified scores |

### Current Prototype

**Status:** [COMPLETE / IN PROGRESS — fill truthfully]

Working components:
- [ ] 5 autonomous robots in Gazebo warehouse simulation
- [ ] 3 classical baseline policies (nearest, hungarian, cost_optimizer)
- [ ] Reproducible validator with evaluation artifacts
- [ ] PoPW-inspired scoring engine
- [ ] Fleet monitoring dashboard (React + Three.js)
- [ ] `make demo` single-command launch
- [ ] `make benchmark` automated comparison

### Benchmark Results

> All numbers from actual experiment runs. See experiments/results/ for raw data.

[INSERT TABLE FROM make benchmark OUTPUT HERE]

Status: [NOT RUN — fill after experiments complete]

### Architecture

[5-layer diagram from BUILD.md Section 3.1]

### Team

[Honest description of relevant backgrounds]

### Roadmap

```
Prototype (now)
  → Spark grant → 5-robot simulation + MARL + validator
  → Launch grant → Testnet deployment + physical robot pilot
  → Mainnet → Open policy marketplace + KNX reward distribution
```

### Grant Request

Spark ($25K): Complete MARL training + physical robot pilot prototype  
Launch ($75K): Testnet deployment + validator network + co-marketing  
Mainnet ($200K+): Open subnet with policy marketplace + KNX rewards
```

---

*This AGENTS.md is a binding technical contract. All agents operating on this repository agree to these rules by operating on this repository. Modifications require a documented commit message explaining the change and which section was affected.*

*Version: 1.0.0 | Project: konnex-fleet-subnet | Konnex Builder Program*
