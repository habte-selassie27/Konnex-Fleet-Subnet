# BUILD.md — Technical Implementation Specification
## Konnex Fleet Intelligence Subnet — System Architecture

> **Phase:** All phases (read before each phase)  
> **Audience:** Coding agents and engineers implementing the system  
> **Companion files:** PLAN.md (what to build), SYSTEM_PROMPT.md (how to behave), TESTING_PLAN.md (how to verify)

---

## 1. Repository Structure

```
konnex-fleet-subnet/
│
├── README.md
├── PLAN.md
├── BUILD.md
├── SYSTEM_PROMPT.md
├── TESTING_PLAN.md
├── KONNEX_APPLICATION.md          # written last, after benchmarks
├── LICENSE                        # Apache 2.0
├── CONTRIBUTING.md
├── SECURITY.md
│
├── Makefile                       # make setup | demo | benchmark | test | lint
├── docker-compose.yml
├── .env.example
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── docs/
│   ├── architecture.md
│   ├── protocol.md
│   ├── powp.md
│   ├── robotics.md
│   ├── ml.md
│   ├── benchmarking.md
│   ├── security.md
│   └── sim-to-real.md
│
├── simulation/
│   ├── worlds/
│   │   └── warehouse_v1.sdf
│   ├── robots/
│   │   └── amr_model.urdf.xacro
│   ├── sensors/
│   │   ├── lidar.yaml
│   │   └── imu.yaml
│   ├── scenarios/
│   │   ├── scenario_generator.py
│   │   └── templates/
│   └── launch/
│       ├── warehouse.launch.py
│       └── multi_robot.launch.py
│
├── robotics/
│   ├── __init__.py
│   ├── adapters/
│   │   ├── base.py                # RobotAdapter Protocol
│   │   ├── simulation.py          # SimulationRobotAdapter
│   │   └── physical.py            # PhysicalRobotAdapter (stub Phase 1–8)
│   ├── perception/
│   │   └── lidar_processor.py
│   ├── localization/
│   │   └── amcl_interface.py
│   ├── navigation/
│   │   ├── nav2_interface.py
│   │   └── path_planner.py
│   ├── models/
│   │   ├── robot_state.py         # RobotState dataclass
│   │   ├── task.py                # Task, Assignment dataclasses
│   │   ├── fleet_state.py         # FleetState
│   │   └── sensor_frame.py        # SensorFrame
│   └── battery/
│       └── battery_model.py
│
├── fleet/
│   ├── __init__.py
│   ├── orchestrator.py            # FleetOrchestrator main class
│   ├── mission_manager.py         # Mission lifecycle
│   ├── task_allocator/
│   │   ├── base.py                # TaskAllocator Protocol
│   │   ├── nearest.py             # NearestTaskAllocator
│   │   ├── hungarian.py           # HungarianAllocator
│   │   └── cost_optimizer.py      # CostOptimizerAllocator
│   ├── collision/
│   │   ├── monitor.py
│   │   └── avoidance.py
│   ├── failure/
│   │   └── detector.py
│   └── communication/
│       └── model.py               # Latency + packet loss simulation
│
├── ml/
│   ├── __init__.py
│   ├── env/
│   │   ├── fleet_env.py           # Gymnasium multi-agent environment
│   │   ├── observation_space.py
│   │   └── action_space.py
│   ├── policies/
│   │   ├── base.py                # FleetPolicy Protocol
│   │   ├── random.py              # RandomPolicy (sanity check)
│   │   └── mappo/
│   │       ├── agent.py
│   │       ├── network.py
│   │       ├── trainer.py
│   │       └── config.yaml
│   ├── training/
│   │   ├── train.py
│   │   └── callbacks.py
│   └── checkpoints/
│       └── .gitkeep
│
├── validator/
│   ├── __init__.py
│   ├── runner.py                  # ValidatorRunner
│   ├── scoring/
│   │   ├── engine.py              # PoPW score calculator
│   │   └── components.py          # Individual score components
│   ├── sandbox/
│   │   ├── container.py           # Policy containerization
│   │   └── resource_limits.py
│   ├── reproducibility/
│   │   ├── artifact.py            # EvaluationArtifact
│   │   └── verifier.py
│   └── anti_gaming/
│       └── checks.py
│
├── protocol/
│   ├── __init__.py
│   ├── powp/
│   │   ├── proof.py               # ProofOfPhysicalWork dataclass
│   │   └── serializer.py
│   └── konnex/
│       ├── adapter.py             # KonnexAdapter (stub until SDK verified)
│       └── models.py
│
├── backend/
│   ├── main.py                    # FastAPI app entrypoint
│   ├── routers/
│   │   ├── missions.py
│   │   ├── policies.py
│   │   ├── evaluations.py
│   │   ├── robots.py
│   │   └── metrics.py
│   ├── services/
│   │   ├── mission_service.py
│   │   ├── policy_service.py
│   │   └── evaluation_service.py
│   ├── events/
│   │   ├── bus.py                 # Internal event bus
│   │   └── types.py               # Event dataclasses
│   └── db/
│       ├── database.py
│       └── models.py
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── components/
│       │   ├── FleetMap.tsx        # Live robot position visualization
│       │   ├── MissionStatus.tsx
│       │   ├── MetricsPanel.tsx
│       │   ├── PolicySelector.tsx
│       │   └── ValidatorLog.tsx
│       ├── services/
│       │   └── api.ts
│       └── types/
│           └── index.ts
│
├── experiments/
│   ├── configs/
│   │   ├── exp_001_nearest.yaml
│   │   ├── exp_002_hungarian.yaml
│   │   ├── exp_003_cost_optimizer.yaml
│   │   ├── exp_004_mappo.yaml
│   │   ├── exp_005_mappo_failure.yaml
│   │   └── exp_006_fleet_scaling.yaml
│   ├── scripts/
│   │   ├── run_experiment.py
│   │   └── generate_report.py
│   └── results/
│       └── .gitkeep               # Populated by actual experiment runs
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_task_allocator.py
│   │   ├── test_cost_function.py
│   │   ├── test_battery_model.py
│   │   ├── test_scoring_engine.py
│   │   ├── test_scenario_generator.py
│   │   └── test_evaluation_artifact.py
│   ├── integration/
│   │   ├── test_fleet_orchestration.py
│   │   ├── test_mission_lifecycle.py
│   │   └── test_validator_runner.py
│   ├── simulation/
│   │   └── test_robot_navigation.py
│   └── e2e/
│       └── test_full_mission.py
│
└── scripts/
    ├── setup.sh
    ├── demo.sh
    ├── benchmark.sh
    └── check_environment.sh
```

---

## 2. Technology Stack

### 2.1 Core stack

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

### 2.2 What we explicitly avoided and why

| Avoided | Reason |
|---|---|
| Isaac Sim | GPU required; overkill for MVP; complex licensing |
| Kubernetes | Not needed until actual subnet scale |
| Kafka | No real-time message volume that justifies it at MVP |
| Ray / RLlib | Heavier than needed; stable-baselines3 sufficient for Phase 4 |
| Custom SLAM | AMCL (Nav2 built-in) is sufficient for warehouse AMR |

---

## 3. Phase 0 — Architecture Setup

### Deliverables

```
docs/architecture.md        (system diagram + component descriptions)
docs/requirements.md        (dependency versions, environment requirements)
docs/mvp.md                 (MVP scope definition)
docs/development-plan.md    (phases + acceptance criteria)
```

### Environment check script

```bash
#!/bin/bash
# scripts/check_environment.sh
echo "=== Konnex Fleet Subnet — Environment Check ==="

check() { command -v "$1" &>/dev/null && echo "✓ $1" || echo "✗ $1 NOT FOUND"; }

check ros2
check gz          # Gazebo Harmonic
check python3
check pip
check docker
check docker-compose
check node
check npm

python3 -c "import torch; print(f'✓ PyTorch {torch.__version__}')" 2>/dev/null || echo "✗ PyTorch not installed"
python3 -c "import rclpy; print('✓ rclpy')" 2>/dev/null || echo "✗ rclpy not installed"
```

### Makefile targets (define all upfront)

```makefile
.PHONY: setup demo benchmark test lint clean

setup:
	@bash scripts/setup.sh

demo:
	@docker-compose up --build fleet-demo

benchmark:
	@python experiments/scripts/run_experiment.py --all --report

test:
	@pytest tests/ -v --cov=. --cov-report=term-missing

lint:
	@ruff check .
	@mypy . --ignore-missing-imports
	@cd frontend && npm run lint

clean:
	@docker-compose down -v
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
```

---

## 4. Phase 1 — Simulation

### Warehouse world spec

```xml
<!-- simulation/worlds/warehouse_v1.sdf -->
<!-- World: 40m x 30m floor plan -->
<!-- Static obstacles: 15 shelf units (1m x 4m x 2m) -->
<!-- Pickup zones: 5 marked floor areas -->
<!-- Delivery zones: 5 marked floor areas -->
<!-- Lighting: uniform overhead (no shadows) -->
```

### Robot model

Each AMR is a differential-drive robot:

```
chassis: 0.5m x 0.5m x 0.3m, mass: 20kg
wheel_base: 0.4m
max_linear_velocity: 1.0 m/s
max_angular_velocity: 1.5 rad/s
lidar: 360° scan, 10m range, 1° resolution, 10Hz
imu: 100Hz
odometry: 50Hz
battery_capacity: 100 units
battery_drain_rate: 0.1 unit/s (moving), 0.02 unit/s (idle)
```

### Robot state dataclass

```python
# robotics/models/robot_state.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class NavState(Enum):
    IDLE = "idle"
    MOVING = "moving"
    BLOCKED = "blocked"
    CHARGING = "charging"
    FAILED = "failed"

class CommState(Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"

@dataclass
class Vector2D:
    x: float
    y: float

@dataclass
class RobotState:
    id: str
    position: Vector2D
    orientation: float          # radians, world frame
    velocity: Vector2D
    battery_pct: float          # 0.0–1.0
    current_task: Optional["Task"] = None
    nav_state: NavState = NavState.IDLE
    in_collision: bool = False
    sensor_data: Optional["SensorFrame"] = None
    comm_state: CommState = CommState.ONLINE
    timestamp: float = 0.0
```

### ROS 2 launch structure

```python
# simulation/launch/multi_robot.launch.py
# Spawns N robots with unique namespaces: /robot_0, /robot_1, ... /robot_N-1
# Each robot gets:
#   - joint_state_publisher
#   - robot_state_publisher
#   - nav2 stack (amcl + costmap + planner + controller)
#   - lidar driver
#   - fleet_agent node
```

---

## 5. Phase 2 — Fleet Orchestration

### FleetOrchestrator

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

### Task allocation Protocol

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

### Hungarian allocator

```python
# fleet/task_allocator/hungarian.py
from scipy.optimize import linear_sum_assignment
import numpy as np

class HungarianAllocator:
    name = "hungarian"
    
    def assign(self, robots, tasks):
        # Build cost matrix: shape (n_robots, n_tasks)
        # Cost = Euclidean distance from robot.position to task.pickup
        # Apply linear_sum_assignment for optimal bipartite matching
        # Return list[Assignment]
```

### Cost optimizer

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
        """
```

### Failure detector

```python
# fleet/failure/detector.py
class FailureDetector:
    """
    Monitors robot health and emits FailureEvents.
    Thresholds configurable via config/failure_thresholds.yaml.
    """
    
    LOW_BATTERY_THRESHOLD = 0.15
    STUCK_TIMEOUT_S = 30.0
    COMM_LOSS_TIMEOUT_S = 10.0
    
    def check(self, state: RobotState, history: list[RobotState]) -> list[FailureEvent]:
        """Returns any new failure events for this robot."""
```

---

## 6. Phase 3 — Benchmarking Engine

### Experiment config schema

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

### Benchmark report format

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

---

## 7. Phase 4 — MARL (MAPPO)

### Environment wrapper

```python
# ml/env/fleet_env.py
import gymnasium as gym
from gymnasium import spaces
import numpy as np

class FleetEnv(gym.Env):
    """
    Multi-agent Gymnasium environment wrapping the Fleet Orchestrator.
    One agent per robot.
    Centralized training / decentralized execution (CTDE).
    """
    
    metadata = {"render_modes": ["human", "rgb_array"]}
    
    def __init__(self, config: FleetEnvConfig) -> None: ...
    
    @property
    def observation_space(self) -> spaces.Dict:
        return spaces.Dict({
            "robot_pos": spaces.Box(-50, 50, (2,), np.float32),
            "robot_vel": spaces.Box(-2, 2, (2,), np.float32),
            "battery": spaces.Box(0, 1, (1,), np.float32),
            "task_rel_pos": spaces.Box(-50, 50, (2,), np.float32),
            "nearby_robots": spaces.Box(-50, 50, (4, 2), np.float32),  # 4 nearest
            "lidar_scan": spaces.Box(0, 10, (36,), np.float32),        # 10° bins
            "has_task": spaces.Discrete(2),
            "fleet_utilization": spaces.Box(0, 1, (1,), np.float32),
        })
    
    @property
    def action_space(self) -> spaces.Box:
        # [linear_velocity, angular_velocity]
        return spaces.Box(
            low=np.array([-1.0, -1.5]),
            high=np.array([1.0, 1.5]),
            dtype=np.float32,
        )
```

### Observation design rationale

| Observation | Why included | Why limited |
|---|---|---|
| `robot_pos` | Robot needs to know where it is | Global frame; known from odometry |
| `task_rel_pos` | Navigate to task | Relative, not absolute (generalizes better) |
| `nearby_robots` | Collision avoidance | 4 nearest only — full fleet state is too large |
| `lidar_scan` | Obstacle detection | 36 bins (10° resolution) = compact but sufficient |
| `has_task` | Task awareness | Binary flag |
| `fleet_utilization` | Global context signal | Scalar summary, not per-robot global state |

**Not included:** absolute positions of all other robots, full map, task queue, battery of other robots. These would leak global state that won't be available in decentralized deployment.

### Reward function

```python
# ml/env/fleet_env.py (reward method)
def _compute_reward(self, robot_id: str, prev_state: RobotState, curr_state: RobotState, event: StepEvent) -> float:
    reward = 0.0
    
    # Task completion (sparse, high magnitude)
    if event.task_completed:
        reward += 10.0
    
    # Progress toward task pickup/delivery (dense shaping)
    if curr_state.current_task:
        prev_dist = distance(prev_state.position, curr_state.current_task.pickup)
        curr_dist = distance(curr_state.position, curr_state.current_task.pickup)
        reward += 0.1 * (prev_dist - curr_dist)  # positive if getting closer
    
    # Energy efficiency
    reward -= 0.001 * event.energy_consumed
    
    # Collision penalty (severe)
    if event.collision:
        reward -= 5.0
    
    # Deadlock penalty (mild, time-based)
    if event.stuck_duration > 5.0:
        reward -= 0.05 * event.stuck_duration
    
    # Mission complete bonus
    if event.mission_complete:
        time_bonus = max(0, 1.0 - (event.elapsed / self.config.time_limit))
        reward += 20.0 * time_bonus
    
    return reward
```

### MAPPO training config

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

---

## 8. Phase 6 — Validator

### ValidatorRunner

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

### EvaluationArtifact

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

---

## 9. Phase 7 — PoPW Score Engine

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

## 10. Phase 8 — Konnex Adapter

> **IMPORTANT:** Do not implement actual SDK calls until Konnex SDK documentation is reviewed.  
> The interface below is a stub. All methods raise `NotImplementedError` until verified.

```python
# protocol/konnex/adapter.py

class KonnexAdapter:
    """
    Adapter between the Fleet subnet and the Konnex network.
    
    STUB: Methods are not implemented until the Konnex SDK is reviewed.
    See: https://docs.konnex.network (verify URL before implementation)
    
    The robotics core has NO dependency on this class.
    This class depends on EvaluationArtifact and PoPWScore only.
    """
    
    def submit_mission(self, metadata: MissionMetadata) -> str:
        """Returns mission_id. Raises KonnexAdapterError on failure."""
        raise NotImplementedError("# TODO: verify Konnex SDK submitMission()")
    
    def submit_policy(self, policy_id: str, policy_hash: str) -> str:
        """Register a policy. Returns registration_id."""
        raise NotImplementedError("# TODO: verify Konnex SDK submitPolicy()")
    
    def publish_proof(self, artifact: EvaluationArtifact) -> str:
        """Publish evaluation proof on-chain. Returns tx_hash."""
        raise NotImplementedError("# TODO: verify Konnex SDK publishProof()")
    
    def query_rewards(self, policy_id: str) -> float:
        """Query pending KNX rewards for a policy."""
        raise NotImplementedError("# TODO: verify Konnex SDK queryRewards()")
```

---

## 11. Backend API Spec

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

---

## 12. Docker Compose Architecture

```yaml
# docker-compose.yml
services:
  
  gazebo:
    build: ./simulation
    environment:
      - ROS_DOMAIN_ID=42
    volumes:
      - ./simulation/worlds:/worlds:ro
    networks: [fleet-net]
    
  fleet-backend:
    build: ./backend
    depends_on: [gazebo, postgres]
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://fleet:fleet@postgres/fleet
      - FLEET_API_KEY=${FLEET_API_KEY:-dev-only-key}
    networks: [fleet-net]
    
  fleet-frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [fleet-backend]
    networks: [fleet-net]
    
  validator:
    build: ./validator
    depends_on: [gazebo, fleet-backend]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock  # for policy containers
      - ./experiments/results:/results
    networks: [fleet-net]
    
  mlflow:
    image: ghcr.io/mlflow/mlflow:v2.11.0
    ports: ["5000:5000"]
    volumes:
      - mlflow-data:/mlflow
    networks: [fleet-net]
    
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: fleet
      POSTGRES_USER: fleet
      POSTGRES_PASSWORD: fleet
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks: [fleet-net]

networks:
  fleet-net:

volumes:
  mlflow-data:
  postgres-data:
```

---

## 13. Data Storage Strategy

| Data type | Format | Storage | Retention |
|---|---|---|---|
| Robot trajectories | Parquet | `experiments/results/{exp_id}/` | Permanent |
| Per-step telemetry | Parquet | `experiments/results/{exp_id}/` | Per experiment |
| Mission records | PostgreSQL | DB | Permanent |
| Evaluation artifacts | JSON + SHA-256 | DB + filesystem | Permanent |
| ML checkpoints | PyTorch `.pt` | `ml/checkpoints/` | Latest 5 |
| Experiment metrics | MLflow | MLflow server | Permanent |
| Logs | JSON (structlog) | stdout + file | 30 days |

---

*Update this document when technology decisions change. Every deviation from this spec must be documented with justification.*
