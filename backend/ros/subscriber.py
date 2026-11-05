"""Subscriber helpers — typed ROS 2 subscriptions for robot telemetry (Phase 1).

These factories convert ROS 2 messages into plain dicts that the backend
event bus understands. They are only callable when the ROSBridge is running
(SIM_MODE=gazebo); the import of ROS message types happens lazily so this
module loads cleanly in a headless environment.
"""

from __future__ import annotations

from typing import Any

from backend.ros.bridge import EventCallback, ROSBridge


def subscribe_robot_odometry(bridge: ROSBridge, namespace: str, callback: EventCallback) -> bool:
    """Subscribe to /{namespace}/odom; callback receives a dict with x, y, yaw."""
    if not bridge.is_running:
        return False
    from nav_msgs.msg import Odometry

    def _wrap(msg: Any) -> None:
        q = msg.pose.pose.orientation
        callback(
            {
                "x": msg.pose.pose.position.x,
                "y": msg.pose.pose.position.y,
                "yaw": _quaternion_to_yaw(q.w, q.x, q.y, q.z),
            }
        )

    return bridge.subscribe(f"/{namespace}/odom", Odometry, _wrap)


def subscribe_robot_scan(bridge: ROSBridge, namespace: str, callback: EventCallback) -> bool:
    """Subscribe to /{namespace}/scan; callback receives a dict with ranges."""
    if not bridge.is_running:
        return False
    from sensor_msgs.msg import LaserScan

    def _wrap(msg: Any) -> None:
        callback({"ranges": list(msg.ranges)})

    return bridge.subscribe(f"/{namespace}/scan", LaserScan, _wrap)


def subscribe_robot_battery(bridge: ROSBridge, namespace: str, callback: EventCallback) -> bool:
    """Subscribe to /{namespace}/battery; callback receives a dict with battery_pct."""
    if not bridge.is_running:
        return False
    from std_msgs.msg import Float32

    def _wrap(msg: Any) -> None:
        callback({"battery_pct": float(msg.data)})

    return bridge.subscribe(f"/{namespace}/battery", Float32, _wrap)


def _quaternion_to_yaw(w: float, x: float, y: float, z: float) -> float:
    """Convert a quaternion to a yaw angle (radians, odom frame)."""
    import math

    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
