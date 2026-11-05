"""Unit tests for backend/ros (Phase 1).

On machines without rclpy (this machine — ROS 2 is containerized) the bridge
must import cleanly and be inert: is_available False, start() returns False,
subscribe/publish return False, stop() is a no-op.
"""

from backend.ros import bridge as bridge_module
from backend.ros.bridge import ROSBridge
from backend.ros.publisher import publish_cmd_vel, publish_goal
from backend.ros.subscriber import (
    subscribe_robot_battery,
    subscribe_robot_odometry,
    subscribe_robot_scan,
)


class TestROSBridgeInert:
    def test_imports_cleanly_without_rclpy(self) -> None:
        assert bridge_module.__name__ == "backend.ros.bridge"

    def test_is_available_matches_rclpy_presence(self) -> None:
        bridge = ROSBridge()
        assert bridge.is_available is bridge_module._HAS_RCLPY  # noqa: SLF001

    def test_start_returns_false_without_rclpy(self) -> None:
        bridge = ROSBridge()
        if not bridge_module._HAS_RCLPY:  # noqa: SLF001
            assert bridge.start() is False
            assert bridge.is_running is False

    def test_subscribe_publish_noop_when_not_running(self) -> None:
        bridge = ROSBridge()
        assert bridge.subscribe("/robot_0/odom", object, lambda _msg: None) is False
        assert bridge.publish("/robot_0/cmd_vel", object, object()) is False

    def test_stop_is_safe_when_never_started(self) -> None:
        ROSBridge().stop()  # must not raise

    def test_subscriber_helpers_bind_topic_names(self) -> None:
        # Helpers must fail gracefully on an inert bridge (no rclpy import
        # happens because the bridge is not running).
        bridge = ROSBridge()
        assert subscribe_robot_odometry(bridge, "robot_0", lambda _msg: None) is False
        assert subscribe_robot_scan(bridge, "robot_0", lambda _msg: None) is False
        assert subscribe_robot_battery(bridge, "robot_0", lambda _msg: None) is False

    def test_publisher_helpers_noop_on_inert_bridge(self) -> None:
        bridge = ROSBridge()
        assert publish_goal(bridge, "robot_0", 1.0, 2.0) is False
        assert publish_cmd_vel(bridge, "robot_0", 0.5, 0.0) is False
