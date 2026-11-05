# PLAN.md — Konnex Fleet Intelligence Subnet
## Product Requirements & Design Document

> **Version:** 0.1.0-draft  
> **Status:** Pre-implementation  
> **Project:** `konnex-fleet-subnet`  
> **Target Programme:** Konnex Builder Program — Robot Fleet Orchestration category

---

## 1. Executive Summary

This document defines the product requirements and design strategy for a **Konnex subnet** that establishes decentralized incentive and evaluation infrastructure for coordinating autonomous robot fleets on physical-world warehouse missions.

The subnet operates on Konnex's **Proof-of-Physical-Work (PoPW)** model: miners submit fleet-control policies, validators execute those policies in standardized simulation environments, score the real physical-world outcomes, and distribute rewards to the best-performing policies.

The goal of the Spark grant milestone ($25K) is a **working prototype** demonstrating five simulated robots completing warehouse delivery missions under competing policies with reproducible, validator-scored outcomes.

---

## 2. Problem Statement

### 2.1 Why robot fleet coordination needs decentralized incentives

Modern autonomous robot fleets face three unsolved coordination problems:

1. **Policy development is centralized** — one company controls one policy; there is no competitive market for fleet intelligence.
2. **Performance evaluation is opaque** — no objective, reproducible standard for measuring "how well did this fleet actually do?"
3. **There is no economic incentive** to contribute better robot coordination algorithms to a shared commons.

Konnex's PoPW model can solve all three: open policy submission, validator-scored physical outcomes, and token rewards for verified performance.

### 2.2 What this subnet enables

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

---

## 3. Target Users

| Actor | Role | Motivation |
|---|---|---|
| **Policy Miners** | Submit fleet-control policies (classical or ML) | Earn KNX rewards for high performance |
| **Validators** | Execute policies, score outcomes, publish proofs | Earn validation fees |
| **Mission Requesters** | Post warehouse delivery missions | Get tasks completed |
| **Robot Operators** | Eventually run physical robots on earned policies | Deploy proven intelligence |
| **Konnex Reviewers** | Evaluate the subnet for grant acceptance | Verify technical credibility |

---

## 4. Core Features — MVP Scope

### 4.1 Must-have (Spark grant demo)

- [ ] Warehouse simulation in Gazebo with 5 autonomous mobile robots
- [ ] Package pickup/delivery mission structure with randomized scenarios
- [ ] Three classical baseline policies: nearest-task, Hungarian, cost-optimizer
- [ ] Fleet orchestrator: task allocation, collision avoidance, failure detection
- [ ] Automated benchmark runner comparing all policies
- [ ] Validator service: reproducible policy execution + scoring
- [ ] PoPW-inspired score engine (clearly labeled as prototype)
- [ ] Fleet monitoring dashboard (React + Vite)
- [ ] `make demo` and `make benchmark` single-command entrypoints
- [ ] Docker Compose deployment
- [ ] CI with lint + unit + integration tests

### 4.2 Should-have (Launch grant demo, $75K)

- [ ] MAPPO multi-agent RL policy
- [ ] Robot failure simulation + dynamic task reassignment
- [ ] Communication degradation model
- [ ] Policy containerization / sandboxed submission
- [ ] Experiment tracking (MLflow)
- [ ] Konnex SDK adapter (post SDK research)
- [ ] GNN fleet representation (if benchmarks justify it)

### 4.3 Nice-to-have (Mainnet, $200K+)

- [ ] Physical robot adapter (ROS 2 hardware interface)
- [ ] Domain randomization for sim-to-real
- [ ] Multi-validator consensus on scores
- [ ] On-chain evaluation commitment + hash anchoring
- [ ] Digital twin synchronization

### 4.4 Explicitly out of scope

- Real robot hardware (MVP phase)
- Actual Konnex token issuance (adapter only)
- More than 5 robots in the MVP benchmark
- Custom simulator (Gazebo is sufficient)

---

## 5. Mission Design

### 5.1 Mission structure

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

### 5.2 Mission generator

The generator must randomize all parameters from a seed so that any validator can reconstruct the exact same scenario deterministically. Hard-coded scenarios are prohibited.

---

## 6. Robot Model

Each simulated robot exposes this state surface to the fleet orchestrator and policy:

```python
@dataclass
class RobotState:
    id: str
    position: Vector2D        # (x, y) in world frame
    orientation: float        # radians
    velocity: Vector2D        # (vx, vy) m/s
    battery_pct: float        # 0.0–1.0
    current_task: Task | None
    nav_state: NavState       # IDLE | MOVING | BLOCKED | CHARGING
    collision_state: bool
    sensor_data: SensorFrame  # LiDAR + odometry
    comm_state: CommState     # ONLINE | DEGRADED | OFFLINE
```

Robot components are modular and independently testable:

```
Robot
├── LiDAR sensor
├── IMU / odometry
├── Localization (AMCL)
├── Navigation (Nav2)
├── Local planner (DWA)
├── Collision monitor
├── Battery model (linear drain + task cost)
├── Task executor (state machine)
└── Fleet agent (receives assignments, reports status)
```

---

## 7. Fleet Orchestrator Design

### 7.1 Responsibility

The orchestrator is the single entity that knows global fleet state and makes assignment decisions. It does NOT control individual robot actuators — it only assigns tasks.

```
Mission
  ↓
Orchestrator
  ├── Decompose into tasks
  ├── Score robot-task pairs via cost model
  ├── Assign via optimization
  ├── Monitor execution
  ├── Detect failures
  └── Reassign on failure
```

### 7.2 Baseline policies

| Policy | Algorithm | Complexity |
|---|---|---|
| `nearest` | Greedy: assign task to closest available robot | O(R × T) |
| `hungarian` | Optimal bipartite matching on distance matrix | O(R³) |
| `cost_optimizer` | Weighted multi-factor cost minimization | O(R × T) |
| `mappo` (Phase 4) | Multi-Agent PPO, centralized training / decentralized execution | — |

### 7.3 Cost function (cost_optimizer)

```python
cost(robot, task) = (
    w1 * normalize(distance(robot.pos, task.pickup)) +
    w2 * normalize(1 - robot.battery_pct) +
    w3 * normalize(task_priority_inverse(task.priority)) +
    w4 * normalize(local_congestion(robot.pos)) +
    w5 * normalize(collision_risk(robot.pos, task.pickup))
)
```

Weights are configurable via `config/cost_weights.yaml`.

---

## 8. PoPW Score Design

The evaluation score is a **prototype** mechanism. It is not Konnex's official scoring algorithm. It will be adapted to match the actual Konnex SDK once that is reviewed.

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

---

## 9. Validator Design

The validator is the trust anchor of the subnet.

### 9.1 Inputs

```
policy_id      — identifier of the submitted policy
policy_hash    — SHA-256 of policy weights/code
scenario_id    — mission definition
seed           — random seed for deterministic reproduction
env_version    — Gazebo world version hash
sim_version    — ROS 2 / Gazebo version string
```

### 9.2 Outputs

```
trajectory     — full robot path data
task_outcomes  — per-task completion status
energy_log     — per-robot energy consumption
collision_log  — timestamped collision events
completion_time
score_components
final_score
evaluation_hash
signature
```

### 9.3 Reproducibility requirement

Two independent validators running the same (policy_hash, scenario_id, seed, env_version) MUST produce scores within ±0.5 points of each other. Any larger divergence flags the evaluation as UNSTABLE.

---

## 10. Anti-Gaming Measures (MVP)

| Threat | MVP Mitigation |
|---|---|
| Reward hacking via scenario exploitation | Randomized scenarios + fixed seed per evaluation |
| Fake trajectories | Validator executes policy directly; no self-reported telemetry |
| Replay attacks | Evaluation timestamps + nonce |
| Sandbox escape | Container CPU/memory limits + network isolation |
| Policy tampering | SHA-256 hash verification before execution |
| Validator collusion | Multiple validator requirement (post-MVP) |

---

## 11. Development Phases

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

---

## 12. Konnex Grant Application Positioning

The application should be framed as:

> "We built an incentive and evaluation infrastructure layer that allows competing AI policies to coordinate physical robot fleets, objectively measure their real-world performance, and earn rewards for verified physical work."

NOT as:

> "We built a cool robot simulator."

Key differentiators to highlight:
- Reproducible validator scoring (not self-reported metrics)
- Competing policy marketplace (not a single fixed controller)
- PoPW-aligned physical-work measurement
- Clear path from simulation → physical robots via hardware abstraction

---

## 13. Success Criteria for Spark Grant Submission

- [ ] `make demo` runs end-to-end in under 3 minutes
- [ ] `make benchmark` produces a comparison table with real numbers
- [ ] At least 3 policies with statistically meaningful differences
- [ ] Validator reproduces any result from (policy_hash + seed)
- [ ] Dashboard shows live robot state during demo
- [ ] All results in `experiments/results/` are from actual runs
- [ ] README contains a demo video link
- [ ] `KONNEX_APPLICATION.md` is complete and accurate

---

*This document is a living specification. Update it before beginning each phase.*
