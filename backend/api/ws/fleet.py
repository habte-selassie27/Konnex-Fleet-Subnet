"""WebSocket /ws/fleet — live fleet telemetry for the dashboard.

Status: COMPLETE (Phase 9). Contract (AGENTS.md §1.5, TESTING_PLAN.md §15):
- Pushes ROBOT_STATE_UPDATE / MISSION_UPDATE snapshots at ~10 Hz and
  TASK_COMPLETED / COLLISION_DETECTED delta events as they occur.
- Emits SIMULATOR_OFFLINE when no live mission data exists.
- Auth: `?api_key=` query param must match settings.fleet_api_key
  (browsers cannot set headers on WebSocket, AGENTS.md §2.1).

The broadcaster polls the orchestrator's FleetState (no coupling to Gazebo or
ROS — the dashboard only ever consumes this typed contract).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, cast

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.config import Settings
from backend.events.types import (
    CollisionDetectedEvent,
    FleetEvent,
    MissionUpdateEvent,
    RobotStateUpdateEvent,
    SimulatorOfflineEvent,
    TaskCompletedEvent,
    event_to_dict,
)
from backend.services.fleet_service import FleetAppState, live_popw_score
from fleet.mission_manager import Mission
from robotics.models.fleet_state import FleetState
from robotics.models.robot_state import RobotState

logger = structlog.get_logger(__name__)

router = APIRouter()

BROADCAST_INTERVAL_S = 0.1  # 10 Hz — satisfies "positions update <= 100ms"


class FleetConnectionManager:
    """Tracks active dashboard WebSocket clients."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    @property
    def connection_count(self) -> int:
        """Number of connected clients."""
        return len(self._connections)

    async def connect(self, ws: WebSocket) -> None:
        """Accept a client and register it."""
        await ws.accept()
        self._connections.append(ws)
        logger.info("ws_client_connected", total=len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        """Unregister a client."""
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info("ws_client_disconnected", total=len(self._connections))

    async def broadcast(self, event: FleetEvent) -> None:
        """Send an event to every connected client (drop dead sockets)."""
        payload = event_to_dict(event)
        stale: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 -- network failure, drop client
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


manager = FleetConnectionManager()


def _robot_state_to_dict(state: RobotState) -> dict[str, Any]:
    """Serialize a RobotState to the dashboard contract shape."""
    return {
        "id": state.id,
        "position": {"x": state.position.x, "y": state.position.y},
        "orientation": state.orientation,
        "velocity": {"x": state.velocity.x, "y": state.velocity.y},
        "battery_pct": state.battery_pct,
        "current_task_id": state.current_task_id,
        "nav_state": state.nav_state.value,
        "in_collision": state.in_collision,
        "comm_state": state.comm_state.value,
        "timestamp": state.timestamp,
        "distance_traveled": state.distance_traveled,
    }


class FleetBroadcaster:
    """Polls the orchestrator and broadcasts delta + snapshot events.

    Runs as a lifespan task so it lives for the app's lifetime; with zero
    connected clients the broadcast loop is a no-op.
    """

    def __init__(self, fleet: FleetAppState, settings: Settings) -> None:
        self._fleet = fleet
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._last_mission_id: str | None = None
        self._last_completed: set[str] = set()
        self._last_collisions = 0

    def start(self) -> None:
        """Start the broadcast loop task."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Cancel the broadcast loop."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(BROADCAST_INTERVAL_S)
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 -- keep the loop alive
                logger.exception("broadcast_loop_error")

    async def _tick(self) -> None:
        """Update delta baselines every tick; broadcast only when clients exist.

        Baselines are tracked regardless of connection count so that a client
        connecting mid-mission receives deltas from the *current* point, not a
        burst of every task that completed since startup.
        """
        orchestrator = self._fleet.orchestrator
        state = orchestrator.get_fleet_state()

        if not state.robots or state.mission_id is None:
            self._last_mission_id = None
            self._last_completed.clear()
            self._last_collisions = 0
            if manager.connection_count == 0:
                return
            await manager.broadcast(
                SimulatorOfflineEvent(reason="no live mission", timestamp=time.time())
            )
            return

        # A new mission invalidates delta baselines (task ids are unique per
        # mission, but resetting keeps the baseline explicit and cheap).
        if state.mission_id != self._last_mission_id:
            self._last_mission_id = state.mission_id
            self._last_completed.clear()
            self._last_collisions = 0

        completed = {task.id for task in state.active_tasks if task.status.value == "completed"}
        new_completed = completed - self._last_completed
        self._last_completed = completed
        new_collisions = max(0, state.collision_count - self._last_collisions)
        self._last_collisions = state.collision_count

        if manager.connection_count == 0:
            return
        await self._broadcast_once(state, new_completed, new_collisions)

    async def _broadcast_once(
        self,
        state: FleetState,
        new_completed: set[str],
        new_collisions: int,
    ) -> None:
        # Resolve the mission BEFORE any await: a POST /missions handler can
        # swap the orchestrator between our awaits on the same event loop, and
        # broadcasting stale state with the new mission's fields would emit one
        # inconsistent MISSION_UPDATE. Drop the frame instead — next tick
        # re-reads both consistently.
        mission = self._fleet.mission
        mission_id = state.mission_id
        if mission_id is None or mission is None or mission.id != mission_id:
            return
        now = time.time()

        for robot in state.robots:
            await manager.broadcast(
                RobotStateUpdateEvent(
                    robot_id=robot.id,
                    state=_robot_state_to_dict(robot),
                    timestamp=now,
                )
            )

        await manager.broadcast(
            MissionUpdateEvent(
                mission_id=mission_id,
                status=state.mission_status,
                policy=self._fleet.orchestrator.policy_name,
                completed_tasks=state.completed_tasks,
                total_tasks=state.total_tasks,
                collision_count=state.collision_count,
                failure_count=mission.failure_count if mission else 0,
                elapsed_seconds=state.elapsed_seconds,
                energy_consumed=mission.energy_consumed if mission else 0.0,
                popw_score=live_popw_score(mission) if mission else None,
                timestamp=now,
            )
        )

        # Delta events computed in _tick() against current-state baselines.
        for task_id in new_completed:
            await manager.broadcast(TaskCompletedEvent(task_id=task_id, timestamp=now))
        if new_collisions > 0:
            await manager.broadcast(
                CollisionDetectedEvent(
                    robot_id=_collision_robot_id(mission),
                    near_miss=False,
                    timestamp=now,
                )
            )


def _collision_robot_id(mission: Mission | None) -> str:
    """Best-effort attribution: the first robot holding an active task.

    The dashboard uses the event for a visual flash, not for attribution
    accuracy, so this is intentionally approximate.
    """
    if mission is None or not mission.tasks:
        return ""
    for task in mission.tasks:
        if task.assigned_robot_id is not None:
            return task.assigned_robot_id
    return ""


@router.websocket("/fleet")
async def fleet_websocket(
    ws: WebSocket,
    api_key: str = Query(default=""),
) -> None:
    """Live fleet telemetry endpoint for the dashboard."""
    settings = cast(Settings, ws.app.state.settings)
    if api_key != settings.fleet_api_key:
        await ws.close(code=4401, reason="invalid api key")
        return
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(ws)
