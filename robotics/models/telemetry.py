"""Telemetry record types shared by the fleet and validator layers.

Status: COMPLETE (Phase 5 domain layer).
These are neutral data records so the fleet orchestrator can produce them and
the validator can consume them without importing fleet internals (AGENTS.md §3.2).
"""

from dataclasses import dataclass

from robotics.models.robot_state import Vector2D


@dataclass(frozen=True)
class TrajectoryFrame:
    """A single robot position sample during a mission."""

    t: float
    robot_id: str
    x: float
    y: float


@dataclass(frozen=True)
class TaskOutcome:
    """The final status of one task after a mission."""

    task_id: str
    robot_id: str | None
    status: str
    completed_at: float | None = None


@dataclass(frozen=True)
class EnergyEntry:
    """A battery sample for one robot during a mission."""

    robot_id: str
    t: float
    battery_pct: float


@dataclass(frozen=True)
class CollisionEvent:
    """A detected robot-robot or near-miss event."""

    robot_id: str
    other_id: str
    position: Vector2D
    timestamp: float
    near_miss: bool = False
