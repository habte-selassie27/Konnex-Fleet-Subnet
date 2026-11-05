"""PaymentService flow tests — the full agentic payment loop.

Covers: quote -> authorize -> execute -> settle -> receipt, mock-labeling of
hashes/explorer URLs, policy rejection paths, wallet/budget accounting, and
the deterministic end-to-end demo scenario (spec §9).
"""

from __future__ import annotations

import pytest

from payments.factory import create_payment_provider
from payments.models import (
    EventType,
    FleetEvent,
    PaymentRequest,
    PaymentStatus,
    ServiceType,
)
from payments.service import PaymentService, PaymentServiceConfig


@pytest.fixture
def service() -> PaymentService:
    """A PaymentService wired to the mock Circle/Arc provider."""
    provider = create_payment_provider("mock")
    assert provider is not None
    return PaymentService(PaymentServiceConfig(), provider)


def _charging_request(
    *,
    amount_usdc: float = 18.0,
    reason: str = "battery below 20%",
    provider_id: str = "prov_charge_a",
    max_allowed_usdc: float = 250.0,
) -> PaymentRequest:
    return PaymentRequest(
        fleet_id="FLEET-017",
        vehicle_id="TRUCK-42",
        provider_id=provider_id,
        service=ServiceType.CHARGING,
        amount_usdc=amount_usdc,
        reason=reason,
        max_allowed_usdc=max_allowed_usdc,
        decision_rationale="cheapest within range",
    )


class TestPaymentFlow:
    def test_quote_authorize_execute_settle(self, service: PaymentService) -> None:
        decision = service.quote(
            FleetEvent(
                vehicle_id="TRUCK-42",
                event_type=EventType.CHARGING_REQUIRED,
                battery_pct=0.18,
            )
        )
        assert decision.selected is not None

        intent, policy_decision = service.authorize(_charging_request())
        assert policy_decision.approved is True
        assert intent.status == PaymentStatus.AUTHORIZED

        record = service.execute(intent.id)
        assert record.status == PaymentStatus.SETTLED
        assert record.settlement_status.value == "settled"
        assert record.amount_usdc == pytest.approx(18.0)
        # Mock-labeled artifacts — never mistaken for real on-chain data.
        assert record.tx_hash.startswith("0xMOCK")
        assert record.is_mock is True
        assert record.explorer_url.startswith("https://mock-explorer.arc.local/")

        receipt = service.get_receipt(record.id)
        assert receipt is not None
        assert receipt.is_mock is True
        assert receipt.tx_hash == record.tx_hash

    def test_wallet_accounting_after_payment(self, service: PaymentService) -> None:
        intent, decision = service.authorize(_charging_request())
        assert decision.approved
        service.execute(intent.id)

        wallet = service.wallet()
        assert wallet.spent_today_usdc == pytest.approx(18.0)
        assert wallet.remaining_today_usdc == pytest.approx(482.0)
        assert wallet.balance_usdc == pytest.approx(982.0)

        assert service.summary().autonomous_payments == 1
        assert service.summary().usdc_settled == pytest.approx(18.0)

    def test_execute_unknown_intent_raises(self, service: PaymentService) -> None:
        with pytest.raises(KeyError):
            service.execute("no-such-intent")

    def test_execute_rejected_intent_raises(self, service: PaymentService) -> None:
        intent, decision = service.authorize(
            _charging_request(amount_usdc=600.0, max_allowed_usdc=250.0)
        )
        assert decision.approved is False
        assert intent.status == PaymentStatus.REJECTED
        with pytest.raises(ValueError):
            service.execute(intent.id)

    def test_policy_rejects_over_max_tx(self, service: PaymentService) -> None:
        # $300 exceeds the $250 max-tx limit but stays under the $500 budget,
        # isolating the max_tx check from the daily-budget check.
        intent, decision = service.authorize(
            _charging_request(amount_usdc=300.0, max_allowed_usdc=250.0)
        )
        assert decision.approved is False
        assert decision.checks["max_tx_limit"] is False
        assert decision.checks["daily_budget"] is True

    def test_execute_rechecks_budget_tooctu(self, service: PaymentService) -> None:
        """Authorize passes while funds remain, but execution re-validates the
        current wallet and refuses once the daily budget is exhausted."""
        # 4 x $125 = $500: the full daily budget.
        intent_ids: list[str] = []
        for _ in range(4):
            intent, decision = service.authorize(
                _charging_request(amount_usdc=125.0, max_allowed_usdc=250.0)
            )
            assert decision.approved
            intent_ids.append(intent.id)
        # A 5th intent is authorized while spent == 0 (policy sees a fresh
        # wallet) …
        late_intent, late_decision = service.authorize(
            _charging_request(amount_usdc=100.0, max_allowed_usdc=250.0)
        )
        assert late_decision.approved
        # … but executing the first four drains the budget, so executing the
        # late one is refused by the execution-time re-check.
        for intent_id in intent_ids:
            service.execute(intent_id)
        with pytest.raises(ValueError, match="no longer authorized"):
            service.execute(late_intent.id)

    def test_daily_budget_blocks_further_payments(self, service: PaymentService) -> None:
        # 5 x $100 = the full $500 daily budget.
        for _ in range(5):
            intent, decision = service.authorize(
                _charging_request(amount_usdc=100.0, max_allowed_usdc=250.0)
            )
            assert decision.approved
            service.execute(intent.id)

        intent, decision = service.authorize(
            _charging_request(amount_usdc=100.0, max_allowed_usdc=250.0)
        )
        assert decision.approved is False
        assert decision.checks["daily_budget"] is False
        assert "daily budget" in decision.reasons[0]

    def test_transactions_list_newest_first(self, service: PaymentService) -> None:
        for amount in (18.0, 62.0, 95.0):
            intent, decision = service.authorize(
                _charging_request(amount_usdc=amount, max_allowed_usdc=250.0)
            )
            assert decision.approved
            service.execute(intent.id)
        records = service.list_transactions()
        assert [record.amount_usdc for record in records] == [95.0, 62.0, 18.0]


class TestDemoScenario:
    def test_demo_settles_three_payments(self, service: PaymentService) -> None:
        run = service.run_demo_scenario(reset=True)
        assert len(run.decisions) == 3
        assert len(run.transactions) == 3
        assert run.summary.usdc_settled == pytest.approx(175.0)
        assert run.summary.autonomous_payments == 3
        assert run.summary.arc_transactions == 3
        assert run.summary.receipts == 3

    def test_demo_wallet_accounting(self, service: PaymentService) -> None:
        run = service.run_demo_scenario(reset=True)
        wallet = run.summary.wallet
        assert wallet.spent_today_usdc == pytest.approx(175.0)
        assert wallet.remaining_today_usdc == pytest.approx(325.0)
        assert wallet.balance_usdc == pytest.approx(825.0)
        assert wallet.is_mock is True

    def test_demo_providers_and_amounts(self, service: PaymentService) -> None:
        run = service.run_demo_scenario(reset=True)
        providers = {record.provider_id for record in run.transactions}
        assert providers == {"prov_charge_a", "prov_maint_b", "prov_fuel_b"}
        amounts = sorted(record.amount_usdc for record in run.transactions)
        assert amounts == [18.0, 62.0, 95.0]

    def test_demo_is_repeatable_and_clean(self, service: PaymentService) -> None:
        first = service.run_demo_scenario(reset=True)
        second = service.run_demo_scenario(reset=True)
        assert first.summary.usdc_settled == second.summary.usdc_settled == 175.0
        # Each run starts from a fresh $1000 wallet.
        assert second.summary.wallet.balance_usdc == pytest.approx(825.0)
