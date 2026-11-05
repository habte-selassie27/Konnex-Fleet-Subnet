"""Agentic Payment Layer — Arc + Circle USDC payments for the fleet agent.

The AI agent never touches a wallet. Every payment flows through a
deterministic policy gate first:

    FleetEvent -> AgentDecision -> PaymentIntent -> PaymentPolicy
    -> CirclePaymentProvider (USDC) -> Arc settlement -> PaymentReceipt

Status: COMPLETE (mock provider, explicitly labeled MOCK/DEMO).
Real Circle Wallets + Arc integration is a documented STUB (docs/payments.md)
that requires credentials not present in this repo.

Boundary contract: the payments/ package imports NOTHING from fleet/,
robotics/, simulation/, ml/, or protocol/. Fleet telemetry enters as plain
FleetEvent dataclasses — keeping this layer independently testable and safe
to hand to the live Arc/Circle integration.
"""

from payments.agent import FleetPaymentAgent
from payments.factory import create_payment_provider
from payments.mock_provider import MockCircleProvider
from payments.models import (
    AgentDecision,
    EventType,
    FleetEvent,
    PaymentIntent,
    PaymentReceipt,
    PaymentRequest,
    PaymentStatus,
    Provider,
    ProviderQuote,
    ProviderTransfer,
    ServiceType,
    SettlementStatus,
    TransactionRecord,
    WalletSnapshot,
)
from payments.policy import PaymentPolicy, PolicyDecision
from payments.providers import ProviderRegistry
from payments.real_provider import RealCircleProvider
from payments.service import PaymentService, PaymentServiceConfig, demo_events

__all__ = [
    "AgentDecision",
    "EventType",
    "FleetEvent",
    "FleetPaymentAgent",
    "MockCircleProvider",
    "PaymentIntent",
    "PaymentPolicy",
    "PaymentReceipt",
    "PaymentRequest",
    "PaymentService",
    "PaymentServiceConfig",
    "PaymentStatus",
    "PolicyDecision",
    "Provider",
    "ProviderQuote",
    "ProviderRegistry",
    "ProviderTransfer",
    "RealCircleProvider",
    "ServiceType",
    "SettlementStatus",
    "TransactionRecord",
    "WalletSnapshot",
    "create_payment_provider",
    "demo_events",
]
