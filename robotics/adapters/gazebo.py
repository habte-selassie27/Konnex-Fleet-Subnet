"""GazeboRobotAdapter — RobotAdapter implementation backed by Gazebo (Phase 1).

Implements the same RobotAdapter Protocol as the headless
SimulationRobotAdapter so the orchestrator and policies are simulator-agnostic
(SYSTEM_PROMPT.md §3.2, docs/robotics.md).

Architecture:
  - The adapter is transport-injected: it talks to a `Transport` (PoseGoal in,
    TwistCommand out, OdometrySample/ScanSample/battery in). Unit tests inject
    a fake transport; the ROS 2 transport (bridging to the fleet_agent node
    topics) is provided by backend/ros/ — wiring it into FleetAppState is the
    documented Phase 2 follow-up.
  - High-level control: the adapter publishes PoseGoal messages to the
    fleet_agent node, which handles low-level go-to-goal + LiDAR avoidance.
  - Failure injection: COMMUNICATION_LOSS / SHUTDOWN stop command emission and
    mark the robot OFFLINE; NAVIGATION_FAILURE marks NAV_STATE FAILED.

Status: COMPLETE (Phase 1 wiring) — live Gazebo execution NOT RUN on this
machine (rclpy/Gazebo are containerized; see docs/requirements.md).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from robotics.models.failure import FailureType
from robotics.models.robot_state import CommState, NavState, RobotState, Vector2D
from robotics.models.sensor_frame import SensorFrame
from robotics.models.task import Task

REACH_THRESHOLD_M = 0.3
BATTERY_CAPACITY_UNITS = 100.0


# ─── Transport messages (ROS-agnostic) ───────────────────────────────────────
@dataclass(frozen=True)
class OdometrySample:
    """Latest odometry snapshot in the world/odom frame."""

    x: float
    y: float
    yaw: float
    timestamp: float


@dataclass(frozen=True)
class ScanSample:
    """Latest LiDAR scan."""

    ranges: tuple[float, ...]
    timestamp: float


@dataclass(frozen=True)
class TwistCommand:
    """Low-level velocity command."""

    linear_x: float
    angular_z: float


@dataclass(frozen=True)
class PoseGoal:
    """High-level goal for the fleet_agent node (odom frame)."""

    x: float
    y: float


class Transport(Protocol):
    """The robot I/O surface the adapter depends on."""

    def is_connected(self) -> bool: ...

    def publish_goal(self, goal: PoseGoal) -> None: ...

    def publish_velocity(self, twist: TwistCommand) -> None: ...

    def latest_odometry(self) -> OdometrySample | None: ...

    def latest_scan(self) -> ScanSample | None: ...

    def latest_battery(self) -> float | None: ...


class GazeboRobotAdapter:
    """Fleet-facing adapter for a Gazebo robot (Phase 1)."""

    MAX_LINEAR_VELOCITY = 1.0

    def __init__(
        self,
        robot_id: str,
        transport: Transport,
        charging_station: Vector2D | None = None,
    ) -> None:
        self._id = robot_id
        self._transport = transport
        self._charging_station = charging_station or Vector2D(2.0, 2.0)
        self._task: Task | None = None
        self._task_phase = "pickup"
        self._completed_task_id: str | None = None
        self._failure: FailureType | None = None
        self._nav_state = NavState.IDLE
        self._clock = 0.0

    @property
    def robot_id(self) -> str:
        """Stable robot identifier."""
        return self._id

    # ── RobotAdapter Protocol ───────────────────────────────────────────────
    def get_state(self) -> RobotState:
        """Current robot state snapshot from latest telemetry."""
        sample = self._transport.latest_odometry()
        battery = self._transport.latest_battery()
        if sample is not None:
            position = Vector2D(sample.x, sample.y)
            orientation = sample.yaw
        else:
            position = Vector2D(0.0, 0.0)
            orientation = 0.0
        comm_state = (
            CommState.OFFLINE
            if self._failure in (FailureType.COMMUNICATION_LOSS, FailureType.SHUTDOWN)
            else CommState.ONLINE
        )
        nav_state = (
            NavState.FAILED if self._failure == FailureType.NAVIGATION_FAILURE else self._nav_state
        )
        return RobotState(
            id=self._id,
            position=position,
            orientation=orientation,
            battery_pct=battery if battery is not None else 1.0,
            current_task_id=self._task.id if self._task else None,
            nav_state=nav_state,
            in_collision=False,
            comm_state=comm_state,
            timestamp=self._clock,
        )

    def get_battery(self) -> float:
        """Latest battery fraction, or 1.0 when no telemetry has arrived yet."""
        battery = self._transport.latest_battery()
        return 1.0 if battery is None else battery

    def get_sensors(self) -> SensorFrame | None:
        """Latest LiDAR frame, or None when no scan has arrived."""
        scan = self._transport.latest_scan()
        if scan is None:
            return None
        return SensorFrame(lidar_ranges=list(scan.ranges), timestamp=scan.timestamp)

    def stop(self) -> None:
        """Stop motion immediately and abandon the current task."""
        self._transport.publish_velocity(TwistCommand(0.0, 0.0))
        if self._nav_state != NavState.FAILED:
            self._nav_state = NavState.IDLE
        self._task = None
        self._task_phase = "pickup"

    def assign_task(self, task: Task) -> bool:
        """Publish the task pickup goal to the fleet_agent node."""
        if not self._transport.is_connected():
            return False
        if self._failure is not None:
            return False
        if self._task is not None:
            return False
        self._task = task
        self._task_phase = "pickup"
        self._nav_state = NavState.MOVING
        self._transport.publish_goal(PoseGoal(task.pickup.x, task.pickup.y))
        return True

    def set_hold(self, hold: bool) -> None:
        """Pause motion this tick (simple collision-avoidance handshake)."""
        if hold:
            self._transport.publish_velocity(TwistCommand(0.0, 0.0))

    def tick(self, dt: float) -> None:
        """Advance the adapter clock; Gazebo physics advances independently."""
        self._clock += dt
        if self._task is None:
            return
        sample = self._transport.latest_odometry()
        if sample is None:
            return
        if self._nav_state == NavState.CHARGING:
            return
        target = self._task.pickup if self._task_phase == "pickup" else self._task.delivery
        distance = math.hypot(sample.x - target.x, sample.y - target.y)
        if distance <= REACH_THRESHOLD_M:
            if self._task_phase == "pickup":
                self._task_phase = "delivery"
                self._transport.publish_goal(PoseGoal(self._task.delivery.x, self._task.delivery.y))
            else:
                self._completed_task_id = self._task.id
                self._task = None
                self._task_phase = "pickup"
                self._nav_state = NavState.IDLE
                self._transport.publish_velocity(TwistCommand(0.0, 0.0))

    def take_completed_task(self) -> str | None:
        """Return and clear the id of a task completed since the last call."""
        completed = self._completed_task_id
        self._completed_task_id = None
        return completed

    def inject_failure(self, failure_type: FailureType, duration_s: float | None = None) -> None:
        """Inject a failure; commands stop being emitted while failed."""
        del duration_s  # Gazebo failures are permanent until cleared (Phase 1)
        self._failure = failure_type
        if failure_type in (FailureType.COMMUNICATION_LOSS, FailureType.SHUTDOWN):
            self._transport.publish_velocity(TwistCommand(0.0, 0.0))
        self._task = None
        self._task_phase = "pickup"

    def clear_failure(self) -> None:
        """Clear any injected failure and restore nominal state."""
        self._failure = None

    def go_charge(self) -> str | None:
        """Send the robot to the charging station; returns the dropped task id."""
        dropped = self._task.id if self._task else None
        self._task = None
        self._task_phase = "pickup"
        self._nav_state = NavState.CHARGING
        self._transport.publish_goal(PoseGoal(self._charging_station.x, self._charging_station.y))
        return dropped

    @property
    def energy_consumed_units(self) -> float:
        """Battery units consumed (modeled from the battery topic)."""
        battery = self._transport.latest_battery()
        if battery is None:
            return 0.0
        return (1.0 - battery) * BATTERY_CAPACITY_UNITS
