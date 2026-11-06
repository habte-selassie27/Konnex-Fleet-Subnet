"""Pydantic v2 API request/response schemas.

Status: COMPLETE (Phase 6).
"""

from typing import Any

from pydantic import BaseModel, Field


class FailureInjectionRequest(BaseModel):
    """Body for POST /robots/{id}/fail."""

    failure_type: str
    duration_s: float | None = None


class MissionCreateRequest(BaseModel):
    """Body for POST /missions — configure a new live mission."""

    robot_count: int = Field(default=5, ge=1, le=50)
    task_count: int = Field(default=20, ge=1, le=200)
    seed: int = Field(default=42)
    policy: str = Field(default="nearest")
    time_limit_s: float = Field(default=600.0, gt=0.0)


class MissionResponse(BaseModel):
    """Current mission state returned by the missions API."""

    id: str  # noqa: A003
    scenario_id: str
    status: str
    policy: str
    robot_count: int
    task_count: int
    completed_tasks: int
    collision_count: int
    failure_count: int
    elapsed_seconds: float
    energy_consumed: float
    popw_score: float


class EvaluationSubmitRequest(BaseModel):
    """Body for POST /evaluations (validator -> backend)."""

    policy_id: str
    policy_hash: str
    scenario_id: str
    seed: int
    env_version: str = ""
    sim_version: str = ""
    status: str = "COMPLETE"
    final_score: float | None = None
    artifact_hash: str = ""
    artifact: dict[str, Any] = Field(default_factory=dict)  # arbitrary artifact JSON payload


class EvaluationResponse(BaseModel):
    """Response for evaluation submission/retrieval."""

    id: str  # noqa: A003
    policy_id: str
    status: str
    final_score: float | None
    artifact_hash: str
    artifact_url: str
    popw_commitments: dict[str, Any] | None = None
    stake: dict[str, Any] | None = None
    serving: dict[str, Any] | None = None


class RobotFailureResponse(BaseModel):
    """Response for a failure injection request."""

    robot_id: str
    failure_type: str
    injected: bool


# ─── Agentic payment layer (Arc + Circle USDC) ───────────────────────────────


class PaymentEventRequest(BaseModel):
    """Body for POST /payments/quote — a fleet event for the agent to observe."""

    vehicle_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)  # charging_required | fueling_required | ...
    battery_pct: float = Field(default=1.0, ge=0.0, le=1.0)
    note: str = ""


class ProviderQuoteResponse(BaseModel):
    """One provider option evaluated by the agent."""

    provider_id: str
    name: str
    service: str
    price_usdc: float
    distance_km: float
    rating: float
    address: str
    score: float
    selected: bool = False


class AgentDecisionResponse(BaseModel):
    """The agent's economic decision for a fleet event."""

    fleet_id: str
    vehicle_id: str
    service: str
    amount_usdc: float
    rationale: str
    no_action: bool = False
    selected_provider_id: str = ""
    quotes: list[ProviderQuoteResponse] = Field(default_factory=list)


class PaymentAuthorizeRequest(BaseModel):
    """Body for POST /payments/authorize — a structured agent payment request."""

    vehicle_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    service: str = Field(min_length=1)
    amount_usdc: float = Field(gt=0)
    currency: str = "USDC"
    reason: str = Field(min_length=1)
    max_allowed_usdc: float | None = None
    decision_rationale: str = ""
    fleet_id: str = ""


class PaymentAuthorizeResponse(BaseModel):
    """Outcome of the policy engine for one payment request."""

    intent_id: str
    approved: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class PaymentExecuteRequest(BaseModel):
    """Body for POST /payments/execute."""

    intent_id: str = Field(min_length=1)


class PaymentTransactionResponse(BaseModel):
    """A settled (or failed) agent payment transaction."""

    id: str  # noqa: A003
    intent_id: str
    fleet_id: str
    vehicle_id: str
    provider_id: str
    provider_name: str = ""
    provider_address: str
    service: str
    amount_usdc: float
    currency: str
    status: str
    settlement_status: str
    tx_hash: str
    receipt_id: str = ""
    reason: str = ""
    decision_rationale: str = ""
    explorer_url: str = ""
    is_mock: bool = True
    created_at: float = 0.0
    executed_at: float | None = None
    settled_at: float | None = None


class PaymentWalletResponse(BaseModel):
    """Agent wallet snapshot: balance, limits, and today's spend."""

    wallet_id: str
    currency: str
    balance_usdc: float
    daily_budget_usdc: float
    spent_today_usdc: float
    remaining_today_usdc: float
    max_tx_usdc: float
    is_mock: bool = True
    # Settlement network: "arc-mock" (simulation) or "arc-mainnet"/"arc-testnet".
    network: str = "arc-mock"


class PaymentSummaryResponse(BaseModel):
    """Aggregate agent-economy stats for the dashboard."""

    wallet: PaymentWalletResponse
    autonomous_payments: int
    usdc_settled: float
    arc_transactions: int
    receipts: int
    rejected_intents: int


class PaymentDemoResponse(BaseModel):
    """Result of the deterministic end-to-end demo scenario."""

    decisions: list[AgentDecisionResponse] = Field(default_factory=list)
    transactions: list[PaymentTransactionResponse] = Field(default_factory=list)
    summary: PaymentSummaryResponse


class BenchmarkResult(BaseModel):
    """One measured policy row from experiments/results/**/result.json.

    Values are read from artifacts written by actual runs; unmeasured policies
    keep ``None`` scores plus a ``skip_reason`` so the gap stays visible
    (AGENTS.md Law 1).
    """

    experiment_id: str
    policy: str
    scenario_id: str = ""
    harness: str = ""
    robot_count: int | None = None
    n_runs: int = 0
    seed_range: list[int] = Field(default_factory=list)
    mean_popw_score: float | None = None
    std_popw_score: float | None = None
    mean_success_rate: float | None = None
    std_success_rate: float | None = None
    mean_collision_count: float | None = None
    std_collision_count: float | None = None
    mean_completion_time_s: float | None = None
    std_completion_time_s: float | None = None
    status: str = "NOT_RUN"
    skip_reason: str = ""
    ran_at: str = ""
    git_commit: str = ""
    source: str = ""
    per_robot: list[dict[str, Any]] = Field(default_factory=list)


# ─── Konnex-aligned validator network (GET /validators/network) ─────────────


class ValidatorCheck(BaseModel):
    """One named assertion made by a role validator."""

    name: str
    passed: bool
    detail: str


class ValidatorAssessmentResponse(BaseModel):
    """One validator's independent verdict on the shared mission evidence."""

    validator_id: str
    role: str
    verdict: str
    score: float | None = None
    checks: list[ValidatorCheck] = Field(default_factory=list)
    reason: str


class ValidatorConsensusResponse(BaseModel):
    """Aggregated decision over all validator assessments."""

    decision: str
    accept_votes: int
    reject_votes: int
    validator_count: int
    reason: str


class MissionVerificationResponse(BaseModel):
    """Verification package for one mission snapshot (real evidence only)."""

    mission_id: str
    scenario_id: str
    policy: str
    mission_status: str
    tasks_completed: int
    task_count: int
    collision_count: int
    failure_count: int
    elapsed_s: float
    time_limit_s: float
    energy_consumed: float
    evidence_hash: str
    assessments: list[ValidatorAssessmentResponse]
    consensus: ValidatorConsensusResponse


class ValidatorIdentityResponse(BaseModel):
    """Registry entry for one role validator."""

    id: str
    role: str
    operator: str
    capabilities: list[str]
    implementation: str
    status: str


class KonnexValidatorBridgeResponse(BaseModel):
    """Status of the Konnex protocol bridge (STUB until SDK verified)."""

    adapter_status: str
    docs_url: str
    note: str


class ValidatorNetworkResponse(BaseModel):
    """Registry + the verification of the current live mission (if any)."""

    validators: list[ValidatorIdentityResponse]
    konnex: KonnexValidatorBridgeResponse
    verification: MissionVerificationResponse | None = None
