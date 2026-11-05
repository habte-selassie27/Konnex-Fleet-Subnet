"""SQLModel DB models: Evaluation (Mission/Policy added per phase).

Status: COMPLETE (Phase 6 — Evaluation model used by the evaluations API).
"""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(timezone.utc)


class EvaluationRecord(SQLModel, table=True):
    """Persisted evaluation result and artifact pointer."""

    __tablename__ = "evaluations"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)  # noqa: A003
    policy_id: str = Field(index=True)
    policy_hash: str = ""
    scenario_id: str = ""
    seed: int = 0
    env_version: str = ""
    sim_version: str = ""
    status: str = ""
    final_score: float | None = None
    artifact_hash: str = ""
    artifact_path: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class PaymentRecord(SQLModel, table=True):
    """Persisted agentic payment transaction (mock provider in demo mode)."""

    __tablename__ = "payments"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)  # noqa: A003
    intent_id: str = Field(default="", index=True)
    fleet_id: str = ""
    vehicle_id: str = ""
    provider_id: str = ""
    provider_name: str = ""
    provider_address: str = ""
    service: str = ""
    amount_usdc: float = 0.0
    currency: str = "USDC"
    status: str = ""
    settlement_status: str = ""
    tx_hash: str = Field(default="", index=True)
    receipt_id: str = ""
    reason: str = ""
    decision_rationale: str = ""
    explorer_url: str = ""
    is_mock: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    executed_at: datetime | None = None
    settled_at: datetime | None = None
