"""Warehouse world launch — Phase 1.

Status: COMPLETE (Phase 1 wiring).
Launches Gazebo Harmonic (gz-sim) with simulation/worlds/warehouse_v1.sdf
via the ros_gz_sim launcher.

Python launch format required (AGENTS.md §4.10).
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    """Launch Gazebo Harmonic with the warehouse world."""
    world_file = PathJoinSubstitution(
        [FindPackageShare("simulation"), "worlds", "warehouse_v1.sdf"]
    )

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare("ros_gz_sim"), "launch", "gz_sim.launch.py"])
        ),
        launch_arguments={
            # gz_sim.launch.py only reads `gz_args` — it has NO `world` argument
            # (verified against the installed ros_gz_sim source), so the world
            # path MUST be passed inside gz_args or gz loads the default empty
            # world (no floor -> robots free-fall).
            # -s (server only): the combined gz sim (server+GUI) would otherwise
            #   abort on the Qt GUI with no display available.
            # --headless-rendering: no window server on CI / headless run boxes.
            # A list of substitutions IS the concatenation (`gz_sim.launch.py`
            # calls `LaunchConfiguration('gz_args').perform(context)`, which
            # joins a list into one string). `TextSubstitution + PathJoinSubstitution`
            # raises "unsupported operand type(s) for +" — verified by execution.
            "gz_args": ["-s -r -v4 --headless-rendering ", world_file],
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "world",
                default_value=world_file,
                description="Path to SDF world file",
            ),
            gz_sim,
        ]
    )
