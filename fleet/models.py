"""Task, Assignment, and related data models.

Spec (AGENTS.md §7.1, TESTING_PLAN.md §3.1):
    Task: pickup/delivery locations, priority, status, assignment tracking
    Assignment: robot_id + task_id + cost
    TaskPriority: LOW/MEDIUM/HIGH/URGENT
    TaskStatus: PENDING/ASSIGNED/IN_PROGRESS/COMPLETED/FAILED/REASSIGNED
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class TaskPriority(int, Enum):
    """Task priority levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


class TaskStatus(str, Enum):
    """Task lifecycle states."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REASSIGNED = "reassigned"


@dataclass
class TaskLocation:
    """A 2D point with optional zone identifier."""

    x: float = 0.0
    y: float = 0.0
    zone_id: str = ""


@dataclass
class Task:
    """A single pickup-and-delivery task.

    Lifecycle: PENDING -> ASSIGNED -> IN_PROGRESS -> COMPLETED | FAILED
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pickup: TaskLocation = field(default_factory=TaskLocation)
    delivery: TaskLocation = field(default_factory=TaskLocation)
    priority: TaskPriority = TaskPriority.MEDIUM
    weight_kg: float = 1.0
    status: TaskStatus = TaskStatus.PENDING
    assigned_robot: str | None = None
    created_at: float = 0.0
    assigned_at: float | None = None
    completed_at: float | None = None
    attempts: int = 0

    @property
    def is_pending(self) -> bool:
        return self.status == TaskStatus.PENDING

    @property
    def is_terminal(self) -> bool:
        return self.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}


@dataclass
class Assignment:
    """A robot-task assignment with associated cost."""

    robot_id: str = ""
    task_id: str = ""
    cost: float = 0.0
