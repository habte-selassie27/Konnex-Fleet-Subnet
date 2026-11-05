"""Task and Assignment dataclasses.

Status: COMPLETE (Phase 5 domain layer).
"""

from dataclasses import dataclass
from enum import Enum

from robotics.models.robot_state import Vector2D


class Priority(str, Enum):
    """Task priority tiers."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(str, Enum):
    """Task lifecycle states."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass
class Task:
    """A pickup/delivery task within a mission."""

    id: str  # noqa: A003 -- `id` mandated by BUILD.md domain models
    pickup: Vector2D
    delivery: Vector2D
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    assigned_robot_id: str | None = None
    created_at: float = 0.0
    completed_at: float | None = None


@dataclass(frozen=True)
class Assignment:
    """A robot -> task assignment produced by an allocator."""

    robot_id: str
    task_id: str
    distance: float = 0.0
