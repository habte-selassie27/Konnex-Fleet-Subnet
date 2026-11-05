# Robotics — Simulation & Hardware Abstraction

> **Status: COMPLETE (Phase 1 wiring)** — headless adapter (COMPLETE, Phase 5),
> Gazebo adapter + backend ROS bridge (COMPLETE wiring, live Gazebo run NOT
> RUN on this machine), physical adapter STUB. See docs/simulation.md.

## Robot Model (BUILD.md §4)

Differential-drive AMR: chassis 0.5×0.5×0.25 m, 20 kg · wheelbase 0.4 m ·
v_max 1.0 m/s · ω_max 1.5 rad/s · LiDAR 360° @ 10 m, 10 Hz · IMU 100 Hz ·
odometry 50 Hz · battery 100 units (0.1/s moving, 0.02/s idle).

## Abstraction

`RobotAdapter` Protocol (`robotics/adapters/base.py`):

```python
class RobotAdapter(Protocol):
    def get_state(self) -> RobotState: ...
    def get_battery(self) -> float: ...
    def get_sensors(self) -> SensorFrame | None: ...
    def stop(self) -> None: ...
    def assign_task(self, task: Task) -> bool: ...
    def tick(self, dt: float) -> None: ...
    def inject_failure(self, failure_type: FailureType, duration_s: float | None = None) -> None: ...
    def clear_failure(self) -> None: ...
    def set_hold(self, hold: bool) -> None: ...
    def take_completed_task(self) -> str | None: ...
    def go_charge(self) -> str | None: ...
    @property
    def energy_consumed_units(self) -> float: ...
```

| Adapter | File | Status |
|---|---|---|
| Headless (deterministic, in-process) | `robotics/adapters/simulation.py` | COMPLETE (Phase 5) — used by orchestrator / benchmarks / validator |
| Gazebo (physics + sensors) | `robotics/adapters/gazebo.py` | COMPLETE wiring (Phase 1) — transport-injected, rclpy-guarded; live run NOT RUN here |
| Physical hardware | `robotics/adapters/physical.py` | STUB (post-MVP / Mainnet tier) |

All adapters implement the same protocol — the orchestrator and policies never
know which one they talk to (SYSTEM_PROMPT.md §3.2).

## ROS 2 Notes

- Humble LTS; launch files in Python format.
- ROS 2 imports exist **only** in `backend/ros/` and `robotics/adapters/gazebo.py` — nothing else imports `rclpy`.
- Multi-robot launch: `/robot_0 … /robot_{N-1}` namespaces, each with a
  `fleet_agent` go-to-goal node (LiDAR obstacle avoidance + modeled battery)
  bridged to gz-sim via `ros_gz_bridge` (see `simulation/launch/` and
  docs/simulation.md).

## Nav2 (follow-up)

The full Nav2 stack (amcl + costmap + planner + controller + lifecycle
manager) plus `map_server` with a warehouse occupancy map is the documented
Phase 2 follow-up. MVP navigation is the `fleet_agent` controller, which
stops before obstacles and rotates in place to recover when the forward
sector is blocked — sufficient for the Phase 1 gate but not shelf-avoiding
path planning.
