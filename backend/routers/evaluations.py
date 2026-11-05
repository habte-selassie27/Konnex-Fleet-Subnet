"""Evaluations router — POST /evaluations, GET /evaluations/{id}, artifact.

Status: COMPLETE (Phase 6).
"""

import json
from typing import cast

from fastapi import APIRouter, HTTPException, Request

from backend.schemas import EvaluationResponse, EvaluationSubmitRequest
from backend.security import require_api_key
from backend.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


def _evaluations(request: Request) -> EvaluationService:
    """Resolve the evaluation service from request context."""
    return cast(EvaluationService, request.app.state.evaluations)


@router.get("", response_model=list[EvaluationResponse])
@router.get("/", response_model=list[EvaluationResponse])
async def list_evaluations(request: Request):
    """List all evaluations (minimal for dashboard/validators)."""
    return await _evaluations(request).list()


@router.post("/", status_code=201, response_model=EvaluationResponse)
async def submit_evaluation(body: EvaluationSubmitRequest, request: Request) -> EvaluationResponse:
    """Accept a validator's evaluation result (stores record + artifact)."""
    require_api_key(request)
    return await _evaluations(request).submit(body)


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(evaluation_id: str, request: Request) -> EvaluationResponse:
    """Fetch an evaluation by id."""
    response = await _evaluations(request).get(evaluation_id)
    if response is None:
        raise HTTPException(status_code=404, detail=f"evaluation {evaluation_id} not found")
    return response


@router.get("/{evaluation_id}/artifact")
async def get_artifact(evaluation_id: str, request: Request) -> dict[str, object]:
    """Download the evaluation artifact JSON."""
    text = await _evaluations(request).artifact_text(evaluation_id)
    if text is None:
        raise HTTPException(status_code=404, detail=f"evaluation {evaluation_id} not found")
    return cast(dict[str, object], json.loads(text))
