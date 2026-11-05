"""Agentic payment layer domain models — protocol-safe types only.

Boundary contract:
    This module (and the whole payments/ package) imports NOTHING from
    fleet/, robotics/, simulation/, ml/, or protocol/. Fleet telemetry enters
    as plain dataclasses (FleetEvent); everything else is primitives and
    payment-domain types. This keeps the payment layer independently
    testable and safe to hand to the live Arc/Circle integration.

Status: COMPLETE (payment layer — mock provider by default; real Circle/Arc
provider implemented in payments/real_provider.py, requires credentials).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class ServiceType(str, Enum):
    """Operational services the fleet agent can purchase."""

    CHARGING = "charging"
    FUELING = "fueling"
    MAINTENANCE = "maintenance"
    INSPECTION = "inspection"


class EventType(str, Enum):
    """Fleet operational events the agent can observe."""

    CHARGING_REQUIRED = "charging_required"
    FUELING_REQUIRED = "fueling_required"
    MAINTENANCE_REQUIRED = "maintenance_required"
    INSPECTION_DUE = "inspection_due"


class PaymentStatus(str, Enum):
    """Lifecycle of an agent payment intent / transaction."""

    DRAFT = "draft"
    AUTHORIZED = "authorized"
    REJECTED = "rejected"
    EXECUTED = "executed"
    SETTLED = "settled"
    FAILED = "failed"


class SettlementStatus(str, Enum):
    """Arc settlement status of an executed USDC transfer."""

    NONE = "none"  # not submitted to Arc yet
    PENDING = "pending"  # submitted, awaiting confirmation
    SETTLED = "settled"  # confirmed on (mock) Arc
    FAILED = "failed"


@dataclass(frozen=True)
class FleetEvent:
    """An operational fleet event the agent can observe (protocol-safe).

    This is the ONLY fleet-shaped input that crosses into the payment layer.
    It carries primitives only — never robot state objects.
    """

    vehicle_id: str
    event_type: EventType
    battery_pct: float = 1.0
    note: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class Provider:
    """A service provider the agent can pay (deterministic catalog entry)."""

    provider_id: str
    name: str
    service: ServiceType
    price_usdc: float
    distance_km: float
    rating: float
    address: str  # 0x + 40 hex chars (validated by PaymentPolicy)


@dataclass(frozen=True)
class ProviderQuote:
    """A provider option with the agent's utility score (lower is better)."""

    provider: Provider
    score: float
    price_note: str = ""


@dataclass(frozen=True)
class AgentDecision:
    """The agent's economic decision: which provider, at what price, and why.

    `no_action=True` means the agent concluded no purchase is needed (e.g.
    battery is above the charging threshold) — no PaymentIntent is created.

    `id` makes the decision independently addressable so the backend can
    persist and display the exact decision that preceded a payment.
    """

    fleet_id: str
    vehicle_id: str
    service: ServiceType
    quotes: tuple[ProviderQuote, ...]
    selected_provider_id: str
    amount_usdc: float
    rationale: str
    no_action: bool = False
    id: str = field(default_factory=lambda: str(uuid.uuid4()))  # noqa: A003
    event_type: EventType | None = None
    battery_pct: float = 1.0
    note: str = ""
    timestamp: float = field(default_factory=time.time)

    @property
    def selected(self) -> ProviderQuote | None:
        """The chosen quote, or None when the decision was no_action."""
        for quote in self.quotes:
            if quote.provider.provider_id == self.selected_provider_id:
                return quote
        return None


@dataclass
class PaymentIntent:
    """A structured payment request produced by the agent.

    The policy engine validates this BEFORE any wallet or chain interaction —
    the AI never calls the wallet directly.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    fleet_id: str = ""
    vehicle_id: str = ""
    provider_id: str = ""
    service: ServiceType = ServiceType.CHARGING
    amount_usdc: float = 0.0
    currency: str = "USDC"
    reason: str = ""
    max_allowed_usdc: float = 0.0
    decision_rationale: str = ""
    status: PaymentStatus = PaymentStatus.DRAFT
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class PaymentRequest:
    """Structured payment request submitted for policy authorization."""

    fleet_id: str = ""
    vehicle_id: str = ""
    provider_id: str = ""
    service: ServiceType = ServiceType.CHARGING
    amount_usdc: float = 0.0
    currency: str = "USDC"
    reason: str = ""
    max_allowed_usdc: float = 0.0
    decision_rationale: str = ""


@dataclass
class TransactionRecord:
    """A persisted payment transaction (executed/settled via the provider)."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    intent_id: str = ""
    fleet_id: str = ""
    vehicle_id: str = ""
    provider_id: str = ""
    provider_name: str = ""
    provider_address: str = ""
    service: ServiceType = ServiceType.CHARGING
    amount_usdc: float = 0.0
    currency: str = "USDC"
    status: PaymentStatus = PaymentStatus.EXECUTED
    settlement_status: SettlementStatus = SettlementStatus.PENDING
    tx_hash: str = ""
    receipt_id: str = ""
    reason: str = ""
    decision_rationale: str = ""
    explorer_url: str = ""
    is_mock: bool = True
    # Provider reconciliation data. Real Circle transfers are asynchronous:
    # Circle returns a transfer id before the Arc transaction hash exists, so
    # both identifiers are stored and surfaced in the dashboard.
    provider_transaction_id: str = ""
    provider_status: str = ""
    error_reason: str = ""
    block_number: int | None = None
    chain_id: str = ""
    created_at: float = field(default_factory=time.time)
    executed_at: float | None = None
    settled_at: float | None = None


@dataclass(frozen=True)
class ProviderTransfer:
    """Result of a USDC transfer executed through the payment provider."""

    tx_hash: str
    status: PaymentStatus
    settlement_status: SettlementStatus
    provider_payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentReceipt:
    """Verifiable receipt produced after Arc settlement (mock in demo mode)."""

    receipt_id: str
    transaction_id: str
    tx_hash: str
    fleet_id: str
    vehicle_id: str
    provider_id: str
    service: ServiceType
    amount_usdc: float
    currency: str
    network: str
    explorer_url: str
    settled_at: float
    is_mock: bool = True


@dataclass(frozen=True)
class WalletSnapshot:
    """Agent wallet state: balance, limits, and today's spend."""

    wallet_id: str
    currency: str
    balance_usdc: float
    daily_budget_usdc: float
    spent_today_usdc: float
    remaining_today_usdc: float
    max_tx_usdc: float
    is_mock: bool = True
    # Settlement network label: "arc-mock" for the simulator, "arc-mainnet" /
    # "arc-testnet" for the real provider (docs.arc.io network parameters).
    network: str = "arc-mock"
    # On-chain address of the agent wallet (empty for the in-process mock).
    wallet_address: str = ""
