"""Deterministic payment-policy engine.

The policy sits BETWEEN the AI agent and any wallet/chain interaction
(spec §6, AGENTS.md Law 2). It is pure and deterministic — no randomness, no
LLM — and enforces:

    - currency must be USDC
    - amount > 0 (rounded to cents)
    - amount <= the request's max_allowed
    - amount <= the maximum transaction limit (config)
    - today's spend + amount <= the daily budget (config)
    - amount <= the wallet balance
    - provider is known and its address is a valid 0x + 40-hex address
    - reason present, service known

Any failed check rejects the intent outright; the reject reasons and the
per-check booleans are returned so the dashboard can show exactly why a
payment was (or was not) approved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from payments.models import PaymentRequest, Provider, ServiceType, WalletSnapshot

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class PolicyLimits:
    """Configurable policy limits (env-driven from backend settings)."""

    daily_budget_usdc: float = 500.0
    max_tx_usdc: float = 250.0


@dataclass(frozen=True)
class PolicyDecision:
    """Outcome of the policy engine for one payment request."""

    approved: bool
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)


class PaymentPolicy:
    """Deterministic gatekeeper for agent-generated payment requests."""

    def __init__(self, limits: PolicyLimits | None = None) -> None:
        self._limits = limits or PolicyLimits()

    @property
    def limits(self) -> PolicyLimits:
        """The active policy limits."""
        return self._limits

    def validate(
        self,
        request: PaymentRequest,
        wallet: WalletSnapshot,
        *,
        provider: Provider | None,
    ) -> PolicyDecision:
        """Validate a structured payment request. Returns a PolicyDecision.

        Args:
            request: The agent-generated payment request.
            wallet: Current agent wallet snapshot (balance + limits + spend).
            provider: The resolved provider from the registry (None = unknown).
        """
        checks: dict[str, bool] = {}
        failures: list[str] = []
        amount = round(request.amount_usdc, 2)

        def check(name: str, passed: bool, message: str) -> None:
            checks[name] = passed
            if not passed:
                failures.append(message)

        check(
            "currency",
            request.currency.upper() == "USDC",
            f"currency must be USDC, got {request.currency!r}",
        )
        check("amount_positive", amount > 0.0, f"amount must be > 0, got {request.amount_usdc}")
        check(
            "max_allowed",
            amount <= request.max_allowed_usdc,
            f"amount {amount} exceeds max_allowed {request.max_allowed_usdc}",
        )
        check(
            "max_tx_limit",
            amount <= self._limits.max_tx_usdc,
            f"amount {amount} exceeds max transaction limit {self._limits.max_tx_usdc}",
        )
        check(
            "daily_budget",
            round(wallet.spent_today_usdc + amount, 2) <= wallet.daily_budget_usdc,
            f"spent {wallet.spent_today_usdc} + {amount} exceeds daily budget "
            f"{wallet.daily_budget_usdc}",
        )
        check(
            "wallet_balance",
            amount <= wallet.balance_usdc,
            f"amount {amount} exceeds wallet balance {wallet.balance_usdc}",
        )
        check("reason_present", bool(request.reason.strip()), "reason must not be empty")
        check(
            "service_known",
            request.service in ServiceType,
            f"unknown service {request.service!r}",
        )
        check("provider_known", provider is not None, f"provider {request.provider_id!r} not found")
        if provider is not None:
            check(
                "provider_address",
                bool(_ADDRESS_RE.match(provider.address)),
                f"invalid provider address {provider.address!r}",
            )

        return PolicyDecision(approved=not failures, reasons=failures, checks=checks)
