"""PaymentPolicy unit tests — deterministic guardrails (spec §6).

Covers: currency, positive amount, max_allowed, max-tx limit, daily budget,
wallet balance, provider allowlist, address validation, reason, and service
validation — plus the per-check `checks` map the dashboard renders.
"""

from __future__ import annotations

import pytest

from payments.models import PaymentRequest, Provider, ServiceType, WalletSnapshot
from payments.policy import PaymentPolicy, PolicyLimits
from payments.providers import ProviderRegistry

BUDGET = 500.0
MAX_TX = 250.0


@pytest.fixture
def policy() -> PaymentPolicy:
    """Default policy with a $500 daily budget and $250 max-tx limit."""
    return PaymentPolicy(PolicyLimits(daily_budget_usdc=BUDGET, max_tx_usdc=MAX_TX))


@pytest.fixture
def provider() -> Provider:
    """A known catalog provider (VoltCharge)."""
    provider = ProviderRegistry().get("prov_charge_a")
    assert provider is not None
    return provider


def wallet(*, spent: float = 0.0, balance: float = 1000.0) -> WalletSnapshot:
    """Build a wallet snapshot for the default budget."""
    return WalletSnapshot(
        wallet_id="fleet-agent-wallet-001",
        currency="USDC",
        balance_usdc=balance,
        daily_budget_usdc=BUDGET,
        spent_today_usdc=spent,
        remaining_today_usdc=round(max(0.0, BUDGET - spent), 2),
        max_tx_usdc=MAX_TX,
        is_mock=True,
    )


def request(
    *,
    provider_id: str = "prov_charge_a",
    service: ServiceType = ServiceType.CHARGING,
    amount_usdc: float = 18.0,
    currency: str = "USDC",
    reason: str = "battery below 20%",
    max_allowed_usdc: float = MAX_TX,
) -> PaymentRequest:
    """Build a well-formed payment request (overridable per test)."""
    return PaymentRequest(
        fleet_id="FLEET-017",
        vehicle_id="TRUCK-42",
        provider_id=provider_id,
        service=service,
        amount_usdc=amount_usdc,
        currency=currency,
        reason=reason,
        max_allowed_usdc=max_allowed_usdc,
        decision_rationale="cheapest provider within range",
    )


class TestPaymentPolicyApproval:
    def test_approves_valid_request(self, policy: PaymentPolicy, provider: Provider) -> None:
        decision = policy.validate(request(), wallet(), provider=provider)
        assert decision.approved is True
        assert decision.reasons == []
        assert all(decision.checks.values())

    def test_every_check_is_reported(self, policy: PaymentPolicy, provider: Provider) -> None:
        decision = policy.validate(request(), wallet(), provider=provider)
        expected = {
            "currency",
            "amount_positive",
            "max_allowed",
            "max_tx_limit",
            "daily_budget",
            "wallet_balance",
            "reason_present",
            "service_known",
            "provider_known",
            "provider_address",
        }
        assert set(decision.checks) == expected


class TestPaymentPolicyRejections:
    def test_rejects_non_usdc_currency(self, policy: PaymentPolicy, provider: Provider) -> None:
        decision = policy.validate(request(currency="EUR"), wallet(), provider=provider)
        assert decision.approved is False
        assert decision.checks["currency"] is False

    def test_rejects_zero_amount(self, policy: PaymentPolicy, provider: Provider) -> None:
        decision = policy.validate(request(amount_usdc=0.0), wallet(), provider=provider)
        assert decision.approved is False
        assert decision.checks["amount_positive"] is False

    def test_rejects_over_max_allowed(self, policy: PaymentPolicy, provider: Provider) -> None:
        decision = policy.validate(
            request(amount_usdc=50.0, max_allowed_usdc=25.0), wallet(), provider=provider
        )
        assert decision.approved is False
        assert decision.checks["max_allowed"] is False

    def test_rejects_over_max_tx_limit(self, policy: PaymentPolicy, provider: Provider) -> None:
        decision = policy.validate(request(amount_usdc=MAX_TX + 1.0), wallet(), provider=provider)
        assert decision.approved is False
        assert decision.checks["max_tx_limit"] is False

    def test_rejects_over_daily_budget(self, policy: PaymentPolicy, provider: Provider) -> None:
        decision = policy.validate(
            request(amount_usdc=100.0), wallet(spent=450.0), provider=provider
        )
        assert decision.approved is False
        assert decision.checks["daily_budget"] is False

    def test_allows_exactly_at_daily_budget(
        self, policy: PaymentPolicy, provider: Provider
    ) -> None:
        decision = policy.validate(
            request(amount_usdc=50.0), wallet(spent=450.0), provider=provider
        )
        assert decision.approved is True

    def test_rejects_over_wallet_balance(self, policy: PaymentPolicy, provider: Provider) -> None:
        decision = policy.validate(
            request(amount_usdc=100.0), wallet(balance=50.0), provider=provider
        )
        assert decision.approved is False
        assert decision.checks["wallet_balance"] is False

    def test_rejects_empty_reason(self, policy: PaymentPolicy, provider: Provider) -> None:
        decision = policy.validate(request(reason="  "), wallet(), provider=provider)
        assert decision.approved is False
        assert decision.checks["reason_present"] is False

    def test_rejects_unknown_provider(self, policy: PaymentPolicy) -> None:
        decision = policy.validate(request(provider_id="prov_ghost"), wallet(), provider=None)
        assert decision.approved is False
        assert decision.checks["provider_known"] is False

    def test_rejects_invalid_provider_address(
        self, policy: PaymentPolicy, provider: Provider
    ) -> None:
        bad_address = Provider(
            provider_id=provider.provider_id,
            name=provider.name,
            service=provider.service,
            price_usdc=provider.price_usdc,
            distance_km=provider.distance_km,
            rating=provider.rating,
            address="0xnot-a-valid-address",
        )
        decision = policy.validate(request(), wallet(), provider=bad_address)
        assert decision.approved is False
        assert decision.checks["provider_address"] is False

    def test_reject_reports_all_failures(self, policy: PaymentPolicy, provider: Provider) -> None:
        """A multi-failure request lists every failing check."""
        decision = policy.validate(
            request(amount_usdc=0.0, reason=" "), wallet(), provider=provider
        )
        assert decision.approved is False
        assert decision.checks["amount_positive"] is False
        assert decision.checks["reason_present"] is False
        assert len(decision.reasons) >= 2
