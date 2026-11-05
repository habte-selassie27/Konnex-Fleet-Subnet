"""FleetPaymentAgent unit tests — deterministic economic decisions.

The agent is a pure function of (fleet event, provider catalog): the same
battery level + service always yields the same provider choice and amount.
"""

from __future__ import annotations

import pytest

from payments.agent import FleetPaymentAgent
from payments.models import EventType, FleetEvent, ServiceType

AGENT = FleetPaymentAgent("FLEET-017")


def event(
    *,
    event_type: EventType = EventType.CHARGING_REQUIRED,
    vehicle_id: str = "TRUCK-42",
    battery_pct: float = 0.18,
) -> FleetEvent:
    """Default charging event (battery 18% -> urgency 2.0)."""
    return FleetEvent(vehicle_id=vehicle_id, event_type=event_type, battery_pct=battery_pct)


class TestAgentDecisions:
    def test_charging_selects_voltcharge_at_low_battery(self) -> None:
        decision = AGENT.decide(event())
        assert decision.no_action is False
        assert decision.service == ServiceType.CHARGING
        assert decision.selected_provider_id == "prov_charge_a"
        assert decision.amount_usdc == pytest.approx(18.0)

    def test_quotes_are_sorted_by_score_ascending(self) -> None:
        decision = AGENT.decide(event())
        scores = [quote.score for quote in decision.quotes]
        assert scores == sorted(scores)
        assert len(decision.quotes) == 3
        # Lowest score is the cheapest-within-range pick, not necessarily the
        # raw cheapest: ApexGrid ($14) loses to VoltCharge ($18) at high
        # urgency because of the distance penalty.
        assert decision.quotes[0].provider.provider_id == "prov_charge_a"

    def test_rationale_mentions_alternatives(self) -> None:
        decision = AGENT.decide(event())
        assert "VoltCharge" in decision.rationale
        assert "ApexGrid" in decision.rationale
        assert "QuickJuice" in decision.rationale
        assert "Cheapest:" in decision.rationale

    def test_no_action_above_battery_threshold(self) -> None:
        decision = AGENT.decide(event(battery_pct=0.80))
        assert decision.no_action is True
        assert decision.amount_usdc == 0.0
        assert decision.quotes == ()

    def test_maintenance_selects_autoservicex(self) -> None:
        decision = AGENT.decide(event(event_type=EventType.MAINTENANCE_REQUIRED, battery_pct=0.62))
        assert decision.service == ServiceType.MAINTENANCE
        assert decision.selected_provider_id == "prov_maint_b"
        assert decision.amount_usdc == pytest.approx(62.0)

    def test_fueling_selects_petrodirect(self) -> None:
        decision = AGENT.decide(event(event_type=EventType.FUELING_REQUIRED))
        assert decision.service == ServiceType.FUELING
        assert decision.selected_provider_id == "prov_fuel_b"
        assert decision.amount_usdc == pytest.approx(95.0)

    def test_decision_is_deterministic(self) -> None:
        first = AGENT.decide(event())
        second = AGENT.decide(event())
        # Timestamps differ between calls — the economic outcome must not.
        assert first.selected_provider_id == second.selected_provider_id
        assert first.amount_usdc == second.amount_usdc
        assert first.rationale == second.rationale
        assert [q.score for q in first.quotes] == [q.score for q in second.quotes]
