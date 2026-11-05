"""FleetPaymentAgent — deterministic economic decision maker.

The agent turns a FleetEvent into a structured AgentDecision:

    1. observe: normalize the event (urgency from battery level)
    2. evaluate: score every provider (price + distance penalty - rating bonus)
    3. decide: pick the lowest-score provider and explain the choice

There is NO LLM here. The agent is a deterministic, seeded function of its
inputs — exactly what the spec asks for: the "AI" makes an economic decision
that is auditable and reproducible. A future LLM policy can replace
`decide()` behind the same interface without touching the policy/wallet
layers (docs/payments.md §Agent).
"""

from __future__ import annotations

from payments.models import (
    AgentDecision,
    EventType,
    FleetEvent,
    Provider,
    ProviderQuote,
    ServiceType,
)
from payments.providers import ProviderRegistry

# Utility weights (deterministic — documented in docs/payments.md §Agent).
_DISTANCE_COST_PER_KM = 0.5
_RATING_BONUS = 0.2

# battery fraction below which the urgency multiplier applies.
_URGENCY_STEPS: tuple[tuple[float, float], ...] = (
    (0.25, 2.0),  # critical: range-constrained, distance matters a lot
    (0.50, 1.0),
    (1.01, 0.5),  # healthy: cheap is king
)

_EVENT_TO_SERVICE: dict[EventType, ServiceType] = {
    EventType.CHARGING_REQUIRED: ServiceType.CHARGING,
    EventType.FUELING_REQUIRED: ServiceType.FUELING,
    EventType.MAINTENANCE_REQUIRED: ServiceType.MAINTENANCE,
    EventType.INSPECTION_DUE: ServiceType.INSPECTION,
}

# Above this battery level the agent takes no action for charging events.
_NO_ACTION_BATTERY = 0.30


class FleetPaymentAgent:
    """Deterministic agent that turns fleet events into provider decisions."""

    def __init__(self, fleet_id: str, registry: ProviderRegistry | None = None) -> None:
        self._fleet_id = fleet_id
        self._registry = registry or ProviderRegistry()

    def decide(self, event: FleetEvent) -> AgentDecision:
        """Observe a fleet event and return the agent's economic decision."""
        service = _EVENT_TO_SERVICE[event.event_type]
        providers = self._registry.by_service(service)

        if (
            event.event_type == EventType.CHARGING_REQUIRED
            and event.battery_pct > _NO_ACTION_BATTERY
        ):
            return AgentDecision(
                fleet_id=self._fleet_id,
                vehicle_id=event.vehicle_id,
                service=service,
                quotes=(),
                selected_provider_id="",
                amount_usdc=0.0,
                rationale=(
                    f"Battery at {event.battery_pct:.0%} — above the "
                    f"{_NO_ACTION_BATTERY:.0%} threshold, no charging needed."
                ),
                no_action=True,
                event_type=event.event_type,
                battery_pct=event.battery_pct,
                note=event.note,
            )

        if not providers:
            return AgentDecision(
                fleet_id=self._fleet_id,
                vehicle_id=event.vehicle_id,
                service=service,
                quotes=(),
                selected_provider_id="",
                amount_usdc=0.0,
                rationale="No providers available for this service — no action taken.",
                no_action=True,
                event_type=event.event_type,
                battery_pct=event.battery_pct,
                note=event.note,
            )

        urgency = next(
            multiplier for threshold, multiplier in _URGENCY_STEPS if event.battery_pct < threshold
        )
        quotes = [
            ProviderQuote(provider=provider, score=round(self._score(provider, urgency), 2))
            for provider in providers
        ]
        quotes.sort(key=lambda quote: quote.score)
        selected = quotes[0]

        return AgentDecision(
            fleet_id=self._fleet_id,
            vehicle_id=event.vehicle_id,
            service=service,
            quotes=tuple(quotes),
            selected_provider_id=selected.provider.provider_id,
            amount_usdc=round(selected.provider.price_usdc, 2),
            rationale=self._rationale(event, quotes, selected, urgency),
            event_type=event.event_type,
            battery_pct=event.battery_pct,
            note=event.note,
        )

    def _score(self, provider: Provider, urgency: float) -> float:
        """Lower is better: price + distance penalty - rating bonus."""
        distance_penalty = _DISTANCE_COST_PER_KM * urgency * provider.distance_km
        rating_bonus = _RATING_BONUS * provider.rating
        return provider.price_usdc + distance_penalty - rating_bonus

    @staticmethod
    def _rationale(
        event: FleetEvent,
        quotes: list[ProviderQuote],
        selected: ProviderQuote,
        urgency: float,
    ) -> str:
        cheapest = min(quotes, key=lambda quote: quote.provider.price_usdc)
        closest = min(quotes, key=lambda quote: quote.provider.distance_km)
        rated = max(quotes, key=lambda quote: quote.provider.rating)
        return (
            f"Battery {event.battery_pct:.0%} (urgency {urgency:.1f}). "
            f"Cheapest: {cheapest.provider.name} (${cheapest.provider.price_usdc:.2f}); "
            f"closest: {closest.provider.name} ({closest.provider.distance_km:.1f} km); "
            f"highest rated: {rated.provider.name} ({rated.provider.rating:.1f}). "
            f"Selected {selected.provider.name} — utility score {selected.score:.2f} "
            f"balances price, distance, and rating."
        )
