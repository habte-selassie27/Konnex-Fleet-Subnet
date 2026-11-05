"""Robots router — GET /robots, GET /robots/{id}, POST /robots/{id}/fail.

Status: COMPLETE (Phase 5/6). The failure-injection endpoint is the Phase 5
gate `POST /robots/:id/fail`.
"""

from typing import cast

from fastapi import APIRouter, HTTPException, Request

from backend.schemas import FailureInjectionRequest, RobotFailureResponse
from backend.security import require_api_key
from backend.services.fleet_service import FleetAppState
from robotics.models.failure import FailureType
from robotics.models.robot_state import RobotState

router = APIRouter(prefix="/robots", tags=["robots"])


def _fleet(request: Request) -> FleetAppState:
    """Resolve the fleet app state from request context."""
    return cast(FleetAppState, request.app.state.fleet)


@router.get("/")
async def list_robots(request: Request) -> list[RobotState]:
    """List all robots with their live state."""
    return _fleet(request).orchestrator.get_fleet_state().robots


@router.get("/{robot_id}")
async def get_robot(robot_id: str, request: Request) -> RobotState:
    """Get one robot's live state."""
    for state in _fleet(request).orchestrator.get_fleet_state().robots:
        if state.id == robot_id:
            return state
    raise HTTPException(status_code=404, detail=f"robot {robot_id} not found")


@router.post("/{robot_id}/fail", status_code=200)
async def fail_robot(
    robot_id: str, body: FailureInjectionRequest, request: Request
) -> RobotFailureResponse:
    """Inject a failure into a robot (Phase 5 failure-injection API)."""
    require_api_key(request)
    try:
        failure_type = FailureType(body.failure_type)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"unknown failure_type: {body.failure_type}"
        ) from None
    injected = _fleet(request).orchestrator.inject_failure(robot_id, failure_type, body.duration_s)
    if not injected:
        raise HTTPException(status_code=404, detail=f"robot {robot_id} not found")
    return RobotFailureResponse(robot_id=robot_id, failure_type=body.failure_type, injected=True)
