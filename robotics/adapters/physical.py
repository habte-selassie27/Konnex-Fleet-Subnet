"""PhysicalRobotAdapter — wraps ROS 2 hardware.

Status: STUB — Phase 8+ (post-MVP, PLAN.md §4.3). Hardware integration is
explicitly out of MVP scope; this adapter implements the RobotAdapter
protocol surface but raises NotImplementedError for every hardware operation
until physical robots are available. The interface is defined so the fleet
orchestrator and policies remain backend-agnostic.
"""

from robotics.adapters.base import RobotAdapter
from robotics.models.failure import FailureType
from robotics.models.robot_state import RobotState
from robotics.models.sensor_frame import SensorFrame
from robotics.models.task import Task


class PhysicalRobotAdapter:
    """RobotAdapter backed by real ROS 2 hardware.

    STUB: no physical robot is connected. Every method raises
    NotImplementedError. Replace with a real rclpy-backed implementation once
    hardware is available (see docs/sim-to-real.md).
    """

    def __init__(self, robot_id: str, ros_node: object | None = None) -> None:
        self._id = robot_id
        self._node = ros_node
        raise NotImplementedError(
            "PhysicalRobotAdapter is STUB. Physical robot integration is "
            "post-MVP. See docs/sim-to-real.md for the implementation plan."
        )

    @property
    def robot_id(self) -> str:
        return self._id

    def get_state(self) -> RobotState:
        raise NotImplementedError("PhysicalRobotAdapter is STUB.")

    def get_battery(self) -> float:
        raise NotImplementedError("PhysicalRobotAdapter is STUB.")

    def get_sensors(self) -> SensorFrame | None:
        raise NotImplementedError("PhysicalRobotAdapter is STUB.")

    def stop(self) -> None:
        raise NotImplementedError("PhysicalRobotAdapter is STUB.")

    def assign_task(self, task: Task) -> bool:
        raise NotImplementedError("PhysicalRobotAdapter is STUB.")

    def tick(self, dt: float) -> None:
        raise NotImplementedError("PhysicalRobotAdapter is STUB.")

    def inject_failure(self, failure_type: FailureType, duration_s: float | None = None) -> None:
        raise NotImplementedError("PhysicalRobotAdapter is STUB.")

    def clear_failure(self) -> None:
        raise NotImplementedError("PhysicalRobotAdapter is STUB.")

    def set_hold(self, hold: bool) -> None:
        raise NotImplementedError("PhysicalRobotAdapter is STUB.")

    def take_completed_task(self) -> str | None:
        raise NotImplementedError("PhysicalRobotAdapter is STUB.")

    def go_charge(self) -> str | None:
        raise NotImplementedError("PhysicalRobotAdapter is STUB.")

    @property
    def energy_consumed_units(self) -> float:
        raise NotImplementedError("PhysicalRobotAdapter is STUB.")
