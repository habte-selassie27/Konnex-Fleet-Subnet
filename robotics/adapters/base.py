"""RobotAdapter Protocol — the hardware abstraction contract.

Status: COMPLETE (Phase 5 domain layer).
Interface per SYSTEM_PROMPT.md §3.2, extended with the simulation-facing
`tick`, `assign_task` and `inject_failure` operations used by the headless
simulation and fleet orchestrator.

SimulationRobotAdapter (headless sim) implements this Protocol. A Gazebo-backed
adapter (Phase 1) and PhysicalRobotAdapter (Phase 8+) will implement the same
interface — the orchestrator and policies never know which one they are talking to.
"""

from typing import Protocol

from robotics.models.failure import FailureType
from robotics.models.robot_state import RobotState
from robotics.models.sensor_frame import SensorFrame
from robotics.models.task import Task


class RobotAdapter(Protocol):
    """Interface every robot backend (simulated or physical) implements."""

    @property
    def robot_id(self) -> str:
        """Stable robot identifier."""
        ...

    def get_state(self) -> RobotState:
        """Current robot state snapshot."""
        ...

    def get_battery(self) -> float:
        """Current battery fraction in [0.0, 1.0]."""
        ...

    def get_sensors(self) -> SensorFrame | None:
        """Latest sensor frame, or None when unavailable."""
        ...

    def stop(self) -> None:
        """Stop all motion immediately."""
        ...

    def assign_task(self, task: Task) -> bool:
        """Accept a task. Returns False if the robot cannot accept commands."""
        ...

    def tick(self, dt: float) -> None:
        """Advance the (simulated) robot by dt seconds."""
        ...

    def inject_failure(self, failure_type: FailureType, duration_s: float | None = None) -> None:
        """Inject a failure; duration_s None means permanent."""
        ...

    def clear_failure(self) -> None:
        """Clear any injected failure."""
        ...

    def set_hold(self, hold: bool) -> None:
        """Pause motion this tick (collision-avoidance handshake)."""
        ...

    def take_completed_task(self) -> str | None:
        """Return and clear the id of a task completed since the last call."""
        ...

    def go_charge(self) -> str | None:
        """Send the robot to charge; returns the id of any dropped task."""
        ...

    @property
    def energy_consumed_units(self) -> float:
        """Battery units consumed so far."""
        ...
