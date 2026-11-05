# simulation/

Gazebo Harmonic simulation assets for the warehouse environment (Phase 1).

| Path | Contents |
|---|---|
| `Dockerfile.gazebo` | ROS 2 Humble + Gazebo Harmonic + ros_gz_bridge image (entrypoint: world + robots + bridge) |
| `package.xml` · `CMakeLists.txt` | ament package so `FindPackageShare("simulation")` resolves after colcon build |
| `worlds/warehouse_v1.sdf` | 40 m × 30 m warehouse: 15 shelf units (4×1×2 m), 5 pickup + 5 delivery zones, 2 charging stations, walls, lighting |
| `robots/amr_model.urdf.xacro` | Differential-drive AMR: 0.5×0.5×0.25 m chassis, 0.4 m wheelbase, v_max 1.0 m/s, LiDAR 360° @ 10 m, IMU 100 Hz |
| `robots/fleet_agent.py` | Per-robot go-to-goal node (LiDAR avoidance + modeled battery); installed via CMake as `simulation` program |
| `sensors/lidar.yaml` · `imu.yaml` | Sensor configuration (COMPLETE — matches the xacro sensors) |
| `scenarios/scenario_generator.py` | Deterministic seeded scenario generator — hard-coded scenarios prohibited |
| `launch/warehouse.launch.py` | World-only launch (ros_gz_sim / Gazebo Harmonic) |
| `launch/multi_robot.launch.py` | World + N robots (spawn via `ros_gz_sim create`, xacro URDF) + gz↔ROS bridge |
| `bridge/robot_bridge.yaml` | Reference gz↔ROS topic bridge config (5 robots) |

**Status: WIRING COMPLETE — live Gazebo execution NOT RUN on this machine**
(ROS 2 / Gazebo are containerized). Run `make sim` on a Gazebo-capable machine;
see docs/simulation.md.
