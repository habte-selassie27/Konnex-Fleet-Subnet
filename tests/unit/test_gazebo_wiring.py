"""Tests for the Gazebo → fleet-loop wiring (no rclpy required).

`RosGazeboTransport` is transport-injected like the adapter, so the live data
path (odom/scan/battery in, goal/cmd_vel out) is verified against a fake bridge
and fake ROS message classes.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from backend.config import Settings
from backend.ros.gazebo_transport import RosGazeboTransport, RosMessageTypes
from backend.services.fleet_service import FleetAppState
from robotics.adapters.gazebo import GazeboRobotAdapter
from robotics.models.robot_state import NavState, Vector2D
from robotics.models.task import Task


class _FakeBridge:
    """Minimal ROSBridge stand-in."""

    is_running = True

    def __init__(self) -> None:
        self.subscriptions: dict[str, Any] = {}
        self.published: list[tuple[str, Any]] = []

    def subscribe(self, topic: str, _msg_type: Any, callback: Any) -> bool:
        self.subscriptions[topic] = callback
        return True

    def publish(self, topic: str, _msg_type: Any, payload: Any) -> bool:
        self.published.append((topic, payload))
        return True


class _Odometry:
    def __init__(self) -> None:
        self.pose = SimpleNamespace(
            pose=SimpleNamespace(
                position=SimpleNamespace(x=0.0, y=0.0),
                orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0),
            )
        )


class _LaserScan:
    def __init__(self) -> None:
        self.ranges: list[float] = []


class _Float32:
    def __init__(self) -> None:
        self.data = 0.0


class _PoseStamped:
    def __init__(self) -> None:
        self.header = SimpleNamespace(frame_id="", stamp=None)
        self.pose = SimpleNamespace(
            position=SimpleNamespace(x=0.0, y=0.0),
            orientation=SimpleNamespace(w=0.0),
        )


class _Twist:
    def __init__(self) -> None:
        self.linear = SimpleNamespace(x=0.0)
        self.angular = SimpleNamespace(z=0.0)


def _msgs() -> RosMessageTypes:
    return RosMessageTypes(
        odometry=_Odometry,
        laser_scan=_LaserScan,
        float32=_Float32,
        pose_stamped=_PoseStamped,
        twist=_Twist,
    )


def _transport(bridge: _FakeBridge) -> RosGazeboTransport:
    return RosGazeboTransport("robot_0", bridge, msgs=_msgs())


def test_attach_subscribes_to_all_telemetry_topics() -> None:
    bridge = _FakeBridge()
    transport = _transport(bridge)

    assert transport.attach() is True
    assert set(bridge.subscriptions) == {
        "/robot_0/odom",
        "/robot_0/scan",
        "/robot_0/battery",
    }
    assert transport.is_connected()


def test_odometry_scan_and_battery_reach_the_adapter() -> None:
    bridge = _FakeBridge()
    transport = _transport(bridge)
    transport.attach()

    odom = _Odometry()
    odom.pose.pose.position.x = 3.0
    odom.pose.pose.position.y = 4.0
    bridge.subscriptions["/robot_0/odom"]({"msg": odom})

    scan = _LaserScan()
    scan.ranges = [1.5, 2.5]
    bridge.subscriptions["/robot_0/scan"]({"msg": scan})

    battery = _Float32()
    battery.data = 0.42
    bridge.subscriptions["/robot_0/battery"]({"msg": battery})

    adapter = GazeboRobotAdapter("robot_0", transport)
    state = adapter.get_state()

    assert state.position.x == pytest.approx(3.0)
    assert state.position.y == pytest.approx(4.0)
    assert state.battery_pct == pytest.approx(0.42)
    assert transport.latest_scan() is not None
    assert transport.latest_scan().ranges == (1.5, 2.5)  # type: ignore[union-attr]


def test_assign_task_publishes_a_goal_on_the_robot_topic() -> None:
    bridge = _FakeBridge()
    transport = _transport(bridge)
    transport.attach()

    odom = _Odometry()
    bridge.subscriptions["/robot_0/odom"]({"msg": odom})

    adapter = GazeboRobotAdapter("robot_0", transport)
    task = Task(id="task_001", pickup=Vector2D(5.0, 5.0), delivery=Vector2D(8.0, 9.0))

    assert adapter.assign_task(task) is True
    topic, message = bridge.published[-1]
    assert topic == "/robot_0/goal"
    assert message.header.frame_id == "odom"
    assert message.pose.position.x == pytest.approx(5.0)
    assert message.pose.position.y == pytest.approx(5.0)


def test_stop_publishes_zero_velocity() -> None:
    bridge = _FakeBridge()
    transport = _transport(bridge)
    transport.attach()

    transport.publish_velocity(
        __import__("robotics.adapters.gazebo", fromlist=["TwistCommand"]).TwistCommand(0.0, 0.0)
    )

    topic, message = bridge.published[-1]
    assert topic == "/robot_0/cmd_vel"
    assert message.linear.x == 0.0


def test_transport_without_ros_is_not_connected() -> None:
    bridge = _FakeBridge()
    transport = RosGazeboTransport("robot_0", bridge, msgs=None)

    # No ROS 2 message types on this host -> attach must fail loudly, not fake.
    assert transport.attach() is False
    assert transport.is_connected() is False


def test_fleet_state_falls_back_to_headless_without_ros(tmp_path: Any) -> None:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/wiring.db",
        artifact_dir=tmp_path / "artifacts",
        sim_mode="gazebo",
    )
    fleet = FleetAppState(settings, ros_bridge=_FakeBridge())

    # A bridge is attached, but no ROS message types exist, so no robot can be
    # Gazebo-backed: sim_backend must report headless rather than claim Gazebo.
    assert fleet.sim_backend == "headless"


def test_gazebo_adapter_reports_failed_nav_state_after_injection() -> None:
    from robotics.models.failure import FailureType

    bridge = _FakeBridge()
    transport = _transport(bridge)
    transport.attach()
    adapter = GazeboRobotAdapter("robot_0", transport)
    adapter.inject_failure(FailureType.NAVIGATION_FAILURE)

    assert adapter.get_state().nav_state == NavState.FAILED
