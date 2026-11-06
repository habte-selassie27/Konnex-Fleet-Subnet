"""Missions router — POST /missions, GET /missions/{id}.

Status: COMPLETE (Phase 10).
Used by the demo (`make demo` POSTs a predefined mission) and by the e2e
full-stack suite (TESTING_PLAN.md §6). The backend holds exactly one live
mission at a time (the demo fleet); GET returns the current mission's state
and 404s when no matching mission exists.
"""

from typing import cast

import structlog
from fastapi import APIRouter, HTTPException, Request

from backend.schemas import MissionCreateRequest, MissionResponse
from fleet.task_allocator import allocator_by_name
from backend.security import require_api_key
from backend.services.fleet_service import FleetAppState, live_popw_score

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/missions", tags=["missions"])


def _fleet(request: Request) -> FleetAppState:
    """Resolve the fleet app state from request context."""
    return cast(FleetAppState, request.app.state.fleet)


def _to_response(fleet: FleetAppState, mission_id: str) -> MissionResponse:
    """Build a MissionResponse for the currently live mission."""
    mission = fleet.mission
    if mission is None or mission.id != mission_id:
        logger.warning(
            "mission_not_found",
            requested=mission_id,
            current=getattr(fleet.mission, "id", None),
        )
        raise HTTPException(status_code=404, detail=f"mission {mission_id} not found")
    return MissionResponse(
        id=mission.id,
        scenario_id=mission.scenario_id,
        status=mission.status.value,
        policy=fleet.orchestrator.policy_name,
        robot_count=mission.robot_count,
        task_count=mission.task_count,
        completed_tasks=mission.completed_tasks,
        collision_count=mission.collision_count,
        failure_count=mission.failure_count,
        elapsed_seconds=mission.elapsed_seconds,
        energy_consumed=mission.energy_consumed,
        popw_score=live_popw_score(mission),
    )


@router.get("/policies", response_model=list[dict])
async def list_policies() -> list[dict]:
    """Return genuinely registered, executable allocator policies.

    Only policies that allocator_by_name can actually construct are exposed,
    so the frontend never invents a policy the backend cannot run.
    """
    registered = ["nearest", "hungarian", "cost_optimizer"]
    out = []
    for name in registered:
        try:
            alloc = allocator_by_name(name)
        except ValueError:
            continue
        out.append(
            {
                "id": name,
                "name": name,
                "algorithm": type(alloc).__name__,
                "available": True,
            }
        )
    return out


@router.post("/", status_code=201, response_model=MissionResponse)
async def create_mission(body: MissionCreateRequest, request: Request) -> MissionResponse:
    """Configure and start a new live mission (replaces the current one)."""
    require_api_key(request)
    fleet = _fleet(request)
    try:
        mission = fleet.start_mission(
            robot_count=body.robot_count,
            task_count=body.task_count,
            seed=body.seed,
            policy=body.policy,
            time_limit_s=body.time_limit_s,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return _to_response(fleet, mission.id)


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(mission_id: str, request: Request) -> MissionResponse:
    """Return the live mission's state when it matches `mission_id`."""
    return _to_response(_fleet(request), mission_id)
