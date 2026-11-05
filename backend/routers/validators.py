"""Validators router — validator/evaluation context for the dashboard.

Status: STUB (Phase 9). Returns the frontend's expected validator context shape
for a known evaluation. Konnex-specific fields are placeholder values until the
Konnex adapter is verified and wired; this endpoint is the fleet subnet’s own
view of validator context, not a Konnex network call.
"""

from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request

from backend.schemas import EvaluationResponse
from backend.security import require_api_key
from backend.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/validators", tags=["validators"])


def _evaluations(request: Request) -> EvaluationService:
    """Resolve the evaluation service from request context."""
    return cast(EvaluationService, request.app.state.evaluations)


def _placeholder_validator_context(_evaluation: EvaluationResponse) -> dict[str, Any]:
    """Minimal Konnex validator context shape for frontend consumption.

    This is deliberately placeholder data (fleet subnet's own view):
    - ScoreRoot / commitments, staking tranche status (knx_staked, knx_at_risk_after_slash,
      stablecoin_settlement_assurance), serving state, and slashing/economics framing
      are present so the frontend can render the Konnex framing panel without
      inventing live data.
    - All Konnex-specific fields are clearly marked as populated by Konnex adapter
      when available; they are not backed by a real Konnex adapter yet.
    """
    return {
        "scoreroot_hash": "",
        "scoreroot_url": "",
        "commitments_url": "",
        "knx_staked": 0.0,
        "knx_at_risk_after_slash": 0.0,
        "stablecoin_settlement_assurance": 0.0,
        "evaluator_status": "ready",
        "serving_mode": "idle",
        "active_request_id": None,
        "requests_since_reset": 0,
        "last_checkpoint_ms": None,
        "_note": (
            "Konnex validator context is not yet wired to a real Konnex adapter. "
            "Populated by Konnex adapter when available."
        ),
        "_source": "fleet_subnet_view",
    }


@router.get(
    "/evaluations/{evaluation_id}/context",
    response_model=dict[str, Any],
    summary="Validator context for an evaluation",
)
async def get_validator_context(evaluation_id: str, request: Request) -> dict[str, Any]:
    """Return validator-side context for an evaluation, if it exists.

    This is the backend equivalent of the frontend's `getValidatorContext(...)`
    call (exact shape expected). It is the fleet subnet's own view of validator
    context — Konnex-specific fields (ScoreRoots/commitments, staking tranche
    status, serving state, slashing/economics framing) are present but marked
    as populated by Konnex adapter when available. No live Konnex protocol call
    is made.
    """
    require_api_key(request)
    evaluation = await _evaluations(request).get(evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail=f"evaluation {evaluation_id} not found")
    return _placeholder_validator_context(evaluation)
