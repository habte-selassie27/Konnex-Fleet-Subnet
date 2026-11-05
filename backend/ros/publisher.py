"""Publisher helpers — typed ROS 2 publishers for robot commands (Phase 1).

Like subscriber.py, these load ROS message types lazily so the module works
in a headless environment; publishing only succeeds when the ROSBridge is
running (SIM_MODE=gazebo).
"""

from __future__ import annotations

from backend.ros.bridge import ROSBridge


def publish_goal(bridge: ROSBridge, namespace: str, x: float, y: float) -> bool:
    """Publish a PoseStamped goal on /{namespace}/goal_pose."""
    if not bridge.is_running:
        return False
    from geometry_msgs.msg import PoseStamped

    msg = PoseStamped()
    msg.header.frame_id = f"{namespace}/odom"
    msg.pose.position.x = x
    msg.pose.position.y = y
    msg.pose.orientation.w = 1.0
    return bridge.publish(f"/{namespace}/goal_pose", PoseStamped, msg)


def publish_cmd_vel(bridge: ROSBridge, namespace: str, linear: float, angular: float) -> bool:
    """Publish a Twist on /{namespace}/cmd_vel."""
    if not bridge.is_running:
        return False
    from geometry_msgs.msg import Twist

    msg = Twist()
    msg.linear.x = linear
    msg.angular.z = angular
    return bridge.publish(f"/{namespace}/cmd_vel", Twist, msg)
