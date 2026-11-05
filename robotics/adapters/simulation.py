"""SimulationRobotAdapter — deterministic headless robot simulation.

Status: COMPLETE (headless simulation, Phase 5).
The Gazebo-backed adapter wiring (BUILD.md §4) is STUB until Phase 1 simulation
integration; this headless adapter provides the deterministic robot behavior the
fleet orchestrator, robustness tests and the validator executor rely on.

Failure semantics (Phase 5):
- COMMUNICATION_LOSS  -> comm_state OFFLINE; stops accepting commands/motion
- NAVIGATION_FAILURE  -> nav_state FAILED; freezes in place
- SHUTDOWN            -> nav_state FAILED; comm_state OFFLINE
- BATTERY_CRITICAL    -> not injected here; orchestrator sends robot to charger
"""

import math

from robotics.battery.battery_model import BatteryModel
from robotics.models.failure import FailureType
from robotics.models.robot_state import CommState, NavState, RobotState, Vector2D
from robotics.models.sensor_frame import SensorFrame
from robotics.models.task import Task

REACH_THRESHOLD_M = 0.3


class SimulationRobotAdapter:
    """Headless differential-drive robot that moves toward its assigned task."""

    MAX_LINEAR_VELOCITY = 1.0  # m/s (BUILD.md §4)

    def __init__(
        self,
        robot_id: str,
        start_position: Vector2D | None = None,
        battery_pct: float = 1.0,
        charging_station: Vector2D | None = None,
    ) -> None:
        self._id = robot_id
        self._position = start_position or Vector2D(0.0, 0.0)
        self._orientation = 0.0
        self._battery = BatteryModel(initial_pct=battery_pct)
        self._charging_station = charging_station or Vector2D(2.0, 2.0)
        self._task: Task | None = None
        self._task_phase = "pickup"  # "pickup" -> "delivery"
        self._completed_task_id: str | None = None
        self._failure: FailureType | None = None
        self._failure_duration_s: float | None = None
        self._failure_elapsed: float = 0.0
        self._comm_state = CommState.ONLINE
        self._nav_state = NavState.IDLE
        self._hold = False
        self._distance_traveled = 0.0
        self._clock = 0.0

    @property
    def robot_id(self) -> str:
        """Stable robot identifier."""
        return self._id

    def get_state(self) -> RobotState:
        """Current robot state snapshot."""
        return RobotState(
            id=self._id,
            position=self._position,
            orientation=self._orientation,
            battery_pct=self._battery.charge_pct,
            current_task_id=self._task.id if self._task else None,
            nav_state=self._nav_state,
            in_collision=False,
            comm_state=self._comm_state,
            timestamp=self._clock,
            distance_traveled=self._distance_traveled,
        )

    def get_battery(self) -> float:
        """Current battery fraction in [0.0, 1.0]."""
        return self._battery.charge_pct

    def get_sensors(self) -> SensorFrame | None:
        """Latest sensor frame (headless: empty ranges)."""
        return SensorFrame(lidar_ranges=[], imu_yaw=self._orientation, timestamp=self._clock)

    def stop(self) -> None:
        """Stop all motion immediately and abandon the current task.

        The fleet calls this when a robot is taken out of service (failure
        recovery); leaving the task attached would create a zombie robot that
        holds a task it can never deliver. A FAILED nav state is preserved so
        the orchestrator does not re-assign work to a dead robot.
        """
        if self._nav_state != NavState.FAILED:
            self._nav_state = NavState.IDLE
        self._task = None
        self._task_phase = "pickup"

    def assign_task(self, task: Task) -> bool:
        """Accept a task. Returns False if the robot cannot accept commands."""
        if self._comm_state != CommState.ONLINE or self._nav_state == NavState.FAILED:
            return False
        if self._task is not None:
            return False
        self._task = task
        self._task_phase = "pickup"
        self._nav_state = NavState.MOVING
        return True

    def set_hold(self, hold: bool) -> None:
        """Pause motion this tick (simple collision-avoidance handshake)."""
        self._hold = hold

    def tick(self, dt: float) -> None:
        """Advance the simulation by dt seconds."""
        self._clock += dt
        if self._failure is not None:
            self._failure_elapsed += dt
            if (
                self._failure_duration_s is not None
                and self._failure_elapsed >= self._failure_duration_s
            ):
                self.clear_failure()

        if self._failure is not None:
            self._apply_failure_state()
            return

        self._comm_state = CommState.ONLINE

        if self._nav_state == NavState.CHARGING:
            self._charge(dt)
            return

        if self._task is not None:
            self._move_toward_task(dt)
        elif self._nav_state == NavState.MOVING:
            self._nav_state = NavState.IDLE

    def take_completed_task(self) -> str | None:
        """Return and clear the id of a task completed this tick."""
        completed = self._completed_task_id
        self._completed_task_id = None
        return completed

    def inject_failure(self, failure_type: FailureType, duration_s: float | None = None) -> None:
        """Inject a failure; duration_s None means permanent."""
        self._failure = failure_type
        self._failure_duration_s = duration_s
        self._failure_elapsed = 0.0
        self._apply_failure_state()

    def clear_failure(self) -> None:
        """Clear any injected failure and restore nominal state."""
        self._failure = None
        self._failure_duration_s = None
        self._failure_elapsed = 0.0
        self._comm_state = CommState.ONLINE
        if self._nav_state == NavState.FAILED:
            self._nav_state = NavState.IDLE

    def go_charge(self) -> str | None:
        """Send the robot to the charging station; returns the dropped task id."""
        dropped = self._task.id if self._task else None
        self._task = None
        self._task_phase = "pickup"
        self._nav_state = NavState.CHARGING
        return dropped

    @property
    def energy_consumed_units(self) -> float:
        """Battery units consumed so far."""
        return self._battery.units_consumed

    def _apply_failure_state(self) -> None:
        if self._failure in (FailureType.COMMUNICATION_LOSS, FailureType.SHUTDOWN):
            self._comm_state = CommState.OFFLINE
        if self._failure in (FailureType.SHUTDOWN, FailureType.NAVIGATION_FAILURE):
            self._nav_state = NavState.FAILED
        self._task = None
        self._task_phase = "pickup"

    def _charge(self, dt: float) -> None:
        added = self._battery.charge(dt)
        if added > 0:
            self._nav_state = NavState.CHARGING
        else:
            self._nav_state = NavState.IDLE

    def _move_toward_task(self, dt: float) -> None:
        if self._hold:
            self._battery.drain(dt, moving=False)
            return
        if self._task is None:
            return
        target = self._task.pickup if self._task_phase == "pickup" else self._task.delivery
        if self._position.distance_to(target) <= REACH_THRESHOLD_M:
            if self._task_phase == "pickup":
                self._task_phase = "delivery"
            else:
                self._completed_task_id = self._task.id
                self._task = None
                self._task_phase = "pickup"
                self._nav_state = NavState.IDLE
            return

        direction = math.atan2(target.y - self._position.y, target.x - self._position.x)
        self._orientation = direction
        step = min(self.MAX_LINEAR_VELOCITY * dt, self._position.distance_to(target))
        self._position = Vector2D(
            self._position.x + step * math.cos(direction),
            self._position.y + step * math.sin(direction),
        )
        self._distance_traveled += step
        self._nav_state = NavState.MOVING
        self._battery.drain(dt, moving=True)
