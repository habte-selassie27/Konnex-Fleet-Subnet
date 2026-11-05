# Simulation

## Running Gazebo-gated tests (Phase 1)

The sim tests in `tests/simulation/` self-skip when the `gz` CLI is not on
the host PATH (this machine: ROS 2/Gazebo are containerized).

### Exact blocker

- Host has no `gz`, `gz-sim`, or `ros2` binary (verified 2026-11-02).
- The `gazebo` container (image `autonomousfleetintelligence-gazebo:latest`,
  3.87 GB) boots the warehouse world + 5 robots + gz↔ROS bridge successfully
  (`docker compose up gazebo`), but it does NOT contain the repository's Python
  test harness or `pytest`, so the sim tests cannot be executed inside it as-is.

### Repro steps to run them

1. Build the image: `docker compose build gazebo` (or `make sim`).
2. Start it headless: `docker compose up -d gazebo`.
3. Confirm it is serving: `docker compose exec gazebo bash -lc "gz topic -l | grep /clock"`.
4. To actually execute `tests/simulation/`, mount the repo and install pytest
   inside the container (NOT automated yet):
   ```
   docker compose run --rm -v "$PWD:/ws/repo" gazebo bash -lc \
     "apt-get update && apt-get install -y python3-pytest && cd /ws/repo && python3 -m pytest tests/simulation -m simulation"
   ```
5. Alternatively, install ROS 2 Humble + Gazebo Harmonic on the host and run
   `make test-sim` directly.

### What IS verified without Gazebo

- `tests/unit/test_gazebo_adapter.py` (22 tests) and
  `tests/unit/test_ros_bridge.py` pass on the host; they exercise the adapter
  and bridge in inert mode (no rclpy).
- The `GazeboRobotAdapter` and `ROSBridge` import cleanly and no-op safely when
  rclpy is absent (see `is_available()`).

### Status

Live Gazebo execution of the fleet loop is **NOT RUN** on this machine.
Do not claim otherwise. — Gazebo Harmonic + ROS 2 (Phase 1)

> **Status: WIRING COMPLETE** — Docker image, launch files, gz↔ROS bridge,
> fleet_agent controller, GazeboRobotAdapter and backend ROS bridge are
> implemented and lint/test-gated.
> **Live Gazebo execution: NOT RUN on this machine** — ROS 2 / Gazebo are
> containerized (docs/requirements.md); the sim tests self-skip until
> `make sim` runs on a Gazebo-capable machine.

---

## 1. Architecture

```
                        ┌──────────────────────────────────────────┐
                        │  Gazebo container (simulation/Dockerfile) │
                        │  osrf/ros:humble-desktop                  │
                        │  + gazebo-harmonic + ros_gzharmonic       │
                        │                                           │
  warehouse_v1.sdf ───► │  gz-server (Harmonic)                     │
  amr_model.urdf.xacro  │    └─ /model/robot_N/odom  (DiffDrive)    │
  (spawned via          │    └─ /model/robot_N/lidar/scan (GPU lidar)│
   ros_gz_sim create)   │    └─ /model/robot_N/imu                  │
                        │    └─ /model/robot_N/cmd_vel              │
                        │              │  ▲                         │
                        │   ros_gz_bridge (parameter_bridge)        │
                        │              │  ▲                         │
                        │   /robot_N/odom  /robot_N/cmd_vel         │
                        │   /robot_N/scan  /robot_N/goal_pose       │
                        │   /robot_N/imu   /robot_N/battery         │
                        │              │  ▲                         │
                        │   fleet_agent node (go-to-goal + LiDAR    │
                        │   avoidance + modeled battery)            │
                        └──────────────┼────────────────────────────┘
                                       │  ROS_DOMAIN_ID=42
        ┌──────────────────────────────┴─────────────────────────────┐
        │  Backend (SIM_MODE=gazebo): backend/ros/ ROSBridge          │
        │  subscribes odom/scan/battery, publishes goals;             │
        │  robotics/adapters/gazebo.py GazeboRobotAdapter             │
        │  implements the same RobotAdapter protocol as the headless  │
        │  SimulationRobotAdapter — orchestrator/policies unchanged.  │
        └────────────────────────────────────────────────────────────┘
```

Two independent paths exist and share one abstraction (`RobotAdapter`,
`robotics/adapters/base.py`):

| Path | Adapter | Used when |
|---|---|---|
| Headless (deterministic, in-process) | `SimulationRobotAdapter` | default (`SIM_MODE=headless`) — the benchmark/validator/demo runs |
| Gazebo (physics, sensors) | `GazeboRobotAdapter` | `SIM_MODE=gazebo` (Phase 1 container) |

## 2. Components

### `simulation/worlds/warehouse_v1.sdf`
40 m × 30 m warehouse: 15 shelf units (4×1×2 m), 4 walls + floor, 5 pickup +
5 delivery zones, 2 charging stations, overhead lighting, 1 kHz physics.

### `simulation/robots/amr_model.urdf.xacro`
Differential-drive AMR: 0.5×0.5×0.25 m chassis (20 kg), wheelbase 0.4 m,
v_max 1.0 m/s, ω_max 1.5 rad/s, GPU LiDAR (360 beams, 10 m, 10 Hz), IMU
(100 Hz). Gazebo plugins: DiffDrive, gpu_lidar, imu, PosePublisher.

### `simulation/robots/fleet_agent.py`
Per-robot ROS 2 node (one per namespace `/robot_0 … /robot_4`):
- subscribes `/goal_pose` (PoseStamped), `/odom`, `/scan`;
- publishes `/cmd_vel` and a modeled `/battery` (0.1 u/s moving, 0.02 u/s idle);
- proportional heading controller with LiDAR obstacle stop + rotate-in-place
  recovery when the forward sector is blocked for `STUCK_TIMEOUT_S`.
- Plain node for Phase 1 (lifecycle-managed variant: documented follow-up).

### `simulation/launch/`
- `warehouse.launch.py` — launches `gz-sim` with the warehouse world via
  `ros_gz_sim` (Harmonic; Gazebo Classic `gazebo_ros` is **not** used).
- `multi_robot.launch.py` — includes the world, spawns N robots at
  deterministic seeded positions via `ros_gz_sim create -param
  robot_description` (xacro-processed URDF), starts `robot_state_publisher`
  + `joint_state_publisher` per namespace, one `fleet_agent` per robot, and a
  generated `ros_gz_bridge parameter_bridge` config covering
  odom/scan/imu/cmd_vel/tf per robot.

### `simulation/bridge/robot_bridge.yaml`
Static reference gz↔ROS bridge config for 5 robots (the launch generates an
equivalent config for the spawned count).

### `robotics/adapters/gazebo.py`
`GazeboRobotAdapter` (pure Python, transport-injected). The adapter publishes
goals, reads odometry/scan/battery, tracks task pickup→delivery phases, and
supports failure injection (COMM_LOSS/SHUTDOWN → OFFLINE + stop; NAV_FAILURE →
FAILED). Unit-tested with a fake transport without ROS 2; the ROS 2 transport
lives in `backend/ros/` (wiring into FleetAppState is the Phase 2 follow-up).

### `backend/ros/`
`ROSBridge` (rclpy spin thread + asyncio marshalling), `subscriber.py`,
`publisher.py`. Started only when `SIM_MODE=gazebo`; inert otherwise. This is
the only place in the backend that knows about ROS 2 (AGENTS.md §4.10).

## 3. How to run

```bash
make sim          # build + run the full containerized sim (world + robots + bridge)
make sim-world    # world only (warehouse.launch.py)
make sim-robots   # spawn robots into a running world (multi_robot.launch.py)
make sim-up       # start the gazebo container detached
make sim-down     # docker compose down
make sim-logs     # follow gazebo container logs
```

Requires Docker + a display/EGL. The first build pulls a multi-GB image.

To start the optional ROS 2 bridge beside the Gazebo container (see §5 —
this is bridge scaffolding; the fleet loop stays headless until the
GazeboRobotAdapter wiring follow-up):

```bash
SIM_MODE=gazebo ROS_DOMAIN_ID=42 python -m uvicorn backend.main:app --port 8000
```

## 4. Testing

| Suite | Command | Requires |
|---|---|---|
| Headless sim tests (19) | `pytest tests/simulation/ -m simulation` | nothing |
| Gazebo-gated tests (6) | same command | live gz-sim + rclpy (self-skip otherwise) |
| Adapter unit tests | `pytest tests/unit/test_gazebo_adapter.py` | nothing (fake transport) |
| Asset validation | `pytest tests/unit/test_simulation_assets.py` | nothing (XML checks) |
| Backend ROS bridge | `pytest tests/unit/test_ros_bridge.py` | nothing (inert w/o rclpy) |

On this machine the 6 Gazebo-gated tests report **skipped** (honest NOT RUN)
— they become live once `make sim` is executed on a Gazebo-capable machine.

## 5. Known limitations & follow-ups

- **`SIM_MODE=gazebo` is bridge scaffolding only**: it starts the `backend/ros`
  ROSBridge (rclpy connectivity beside the container) but the fleet loop still
  drives headless `SimulationRobotAdapter` robots. Wiring `GazeboRobotAdapter`
  (+ its ROS 2 transport) into `FleetAppState` so the orchestrator consumes
  Gazebo telemetry is the documented Phase 2 follow-up.
- **Nav2/AMCL path planning** is not wired yet: MVP navigation is the
  `fleet_agent` go-to-goal controller (obstacle-stop + rotate recovery). The
  Nav2 stack (amcl/costmap/planner/controller) + `map_server` with a
  warehouse occupancy map is the documented Phase 2 follow-up.
- **Bridge topic names** (`/model/{ns}/odom`, `/model/{ns}/lidar/scan`,
  `/model/{ns}/tf`) follow the ros_gz_bridge demos and carry
  `TODO: verify` markers — they must be confirmed against a running gz-sim
  instance on the first Phase 1 run.
- **Battery** in Gazebo is a modeled estimate published by `fleet_agent`
  (no battery sensor on the AMR yet); it idle-drains while obstacle-blocked.
- **Lifecycle-managed nodes** (SYSTEM_PROMPT.md §2.4) are a follow-up;
  `fleet_agent` is a plain node for Phase 1.
- **Failure injection in Gazebo** (shutdown / comm loss / sensor degradation /
  nav freeze) is designed into `GazeboRobotAdapter`; the Gazebo-side sim
  failure simulation (Phase 5 §docs/robustness.md) remains STUB.
- **Dockerfiles** for backend / frontend / validator services are still TODO
  (compose `build` targets them; CI builds only `gazebo` until then).
