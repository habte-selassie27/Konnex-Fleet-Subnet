"""Robot state dataclasses — the shared robot state surface.

Status: COMPLETE (Phase 5 domain layer).
Interface per BUILD.md §4 and PLAN.md §6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import hypot


class NavState(str, Enum):
    """Robot navigation state machine states."""

    IDLE = "idle"
    MOVING = "moving"
    BLOCKED = "blocked"
    CHARGING = "charging"
    FAILED = "failed"


class CommState(str, Enum):
    """Robot communication state."""

    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass(frozen=True)
class Vector2D:
    """Immutable 2D world-frame position."""

    x: float
    y: float

    def distance_to(self, other: Vector2D) -> float:
        """Euclidean distance to another point."""
        return hypot(self.x - other.x, self.y - other.y)


@dataclass
class RobotState:
    """Snapshot of a single robot's state at a point in time."""

    id: str  # noqa: A003 -- `id` mandated by BUILD.md domain models
    position: Vector2D
    orientation: float = 0.0
    velocity: Vector2D = field(default_factory=lambda: Vector2D(0.0, 0.0))
    battery_pct: float = 1.0
    current_task_id: str | None = None
    nav_state: NavState = NavState.IDLE
    in_collision: bool = False
    comm_state: CommState = CommState.ONLINE
    timestamp: float = 0.0
    distance_traveled: float = 0.0
