"""Multi-robot launch — Phase 1.

Status: COMPLETE (Phase 1 wiring).

Starts the warehouse world (warehouse.launch.py) and spawns N robots in unique
namespaces /robot_0 ... /robot_{N-1}, each with:

  - robot_state_publisher (URDF processed via xacro)
  - fleet_agent navigation node (go-to-goal + LiDAR obstacle avoidance)
  - a gz -> ROS topic bridge entry for odom / scan / imu / cmd_vel / tf

Robots are spawned into Gazebo Harmonic via `ros_gz_sim create` at
deterministic positions derived from a seed (mirrors ScenarioGenerator's
contract: same seed => same positions, >= 1.5 m apart, inside world bounds).

NOTE: robot_count and seed are resolved at launch-parse time (Python
constants) so the bridge config can be generated to match. Change the
defaults in this file, not via launch arguments.

Nav2/AMCL path planning is a documented follow-up (docs/robotics.md §Nav2);
MVP navigation is the fleet_agent controller.

Python launch format required (AGENTS.md §4.10).
"""

import random
from pathlib import Path
from tempfile import gettempdir

import yaml
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

# ─── Parse-time configuration (see docstring) ───────────────────────────────
WORLD_NAME = "warehouse_v1"  # must match <world name> in warehouse_v1.sdf
DEFAULT_ROBOT_COUNT = 5
DEFAULT_SEED = 42
WORLD_SIZE = (40.0, 30.0)
MIN_ROBOT_SPACING_M = 1.5
WORLD_MARGIN_M = 1.0
SPAWN_Z = 0.125  # wheel bottom sits at base_link_z - 0.125; this puts it on the floor


def _spawn_positions(count: int, seed: int) -> list[tuple[float, float]]:
    """Deterministic robot spawn positions (mirrors ScenarioGenerator)."""
    rng = random.Random(seed)
    positions: list[tuple[float, float]] = []
    for _ in range(count):
        for _attempt in range(200):
            x = rng.uniform(WORLD_MARGIN_M, WORLD_SIZE[0] - WORLD_MARGIN_M)
            y = rng.uniform(WORLD_MARGIN_M, WORLD_SIZE[1] - WORLD_MARGIN_M)
            if all((x - px) ** 2 + (y - py) ** 2 >= MIN_ROBOT_SPACING_M**2 for px, py in positions):
                positions.append((x, y))
                break
        else:  # pragma: no cover -- world is large enough for realistic counts
            positions.append((WORLD_MARGIN_M, WORLD_MARGIN_M))
    return positions


def _bridge_config_yaml(robot_count: int) -> str:
    """Generate the ros_gz_bridge parameter_bridge config for N robots.

    gz topic names are VERIFIED against a running Gazebo Harmonic 8.15
    instance (Phase 1, `gz topic -l`), not assumed:

      - DiffDrive publishes odometry on /model/{ns}/odometry (gz default;
        /odom does not exist, so bridging /odom silently carried no data).
      - A sensor's <topic> is used LITERALLY, so omitting it yields the
        model-scoped default
        /world/{world}/model/{ns}/link/base_link/sensor/{sensor}/<type>.
        Fixed-joint lumping puts both sensors on base_link.
      - DiffDrive publishes odom->base_link on /model/{ns}/tf.
    """
    entries: list[dict[str, str]] = [
        {
            "ros_topic_name": "/clock",
            "gz_topic_name": "/clock",
            "ros_type_name": "rosgraph_msgs/msg/Clock",
            "gz_type_name": "gz.msgs.Clock",
            "direction": "GZ_TO_ROS",
        }
    ]
    for index in range(robot_count):
        ns = f"robot_{index}"
        entries.extend(
            [
                {
                    "ros_topic_name": f"/{ns}/odom",
                    "gz_topic_name": f"/model/{ns}/odometry",
                    "ros_type_name": "nav_msgs/msg/Odometry",
                    "gz_type_name": "gz.msgs.Odometry",
                    "direction": "GZ_TO_ROS",
                },
                {
                    "ros_topic_name": f"/{ns}/cmd_vel",
                    "gz_topic_name": f"/model/{ns}/cmd_vel",
                    "ros_type_name": "geometry_msgs/msg/Twist",
                    "gz_type_name": "gz.msgs.Twist",
                    "direction": "ROS_TO_GZ",
                },
                {
                    "ros_topic_name": f"/{ns}/scan",
                    "gz_topic_name": (
                        f"/world/{WORLD_NAME}/model/{ns}/link/base_link/sensor/lidar/scan"
                    ),
                    "ros_type_name": "sensor_msgs/msg/LaserScan",
                    "gz_type_name": "gz.msgs.LaserScan",
                    "direction": "GZ_TO_ROS",
                },
                {
                    "ros_topic_name": f"/{ns}/imu",
                    "gz_topic_name": (
                        f"/world/{WORLD_NAME}/model/{ns}/link/base_link/sensor/imu/imu"
                    ),
                    "ros_type_name": "sensor_msgs/msg/Imu",
                    "gz_type_name": "gz.msgs.IMU",
                    "direction": "GZ_TO_ROS",
                },
                # odom -> base_link transform from the gz diff-drive plugin.
                {
                    "ros_topic_name": f"/{ns}/tf",
                    "gz_topic_name": f"/model/{ns}/tf",
                    "ros_type_name": "tf2_msgs/msg/TFMessage",
                    "gz_type_name": "gz.msgs.Pose_V",
                    "direction": "GZ_TO_ROS",
                },
            ]
        )
    dump = yaml.safe_dump(entries)
    assert isinstance(dump, str)
    return dump


def _write_bridge_config(robot_count: int) -> Path:
    """Persist the generated bridge config; returns its path."""
    path = Path(gettempdir()) / "fleet_robot_bridge.yaml"
    path.write_text(_bridge_config_yaml(robot_count), encoding="utf-8")
    return path


def generate_launch_description() -> LaunchDescription:
    """Launch warehouse world + N robots + gz->ROS bridge."""
    robot_count = DEFAULT_ROBOT_COUNT
    seed = DEFAULT_SEED
    positions = _spawn_positions(robot_count, seed)

    xacro_path = PathJoinSubstitution(
        [FindPackageShare("simulation"), "robots", "amr_model.urdf.xacro"]
    )
    # ParameterValue(str) is required: the xacro output is raw XML that launch
    # cannot parse as YAML when passed directly as a parameter value.
    robot_description = ParameterValue(Command(["xacro ", xacro_path]), value_type=str)
    bridge_config = _write_bridge_config(robot_count)

    warehouse = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare("simulation"), "launch", "warehouse.launch.py"])
        )
    )

    actions: list[object] = [warehouse]

    for index in range(robot_count):
        ns = f"robot_{index}"
        x, y = positions[index]

        actions.append(
            Node(
                package="ros_gz_sim",
                executable="create",
                name=f"spawn_{ns}",
                output="screen",
                arguments=[
                    "-name",
                    ns,
                    "-param",
                    "robot_description",
                    "-x",
                    str(x),
                    "-y",
                    str(y),
                    "-z",
                    str(SPAWN_Z),
                    "-Y",
                    "0.0",
                ],
                parameters=[{"robot_description": robot_description}],
            )
        )
        actions.append(
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                name="robot_state_publisher",
                output="screen",
                namespace=ns,
                parameters=[{"robot_description": robot_description, "use_sim_time": True}],
            )
        )
        actions.append(
            Node(
                package="simulation",
                executable="fleet_agent.py",
                name="fleet_agent",
                output="screen",
                namespace=ns,
                parameters=[{"use_sim_time": True}],
            )
        )

    actions.append(
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="gz_ros_bridge",
            output="screen",
            parameters=[{"config_file": str(bridge_config)}],
        )
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "robot_count",
                default_value=str(robot_count),
                description="Number of robots (parse-time; edit this file to change)",
            ),
            DeclareLaunchArgument(
                "seed",
                default_value=str(seed),
                description="Spawn-position seed (parse-time; edit this file to change)",
            ),
            *actions,
        ]
    )
