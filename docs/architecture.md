# Architecture — Konnex Fleet Intelligence Subnet

> **Phase 0 deliverable** (BUILD.md §3). Status: COMPLETE (design doc).
> Source of truth: AGENTS.md §3 (Architecture Skills) and BUILD.md.

---

## 1. System Context

A Konnex subnet that lets competing AI policies coordinate an autonomous robot fleet on warehouse delivery missions, with validator-scored, reproducible physical-work outcomes and (eventually) KNX rewards.

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

## 2. Layer Map (AGENTS.md §3.1)

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

## 3. Component Descriptions

| Component | Directory | Responsibility |
|---|---|---|
| **Gazebo simulation** | `simulation/` | Warehouse world (40×30 m), 15 shelf obstacles, 5 AMR robots, LiDAR/IMU/odometry |
| **Robotics core** | `robotics/` | RobotAdapter protocol (sim/physical), perception, localization (AMCL), navigation (Nav2), battery model, sensor frames. **Zero imports from `protocol/konnex/`** |
| **Fleet orchestrator** | `fleet/` | Task assignment via pluggable allocators (nearest, hungarian, cost_optimizer), mission lifecycle, collision monitor, failure detection, comm model |
| **ML platform** | `ml/` | Gymnasium multi-agent `FleetEnv`, policies (random, MAPPO), training pipeline, MLflow tracking |
| **Validator** | `validator/` | `ValidatorRunner`, PoPW scoring engine, sandboxed policy execution, reproducibility artifacts, anti-gaming checks |
| **Protocol / Konnex** | `protocol/` | PoPW proof dataclasses + serializer; `KonnexAdapter` is a **STUB** until the SDK is verified (`# TODO: verify SDK`) |
| **Backend** | `backend/` | FastAPI app: REST API (`/api/v1`), WebSocket `/ws/fleet`, services, event bus, DB access |
| **Frontend** | `frontend/` | React 18 + TS dashboard: live 3D map, mission panel, metrics, validator/policy views. Never talks to Gazebo directly |
| **Benchmarks** | `experiments/` | Seeded experiment configs (exp_001…006), runner + report scripts, results/ (real runs only) |
| **Infrastructure** | `infra/` + docker-compose | PostgreSQL 16, Redis 7, MinIO, MLflow 2.11, Prometheus 2.51, Grafana 10.4 |

## 4. Allowed Data Flows (AGENTS.md §3.3)

```
Frontend → Backend API (REST)              ✅ POST /missions, GET /robots
Frontend ← Backend WebSocket              ✅ Live robot states, events
Backend → Fleet Orchestrator (direct call) ✅ In-process (same Python process)
Backend → ROS 2 (via ROSBridge)           ✅ Thread-safe callback queue
Fleet Orchestrator → Robot Adapters       ✅ Protocol-defined interface
Robot Adapters → Gazebo (via ROS 2)       ✅ ROS 2 topics/services
Validator → Policy Container (Docker API) ✅ JSON lines over stdin/stdout, network=none
Validator → Gazebo (via ROS 2)            ✅ Spawn/reset environment
Validator → Backend (evaluation result)   ✅ POST /evaluations
Backend → MinIO/S3 (artifact storage)     ✅ boto3
Backend → Redis (cache + task queue)      ✅ redis
Konnex Adapter ← PoPW Adapter             ✅ Adapter calls adapter
ML Training → FleetEnv (Gymnasium)        ✅ Training loop uses env
MLflow ← ML Training (metrics logging)   ✅ mlflow.log_metric()
```

## 5. Forbidden Cross-Layer Imports (AGENTS.md §3.2)

Architecture violations that must never exist:

```python
from protocol.konnex.adapter import KonnexAdapter  # in robotics/ or fleet/ ❌
import rclpy                                        # in frontend             ❌
from fleet.orchestrator import FleetOrchestrator    # in validator/runner.py ❌
from ml.training.train import MAPPOTrainer          # in backend/services    ❌
from validator.scoring.engine import PoPWScoringEngine  # in ml/policies      ❌
```

## 6. Event System (AGENTS.md §3.4)

In-process asyncio event bus (`backend/events/`) with typed dataclasses:

`MISSION_CREATED` · `TASK_ASSIGNED` · `ROBOT_STATE_UPDATE` · `COLLISION_DETECTED` · `MISSION_COMPLETE` · `EVALUATION_COMPLETE`

Events are broadcast to WebSocket clients by `backend/events/handlers/websocket_handler.py` without blocking request handlers.

## 7. Deployment (docker-compose.yml — AGENTS.md §3.6)

Services: `postgres` · `redis` · `minio` · `gazebo` (Phase 1) · `backend` · `arq-worker` · `frontend` · `validator` (Phase 6) · `mlflow` · `prometheus` · `grafana`.

Shared network `fleet-net`; named volumes for all stateful services.

## 8. Scalability Path (AGENTS.md §3.7)

```
LEVEL 1 — Prototype (current)     single docker-compose, SQLite→PostgreSQL, local MinIO, 1 validator
LEVEL 2 — Testnet ($75K)          cloud deployment, managed DB/S3, 3+ validators, public endpoint
LEVEL 3 — Mainnet ($200K+)        Konnex SDK integration, on-chain registry, distributed validators
```

## 9. Configuration (AGENTS.md §3.5)

All configuration is environment-driven via Pydantic Settings (`backend/config.py`); `.env.example` documents every variable. No hard-coded URLs, passwords, or ports.
