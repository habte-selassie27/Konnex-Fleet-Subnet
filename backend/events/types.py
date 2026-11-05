"""Typed fleet events broadcast over /ws/fleet (Phase 9 dashboard contract).

Contract (AGENTS.md §1.5, TESTING_PLAN.md §15):
- ROBOT_STATE_UPDATE  — live robot position/state snapshot
- MISSION_UPDATE      — mission progress (tasks, collisions, elapsed, score)
- TASK_COMPLETED      — a task finished (delta event)
- COLLISION_DETECTED  — a collision (or near-miss) was recorded
- SIMULATOR_OFFLINE   — no live fleet data available

All events serialize to JSON via to_dict(); the frontend dispatches on the
"type" field (src/hooks/useFleetSocket.ts).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FleetEvent:
    """Base class — `type` discriminates the payload on the client."""

    type: str  # noqa: A003 -- mandated by the WS contract


@dataclass(frozen=True)
class RobotStateUpdateEvent(FleetEvent):
    """Live robot state. `state` mirrors robotics.models.robot_state.RobotState."""

    type: str = "ROBOT_STATE_UPDATE"  # noqa: A003
    robot_id: str = ""
    state: dict[str, Any] | None = None
    timestamp: float = 0.0


@dataclass(frozen=True)
class MissionUpdateEvent(FleetEvent):
    """Aggregate mission snapshot (fields match robotics Mission/FleetState)."""

    type: str = "MISSION_UPDATE"  # noqa: A003
    mission_id: str = ""
    status: str = ""
    policy: str = ""
    completed_tasks: int = 0
    total_tasks: int = 0
    collision_count: int = 0
    failure_count: int = 0
    elapsed_seconds: float = 0.0
    energy_consumed: float = 0.0
    popw_score: float | None = None
    timestamp: float = 0.0


@dataclass(frozen=True)
class TaskCompletedEvent(FleetEvent):
    """Delta event: a task finished."""

    type: str = "TASK_COMPLETED"  # noqa: A003
    task_id: str = ""
    robot_id: str | None = None
    timestamp: float = 0.0


@dataclass(frozen=True)
class CollisionDetectedEvent(FleetEvent):
    """Delta event: a collision (or near-miss) was recorded."""

    type: str = "COLLISION_DETECTED"  # noqa: A003
    robot_id: str = ""
    near_miss: bool = False
    x: float = 0.0
    y: float = 0.0
    timestamp: float = 0.0


@dataclass(frozen=True)
class SimulatorOfflineEvent(FleetEvent):
    """No live fleet data available (e.g., no mission running)."""

    type: str = "SIMULATOR_OFFLINE"  # noqa: A003
    reason: str = ""
    timestamp: float = 0.0


def event_to_dict(event: FleetEvent) -> dict[str, Any]:
    """Serialize any FleetEvent to a JSON-safe dict."""
    return asdict(event)
