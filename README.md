# Konnex Fleet Intelligence Subnet

Decentralized incentive and evaluation infrastructure for coordinating autonomous robot fleets on physical-world warehouse missions, built for the **Konnex Builder Program** (PoPW model).

Policy developers (miners) submit fleet-coordination algorithms; validators execute them in a reproducible simulation, score the physical-work outcomes with a PoPW-aligned engine, and the best policies earn KNX rewards.

---

## Quickstart

```bash
make setup          # environment check + dependency installation
make demo           # boot backend + dashboard + predefined mission (5 robots / 20 tasks / seed 42)
make benchmark      # run the benchmark suite (exp_001–003, real orchestrator runs)
make payment-demo   # FleetPay Agent demo: AI decisions → policy → USDC → Arc (mock)
make test           # unit + integration tests
make lint           # ruff + mypy + bandit + eslint + tsc
make sim            # Phase 1: boot the containerized Gazebo Harmonic sim (needs Docker)
pytest tests/e2e/ -m e2e   # Phase 10 e2e gate (boots the real backend stack, ~3 min)
pytest tests/simulation/ -m simulation  # Phase 1 sim tests (Gazebo-gated tests self-skip)
```

## What Works

| Component | Status |
|---|---|
| Headless warehouse simulation | ✅ 5 robots, 20 tasks, deterministic from seed |
| 3 classical policies | ✅ nearest, hungarian, cost_optimizer |
| FleetOrchestrator | ✅ Task allocation, collision detection, failure recovery |
| PoPW scoring engine | ✅ 6-component weighted score (0–100), configurable weights |
| Evaluation artifacts | ✅ SHA-256 hashed, reproducible, tamper-evident |
| Fleet dashboard | ✅ React 18 + Three.js + WebSocket (live robot positions) |
| Backend API | ✅ FastAPI + SQLite + WebSocket bridge |
| ML platform | ✅ FleetEnv (Gymnasium) + PPO trainer + BC/DAgger pretraining + rollout evaluator; trained MAPPO checkpoint at 100% success / 92.9 PoPW |
| Konnex adapter | ✅ Boundary interface (SDK stub — researched, not integrated) |
| Test suite | 🟡 `make test` is the source of truth; stale counts removed |
| Gazebo simulation | ✅ Phase 1 wiring (Docker image, launch files, gz↔ROS bridge, fleet_agent, GazeboRobotAdapter) — live run NOT RUN here |
| Agentic payments | ✅ FleetPay Agent — agent decisions → policy-gated USDC → Arc settlement (mock, MOCK-labeled by default; real Circle/Arc provider implemented, credentials required) + live fleet-telemetry payments (docs/payments.md) |

## Benchmark Results

> All numbers from actual experiment runs. See `experiments/results/` for raw data.

| Policy | Success Rate | Time (s) | Collisions | PoPW Score | Status |
|---|---|---|---|---|---|
| Hungarian | 99.8% ± 0.9% | 144.20 ± 87.36 | 1.1 ± 0.8 | 90.7 ± 3.8 | COMPLETE |
| Cost Optimizer | 99.7% ± 1.3% | 184.78 ± 115.16 | 2.2 ± 1.5 | 86.4 ± 4.7 | COMPLETE |
| Nearest Assignment | 99.5% ± 1.5% | 202.87 ± 136.75 | 2.2 ± 1.6 | 85.8 ± 6.0 | COMPLETE |
| MAPPO actor (BC + DAgger) | 100.0% ± 0.0% | 135.63 ± 14.20 | 1.1 | 92.9 ± 2.1 | COMPLETE |

**Scenario:** warehouse_v1 | 5 robots | 20 tasks | 30 seeds (1000–1029) | 600s time limit

The classical rows use the latest `exp_001`–`exp_003` run (`run_id`
`...20261101T1951*`), which counts one collision per new contact. Earlier logs
counted a sustained contact on every tick, producing hundreds of collisions and
lower scores; those numbers are superseded.

**MAPPO is evaluated through FleetEnv rollouts, not the TaskAllocator
benchmark.** `exp_004`/`exp_005` were previously reported as MAPPO but were
actually silent nearest-task fallbacks (identical rows to `exp_001`). They are
now `SKIPPED` with an explicit reason. The trained MAPPO actor
(`ml/checkpoints/step_bc_v3.pt`) was bootstrapped with behavioral cloning plus
three DAgger rounds, then evaluated with
`experiments/scripts/evaluate_mappo.py` on the same 30 seeds. It completes all
30 missions (20/20 tasks each) and scores 92.9 ± 2.1 PoPW, above the best
classical baseline (Hungarian, 90.7 ± 3.8). Raw run:
`experiments/results/mappo_eval/result.json`. PPO fine-tuning was attempted
(30k, 20k, and 100k timesteps) and did not improve it; the post-mortem is in
`experiments/results/mappo_ppo_ft/`.

### Unified harness (all five policies in one simulator)

`make benchmark-unified` scores every policy inside **FleetEnv** — one
simulator, one waypoint controller, one PoPW engine, one seed set — so no
cross-harness caveat is needed. Classical allocators choose assignments through
FleetEnv's assignment-provider seam; MAPPO and the heuristic expert emit
waypoints directly.

| Policy | Success | Time (s) | Collisions | PoPW |
|---|---|---|---|---|
| MAPPO actor (BC + DAgger) | 100.0% ± 0.0% | 135.6 ± 14.2 | 1.1 ± 0.9 | **92.9 ± 2.1** |
| Expert (greedy task-seeker) | 100.0% ± 0.0% | 135.8 ± 14.7 | 1.2 ± 0.9 | 92.8 ± 2.2 |
| Hungarian | 100.0% ± 0.0% | 136.4 ± 16.9 | 1.4 ± 1.1 | 92.2 ± 2.7 |
| Nearest assignment | 100.0% ± 0.0% | 163.5 ± 22.2 | 1.6 ± 1.2 | 90.8 ± 3.3 |
| Cost optimizer | 100.0% ± 0.0% | 165.8 ± 18.7 | 1.8 ± 1.4 | 90.1 ± 3.6 |

**Scenario:** warehouse_v1 | 5 robots | 20 tasks | 30 seeds (1000–1029)
Raw run: `experiments/results/fleet_env_unified/result.json`

MAPPO's advantage is real but narrow: +0.1 PoPW over the heuristic expert and
+0.7 over Hungarian in the same harness, with overlapping standard deviations.
The honest claim is that the learned policy **matches** the strongest
hand-written controller, not that it dominates it.

**Fleet scaling** (`exp_006`, cost optimizer, 40 tasks, seeds 1000–1004):

| Robots | Success Rate | Time (s) | Collisions | PoPW Score |
|---|---|---|---|---|
| 5 | 99.5% ± 1.1% | 349.0 ± 141.0 | 3.6 ± 3.5 | 78.5 ± 9.0 |
| 10 | 99.5% ± 1.1% | 247.1 ± 197.9 | 8.4 ± 2.3 | 71.5 ± 6.3 |
| 20 | 95.0% ± 1.8% | 600.0 ± 0.0 (timeout) | 17.4 ± 5.5 | 56.0 ± 2.5 |

PoPW falls monotonically as the fleet grows: collision and coordination
penalties grow faster than throughput, and at 20 robots the fleet no longer
finishes 40 tasks inside the 600 s limit.

## Demo

> **TODO (Needs Joshua):** Demo video link — record per `DEMO_SCRIPT.md`, upload,
> and paste the URL here. Until then, run `make demo` locally; it boots the
> full stack in under 3 minutes.

`make demo` (`scripts/demo.sh`) boots the full stack with zero manual steps:
backend (headless simulator + REST + WebSocket on :8000), the React dashboard
on :3014, and the predefined demo mission (5 robots / 20 tasks / seed 42 /
nearest). No Docker or Gazebo required. The mission runs live and completes in
roughly 3–4 minutes; the dashboard streams robot positions (10 Hz), the live
PoPW score, the active policy, and the energy chart.

### Gazebo simulation (Phase 1)

The containerized Gazebo Harmonic sim (`make sim`, Docker required) runs the
same warehouse world and 5-robot fleet with real physics and LiDAR/IMU:
`simulation/Dockerfile.gazebo`, ROS 2 launch files, a gz↔ROS bridge, and the
per-robot `fleet_agent` controller. The backend can attach to it via
`SIM_MODE=gazebo` (ROSBridge + GazeboRobotAdapter) while keeping the same
RobotAdapter protocol — see docs/simulation.md.

**Verified (2026-11-02):** the sim tests now execute inside the container:
```bash
docker build -f simulation/Dockerfile.gazebo -t fleet-sim-test simulation/
docker run --rm -v "$PWD:/ws/repo" fleet-sim-test
# => 26 passed, 0 skipped
```
The gz↔ROS bridge publishes `/model/robot_N/odometry`, `/robot_N/scan` and
`/robot_N/cmd_vel` per robot. Host runs still self-skip (no `gz` on PATH).

```bash
make demo
#  Using Python: .venv/bin/python
#  Backend healthy: http://127.0.0.1:8000
#  Mission started: 5 robots / 20 tasks / seed 42 / policy=nearest
#  Dashboard: http://127.0.0.1:3014
```

Comparative policy results come from `make benchmark` (see table above) —
real orchestrator runs saved to `experiments/results/exp_00X/`.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ PRESENTATION: React 18 + Three.js + WebSocket           │
├─────────────────────────────────────────────────────────┤
│ API GATEWAY: FastAPI + Auth + OpenAPI + WS broadcaster   │
├────────────────────────┬────────────────────────────────┤
│ APPLICATION SERVICES   │ ASYNC WORKERS (ARQ + Redis)     │
├────────────────────────┴────────────────────────────────┤
│ DOMAIN CORE: FleetOrchestrator + TaskAllocator +        │
│   MissionManager + CollisionMonitor + FailureDetector    │
├────────────────────────┬────────────────────────────────┤
│ AGENTIC PAYMENTS       │ ML PLATFORM / VALIDATION        │
│  FleetPay Agent        │   FleetEnv + MAPPO + PoPW      │
│  Policy → Circle → Arc │   Scoring + Artifacts           │
├────────────────────────┴────────────────────────────────┤
│ ROBOTICS: ROS 2 + Nav2 + AMCL + Hardware Abstraction    │
├────────────────────────┬────────────────────────────────┤
│ SIMULATION             │ PROTOCOL / WEB3                 │
│   Gazebo Harmonic      │   PoPW + Konnex + FleetPayment  │
├────────────────────────┴────────────────────────────────┤
│ INFRASTRUCTURE: PostgreSQL + Redis + MinIO + Docker      │
└─────────────────────────────────────────────────────────┘
```

## Repository Guide

| File | Purpose |
|---|---|
| `AGENTS.md` | Binding operational contract for all AI coding agents |
| `PLAN.md` | Product requirements & design |
| `BUILD.md` | Technical implementation specification |
| `SYSTEM_PROMPT.md` | Coding standards, error handling, prohibited patterns |
| `TESTING_PLAN.md` | Test strategy, phase gates, CI/CD |
| `KONNEX_APPLICATION.md` | Builder Program application — real data only |
| `docs/` | Architecture, requirements, MVP, development plan |
| `Makefile` | All workflow targets (`make help` for list) |

## Repository Structure

```
simulation/   Gazebo Harmonic world, robot URDF, sensor configs, launch files
robotics/     ROS 2 adapters, perception, localization, navigation, models, battery
fleet/        FleetOrchestrator, mission manager, task allocators, collision, failure
payments/     Agentic payment layer — agent, policy, provider boundary, mock Circle/Arc
ml/           FleetEnv (Gymnasium), policies (random, MAPPO), training pipeline
validator/    ValidatorRunner, PoPW scoring engine, sandbox, reproducibility
protocol/     PoPW proof serialization + Konnex adapter boundary
backend/      FastAPI app, routers, services, event bus, DB
frontend/     React 18 + TypeScript + Vite + Tailwind dashboard
experiments/  Benchmark configs (exp_001…exp_006), runner scripts, results/
tests/        unit / integration / simulation / e2e
scripts/      setup, demo, benchmark, environment check, payment demo
infra/        Prometheus + Grafana provisioning
```

## Konnex Integration Status

Two-tier integration (Spark + Launch):

- **Spark tier — HTTP-based** (`protocol/konnex/real_provider.py`): implements the
  3 documented HTTP endpoints (`/api/v1/tasks`, `/api/v1/miners/models`,
  `/api/v1/validators/verify`) via `httpx`. `query_rewards` and
  `get_submission_status` remain STUBs (no documented endpoint).
- **Launch tier — on-chain** (`protocol/konnex/bittensor_provider.py` +
  `protocol/konnex/synapse.py`): bittensor-based provider + `FleetMissionSynapse`
  using the konnex-chain-sdk (bittensor fork). Live chain ops remain STUBs
  (need testnet funds + registered hotkey). `query_rewards` reads from the
  metagraph; `get_submission_status` queries extrinsics.
- **Mock provider** (`MockKonnexProvider`): full lifecycle, used for demos.
- Provider factory supports `disabled` / `mock` / `real` / `bittensor` modes.
- Adapter is intentionally decoupled from the fleet core (zero imports from
  robotics/sim/ml layers). 24 contract tests pass.

## FleetPay Agent — Agentic Payments (Arc + Circle USDC)

A new `payments/` domain layer turns the fleet agent into an economic actor:
`Fleet Event → AI Agent → Provider Evaluation → Payment Intent → Policy
Engine → Circle Wallet → USDC → Arc → Settlement → Receipt`. The AI never
holds keys — a deterministic payment-policy engine (max-tx, daily budget,
provider allowlist, address validation) gates every payment.

- **API:** `/api/v1/payments/{quote,authorize,execute,demo,wallet,transactions,summary}`
- **Dashboard:** "FleetPay Agent" panel — wallet, agent decisions, provider
  comparison, payment history with `0xMOCK…` hashes and MOCK explorer links
- **Demo:** `make payment-demo` (terminal) or `make demo` → dashboard → **Run demo**
- **Contract:** `payments/contracts/FleetPayment.sol` (reference, not deployed)
- **Honesty:** mock mode is fully MOCK-labeled; the real Circle Wallets + Arc
  provider is implemented but has never run without credentials — no live
  transfer is claimed — see `docs/payments.md`

## Roadmap

```
Prototype (current) — Spark grant
  → Complete MAPPO training + validation
  → Gazebo Docker integration
  → Physical robot pilot prototype

Testnet — Launch grant ($75K)
  → Cloud deployment + auto-scaling
  → 3+ validators with consensus
  → Public demo endpoint

Mainnet — $200K+
  → Konnex network integration (actual SDK)
  → On-chain policy registry + KNX rewards
  → Open policy marketplace
  → Multi-robot physical fleet
```

## Environment Requirements

| Tool | Version | Status |
|---|---|---|
| Python | 3.10+ (dev: 3.11.5) | ✓ |
| Node.js | 20+ (dev: 22.12.0) | ✓ |
| Docker | 20+ (dev: 29.7.2) | ✓ |
| ROS 2 | Humble | Containerized |
| Gazebo | Harmonic | Containerized |

## License

Apache 2.0 — see `LICENSE`.
