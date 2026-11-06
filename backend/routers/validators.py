"""Validators router — role validators, consensus and evaluation context.

`GET /validators/network` is the live fleet subnet's own validator network:
three role validators (execution, safety, performance) independently assess the
current mission evidence, then a consensus layer decides. Evidence comes from
the running mission record — nothing is fabricated (AGENTS.md Law 1).

The `GET /validators/evaluations/{id}/context` endpoint remains the placeholder
Konnex framing for a known evaluation; its Konnex-specific fields stay empty
until `protocol/konnex/adapter.py` is wired against the verified SDK.
"""

from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request

from backend.schemas import (
    EvaluationResponse,
    KonnexValidatorBridgeResponse,
    MissionVerificationResponse,
    ValidatorAssessmentResponse,
    ValidatorCheck,
    ValidatorConsensusResponse,
    ValidatorIdentityResponse,
    ValidatorNetworkResponse,
)
from backend.security import require_api_key
from backend.services.evaluation_service import EvaluationService
from backend.services.fleet_service import FleetAppState
from validator.network import VALIDATORS, MissionEvidence, Verification, verify_mission

KONNEX_VALIDATOR_DOCS = "https://docs.konnex.world/sdk/validators"
KONNEX_ADAPTER_STATUS = "STUB"
KONNEX_BRIDGE_NOTE = (
    "Fleet-subnet validators run locally over real mission evidence. Konnex "
    "protocol registration, staking and ScoreRoot publishing are not wired: "
    "protocol/konnex/adapter.py is STUB until the Konnex SDK is verified."
)

router = APIRouter(prefix="/validators", tags=["validators"])


def _evaluations(request: Request) -> EvaluationService:
    """Resolve the evaluation service from request context."""
    return cast(EvaluationService, request.app.state.evaluations)


def _fleet(request: Request) -> FleetAppState:
    """Resolve the live fleet from request context."""
    return cast(FleetAppState, request.app.state.fleet)


def _verification_response(verification: Verification) -> MissionVerificationResponse:
    """Serialize a verification package into the API contract."""
    evidence = verification.evidence
    return MissionVerificationResponse(
        mission_id=evidence.mission_id,
        scenario_id=evidence.scenario_id,
        policy=evidence.policy,
        mission_status=evidence.mission_status,
        tasks_completed=evidence.tasks_completed,
        task_count=evidence.task_count,
        collision_count=evidence.collision_count,
        failure_count=evidence.failure_count,
        elapsed_s=evidence.elapsed_s,
        time_limit_s=evidence.time_limit_s,
        energy_consumed=evidence.energy_consumed,
        evidence_hash=verification.evidence_hash,
        assessments=[
            ValidatorAssessmentResponse(
                validator_id=assessment.validator_id,
                role=assessment.role,
                verdict=assessment.verdict,
                score=assessment.score,
                checks=[
                    ValidatorCheck(name=c.name, passed=c.passed, detail=c.detail)
                    for c in assessment.checks
                ],
                reason=assessment.reason,
            )
            for assessment in verification.assessments
        ],
        consensus=ValidatorConsensusResponse(
            decision=verification.consensus.decision,
            accept_votes=verification.consensus.accept_votes,
            reject_votes=verification.consensus.reject_votes,
            validator_count=verification.consensus.validator_count,
            reason=verification.consensus.reason,
        ),
    )


def _current_verification(fleet: FleetAppState) -> MissionVerificationResponse | None:
    """Verify the live mission, or None when the fleet has no mission yet."""
    mission = fleet.mission
    if mission is None:
        return None
    evidence = MissionEvidence.from_mission(
        mission, policy=fleet.orchestrator.policy_name
    )
    return _verification_response(verify_mission(evidence))


@router.get(
    "/network",
    response_model=ValidatorNetworkResponse,
    summary="Validator registry and current mission verification",
)
async def get_validator_network(request: Request) -> ValidatorNetworkResponse:
    """Return the registered role validators and their verdict on the live mission.

    The three validators receive the same evidence package and assess it
    independently; consensus uses a 2-of-3 quorum with a safety veto. A running
    mission reports PENDING (never an early accept). Konnex protocol fields are
    reported as STUB — no Konnex network call is made.
    """
    return ValidatorNetworkResponse(
        validators=[
            ValidatorIdentityResponse(
                id=spec.id,
                role=spec.role,
                operator=spec.operator,
                capabilities=list(spec.capabilities),
                implementation=spec.implementation,
                status=spec.status,
            )
            for spec in VALIDATORS
        ],
        konnex=KonnexValidatorBridgeResponse(
            adapter_status=KONNEX_ADAPTER_STATUS,
            docs_url=KONNEX_VALIDATOR_DOCS,
            note=KONNEX_BRIDGE_NOTE,
        ),
        verification=_current_verification(_fleet(request)),
    )


@router.get(
    "/missions/{mission_id}/verification",
    response_model=MissionVerificationResponse,
    summary="Verification package for one mission",
)
async def get_mission_verification(
    mission_id: str, request: Request
) -> MissionVerificationResponse:
    """Verify a specific live mission (404 when it is not the current one)."""
    verification = _current_verification(_fleet(request))
    if verification is None or verification.mission_id != mission_id:
        raise HTTPException(
            status_code=404, detail=f"mission {mission_id} not found"
        )
    return verification


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
