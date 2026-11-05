"""FleetState — aggregate fleet snapshot.

Status: COMPLETE (Phase 5 domain layer).
"""

from dataclasses import dataclass

from robotics.models.robot_state import RobotState
from robotics.models.task import Task


@dataclass
class FleetState:
    """Aggregate view of the fleet used by monitoring and policies."""

    robots: list[RobotState]
    active_tasks: list[Task]
    mission_id: str | None = None
    mission_status: str = "pending"
    completed_tasks: int = 0
    total_tasks: int = 0
    collision_count: int = 0
    elapsed_seconds: float = 0.0
    timestamp: float = 0.0
