#!/usr/bin/env python3
"""fleet_agent — per-robot go-to-goal navigation node (Phase 1 MVP).

Runs once per robot inside its namespace (/robot_0, /robot_1, ...):

  Subscribes:  /goal_pose  (geometry_msgs/PoseStamped)  goal in odom frame
               /odom       (nav_msgs/Odometry)          current pose
               /scan       (sensor_msgs/LaserScan)      obstacle ranges
  Publishes:   /cmd_vel    (geometry_msgs/Twist)        drive command
               /battery    (std_msgs/Float32)           modeled drain

Behavior (MVP, Nav2-free):
  - proportional heading controller toward the current goal;
  - if any LiDAR range in the forward sector (min_range within +/-30 deg)
    drops below 0.5 m for STUCK_TIMEOUT_S, rotate in place to recover;
  - battery drains 0.1 u/s while moving, 0.02 u/s while idle (BUILD.md §4)
    and is published as a modeled estimate — there is no battery sensor in
    the Phase 1 AMR.

This is intentionally a plain rclpy.Node for Phase 1; lifecycle-managed
nodes (SYSTEM_PROMPT.md §2.4) are a documented follow-up in docs/robotics.md.
"""

import math

import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Float32

CONTROL_HZ = 10
MAX_LINEAR = 1.0  # m/s  (BUILD.md §4)
MAX_ANGULAR = 1.5  # rad/s
GOAL_TOLERANCE_M = 0.3
OBSTACLE_STOP_M = 0.5
FORWARD_SECTOR_DEG = 30.0
STUCK_TIMEOUT_S = 3.0
BATTERY_CAPACITY_UNITS = 100.0
BATTERY_DRAIN_MOVING = 0.1  # units/s
BATTERY_DRAIN_IDLE = 0.02  # units/s


class FleetAgent(Node):  # type: ignore[misc]  # rclpy is Any here (container-only dep)
    """Go-to-goal controller with LiDAR obstacle avoidance and battery model."""

    def __init__(self) -> None:
        super().__init__("fleet_agent")
        # `use_sim_time` is pre-declared when the launch passes it via the
        # params file — only declare here when running standalone (ros2 run).
        if not self.has_parameter("use_sim_time"):
            self.declare_parameter("use_sim_time", True)

        self._goal: tuple[float, float] | None = None
        self._pose: tuple[float, float, float] | None = None  # x, y, yaw (odom)
        self._ranges: list[float] = []
        self._battery_units = BATTERY_CAPACITY_UNITS
        self._last_control = self.get_clock().now().nanoseconds / 1e9
        self._stuck_since: float | None = None

        self._goal_sub = self.create_subscription(PoseStamped, "goal_pose", self._on_goal, 1)
        self._odom_sub = self.create_subscription(Odometry, "odom", self._on_odom, 1)
        self._scan_sub = self.create_subscription(LaserScan, "scan", self._on_scan, 1)
        self._cmd_pub = self.create_publisher(Twist, "cmd_vel", 1)
        self._battery_pub = self.create_publisher(Float32, "battery", 1)
        self.create_timer(1.0 / CONTROL_HZ, self._control_loop)

    # ── ROS callbacks ──────────────────────────────────────────────────────
    def _on_goal(self, msg: PoseStamped) -> None:
        self._goal = (msg.pose.position.x, msg.pose.position.y)
        self.get_logger().info(
            f"new goal: ({msg.pose.position.x:.2f}, {msg.pose.position.y:.2f})",
            throttle_duration_sec=1.0,
        )

    def _on_odom(self, msg: Odometry) -> None:
        q = msg.pose.pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        self._pose = (msg.pose.pose.position.x, msg.pose.pose.position.y, yaw)

    def _on_scan(self, msg: LaserScan) -> None:
        self._ranges = list(msg.ranges)

    # ── Control loop ───────────────────────────────────────────────────────
    def _control_loop(self) -> None:
        now = self.get_clock().now().nanoseconds / 1e9
        dt = max(0.0, now - self._last_control)
        self._last_control = now

        twist = self._compute_twist(now)
        self._update_battery(dt, moving=twist.linear.x > 0.0 or abs(twist.angular.z) > 0.0)
        self._cmd_pub.publish(twist)

    def _compute_twist(self, now: float) -> Twist:
        """Proportional heading control with LiDAR stop + rotate recovery."""
        twist = Twist()
        if self._goal is None or self._pose is None:
            return twist

        gx, gy = self._goal
        x, y, yaw = self._pose
        dx, dy = gx - x, gy - y
        distance = math.hypot(dx, dy)

        if distance <= GOAL_TOLERANCE_M:
            self._goal = None
            self._stuck_since = None
            return twist

        if self._forward_blocked():
            if self._stuck_since is None:
                self._stuck_since = now
            if now - self._stuck_since >= STUCK_TIMEOUT_S:
                # Rotate in place to find a free direction.
                twist.angular.z = MAX_ANGULAR * 0.6
            return twist

        self._stuck_since = None
        goal_angle = math.atan2(dy, dx)
        angle_error = _wrap_pi(goal_angle - yaw)
        twist.linear.x = max(0.0, min(MAX_LINEAR, distance))
        twist.angular.z = _clamp(1.5 * angle_error, -MAX_ANGULAR, MAX_ANGULAR)
        return twist

    def _forward_blocked(self) -> bool:
        """True when any range in the forward sector is below the stop distance."""
        if not self._ranges:
            return False
        sector = math.radians(FORWARD_SECTOR_DEG)
        n = len(self._ranges)
        for i, r in enumerate(self._ranges):
            if not math.isfinite(r) or r <= 0.0:
                continue
            angle = (i / n) * 2.0 * math.pi - math.pi
            if abs(angle) <= sector and r < OBSTACLE_STOP_M:
                return True
        return False

    def _update_battery(self, dt: float, moving: bool) -> None:
        """Drain the modeled battery; publish the estimate.

        Drains at the moving rate only while a motion command is actually
        issued (blocked robots idle-drain).
        """
        rate = BATTERY_DRAIN_MOVING if moving else BATTERY_DRAIN_IDLE
        self._battery_units = max(0.0, self._battery_units - rate * dt)
        msg = Float32()
        msg.data = self._battery_units / BATTERY_CAPACITY_UNITS
        self._battery_pub.publish(msg)


def _wrap_pi(angle: float) -> float:
    """Wrap an angle to [-pi, pi]."""
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp value into [low, high]."""
    return max(low, min(high, value))


def main(args: list[str] | None = None) -> None:
    """ROS 2 entrypoint."""
    rclpy.init(args=args)
    node = FleetAgent()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:  # pragma: no cover - interactive shutdown
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
