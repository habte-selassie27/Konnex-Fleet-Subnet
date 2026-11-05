"""ROS 2 transport for GazeboRobotAdapter (the Gazebo → fleet-loop bridge).

`GazeboRobotAdapter` is deliberately transport-agnostic; this module supplies
the live transport that reads Gazebo telemetry through the ROSBridge and writes
goals/velocity commands back to the per-robot `fleet_agent` node.

Topic contract (per robot, namespaced):

    subscribe  /{robot_id}/odom      nav_msgs/Odometry     -> pose, yaw
    subscribe  /{robot_id}/scan      sensor_msgs/LaserScan -> LiDAR ranges
    subscribe  /{robot_id}/battery   std_msgs/Float32      -> battery fraction
    publish    /{robot_id}/goal      geometry_msgs/PoseStamped  (fleet_agent)
    publish    /{robot_id}/cmd_vel   geometry_msgs/Twist        (stop/velocity)

The ROS message classes are imported lazily and injectable (`msgs=`), so this
module imports cleanly on a host with no ROS 2 and is testable without rclpy.
Nothing outside `backend/ros/` and `robotics/adapters/gazebo.py` imports ROS
types (AGENTS.md §4.10).

Status: COMPLETE wiring. Live execution requires the Gazebo container plus a
ROS-2-enabled backend (`docker compose --profile simulation up`); running the
host backend without rclpy leaves `is_connected()` False, so the fleet stays on
the headless adapter instead of pretending to have live data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import structlog

from robotics.adapters.gazebo import OdometrySample, PoseGoal, ScanSample, TwistCommand

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RosMessageTypes:
    """Message classes the transport needs (injectable for tests)."""

    odometry: Any
    laser_scan: Any
    float32: Any
    pose_stamped: Any
    twist: Any


def load_ros_message_types() -> RosMessageTypes | None:
    """Import ROS 2 message classes, or None when ROS is unavailable."""
    try:  # pragma: no cover - depends on the host having ROS 2
        from geometry_msgs.msg import PoseStamped, Twist
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import LaserScan
        from std_msgs.msg import Float32
    except ImportError:
        return None
    return RosMessageTypes(
        odometry=Odometry,
        laser_scan=LaserScan,
        float32=Float32,
        pose_stamped=PoseStamped,
        twist=Twist,
    )


class RosGazeboTransport:
    """`robotics.adapters.gazebo.Transport` backed by ROS 2 topics."""

    def __init__(
        self,
        robot_id: str,
        bridge: Any,
        *,
        msgs: RosMessageTypes | None = None,
    ) -> None:
        self._robot_id = robot_id
        self._bridge = bridge
        self._msgs = msgs if msgs is not None else load_ros_message_types()
        self._odometry: OdometrySample | None = None
        self._scan: ScanSample | None = None
        self._battery: float | None = None
        self._attached = False

    @property
    def robot_id(self) -> str:
        """Robot this transport is bound to."""
        return self._robot_id

    def attach(self) -> bool:
        """Subscribe to the robot's telemetry topics. False when ROS is absent."""
        if self._msgs is None:
            logger.warning("gazebo_transport_no_ros", robot=self._robot_id)
            return False
        bridge_running = getattr(self._bridge, "is_running", False)
        if not bridge_running:
            logger.warning("gazebo_transport_bridge_down", robot=self._robot_id)
            return False

        subscribed = all(
            [
                self._bridge.subscribe(
                    f"/{self._robot_id}/odom", self._msgs.odometry, self._on_odometry
                ),
                self._bridge.subscribe(
                    f"/{self._robot_id}/scan", self._msgs.laser_scan, self._on_scan
                ),
                self._bridge.subscribe(
                    f"/{self._robot_id}/battery", self._msgs.float32, self._on_battery
                ),
            ]
        )
        self._attached = subscribed
        logger.info("gazebo_transport_attached", robot=self._robot_id, ok=subscribed)
        return subscribed

    # ── Transport protocol ─────────────────────────────────────────────────
    def is_connected(self) -> bool:
        """True when the bridge is running and the subscriptions attached."""
        return self._attached and bool(getattr(self._bridge, "is_running", False))

    def publish_goal(self, goal: PoseGoal) -> None:
        """Send a high-level target to the robot's fleet_agent node."""
        if self._msgs is None or not self.is_connected():
            return
        message = self._msgs.pose_stamped()
        message.header.frame_id = "odom"
        stamp = getattr(self._bridge, "now", None)
        if callable(stamp):
            message.header.stamp = stamp()
        message.pose.position.x = goal.x
        message.pose.position.y = goal.y
        message.pose.orientation.w = 1.0
        self._bridge.publish(f"/{self._robot_id}/goal", self._msgs.pose_stamped, message)

    def publish_velocity(self, twist: TwistCommand) -> None:
        """Send a direct velocity command (used for stops)."""
        if self._msgs is None or not self.is_connected():
            return
        message = self._msgs.twist()
        message.linear.x = twist.linear_x
        message.angular.z = twist.angular_z
        self._bridge.publish(f"/{self._robot_id}/cmd_vel", self._msgs.twist, message)

    def latest_odometry(self) -> OdometrySample | None:
        """Most recent odometry sample, or None before the first message."""
        return self._odometry

    def latest_scan(self) -> ScanSample | None:
        """Most recent LiDAR scan, or None before the first message."""
        return self._scan

    def latest_battery(self) -> float | None:
        """Most recent battery fraction, or None before the first message."""
        return self._battery

    # ── Subscription callbacks ─────────────────────────────────────────────
    def _on_odometry(self, payload: dict[str, Any]) -> None:
        message = payload.get("msg")
        if message is None:
            logger.warning("gazebo_bad_odometry_event", robot=self._robot_id)
            return
        position = message.pose.pose.position
        orientation = message.pose.pose.orientation
        yaw = math.atan2(
            2.0 * (orientation.w * orientation.z + orientation.x * orientation.y),
            1.0 - 2.0 * (orientation.y**2 + orientation.z**2),
        )
        self._odometry = OdometrySample(
            x=float(position.x), y=float(position.y), yaw=yaw, timestamp=0.0
        )

    def _on_scan(self, payload: dict[str, Any]) -> None:
        message = payload.get("msg")
        if message is None:
            logger.warning("gazebo_bad_scan_event", robot=self._robot_id)
            return
        self._scan = ScanSample(ranges=tuple(float(r) for r in message.ranges), timestamp=0.0)

    def _on_battery(self, payload: dict[str, Any]) -> None:
        message = payload.get("msg")
        if message is None:
            logger.warning("gazebo_bad_battery_event", robot=self._robot_id)
            return
        self._battery = float(message.data)
