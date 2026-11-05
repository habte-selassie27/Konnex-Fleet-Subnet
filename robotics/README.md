# robotics/

Hardware-abstraction layer between the fleet orchestrator and the robot (simulation or physical).

| Path | Contents (planned) |
|---|---|
| `adapters/base.py` | `RobotAdapter` Protocol: `move / stop / get_state / get_battery / get_sensors` (SYSTEM_PROMPT §3.2) |
| `adapters/simulation.py` | `SimulationRobotAdapter` — wraps Gazebo (Phase 1) |
| `adapters/physical.py` | `PhysicalRobotAdapter` — STUB (Phase 8+) |
| `perception/lidar_processor.py` | LiDAR scan processing |
| `localization/amcl_interface.py` | AMCL wrapper |
| `navigation/nav2_interface.py` · `path_planner.py` | Nav2 integration |
| `models/` | `RobotState`, `Task`, `FleetState`, `SensorFrame` dataclasses |
| `battery/battery_model.py` | Linear drain + task cost (0.1/s moving, 0.02/s idle) |

**Status: STUB — placeholders pending Phase 1.**
