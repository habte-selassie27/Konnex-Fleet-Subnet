"""Deterministic provider catalog for the agentic payment layer.

Providers are static demo entities (charging / fueling / maintenance /
inspection stations) with prices, distances, ratings, and wallet addresses.
Addresses are valid 0x + 40-hex strings derived deterministically from the
provider id, so the policy's address validation exercises the real code path.

There is no network access — this is the catalog the agent reasons over in
demo mode. A production deployment would replace it with a live marketplace
API behind the same Provider shape.

Status: COMPLETE (demo catalog).
"""

from __future__ import annotations

import hashlib

from payments.models import Provider, ServiceType

# service -> tuple of (provider_id, name, price_usdc, distance_km, rating)
_CATALOG: dict[ServiceType, tuple[tuple[str, str, float, float, float], ...]] = {
    ServiceType.CHARGING: (
        ("prov_charge_a", "VoltCharge", 18.00, 3.0, 4.8),
        ("prov_charge_b", "ApexGrid", 14.00, 8.0, 4.5),
        ("prov_charge_c", "QuickJuice", 21.00, 2.0, 4.9),
    ),
    ServiceType.FUELING: (
        ("prov_fuel_a", "FuelHub", 120.00, 2.0, 4.6),
        ("prov_fuel_b", "PetroDirect", 95.00, 6.0, 4.2),
        ("prov_fuel_c", "TankPro", 110.00, 4.0, 4.7),
    ),
    ServiceType.MAINTENANCE: (
        ("prov_maint_a", "FleetCare", 75.00, 1.0, 4.9),
        ("prov_maint_b", "AutoServiceX", 62.00, 5.0, 4.4),
        ("prov_maint_c", "PrecisionWrench", 85.00, 3.0, 4.8),
    ),
    ServiceType.INSPECTION: (
        ("prov_insp_a", "SafeCheck", 45.00, 1.5, 4.7),
        ("prov_insp_b", "InspectNow", 38.00, 4.0, 4.3),
        ("prov_insp_c", "CertiScan", 52.00, 2.5, 4.8),
    ),
}


def _address_for(provider_id: str) -> str:
    """Deterministic valid-looking 0x address derived from the provider id."""
    return "0x" + hashlib.sha256(provider_id.encode()).hexdigest()[:40]


class ProviderRegistry:
    """Deterministic provider catalog keyed by service type."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}
        for service, rows in _CATALOG.items():
            for provider_id, name, price_usdc, distance_km, rating in rows:
                provider = Provider(
                    provider_id=provider_id,
                    name=name,
                    service=service,
                    price_usdc=price_usdc,
                    distance_km=distance_km,
                    rating=rating,
                    address=_address_for(provider_id),
                )
                self._providers[provider_id] = provider

    def by_service(self, service: ServiceType) -> list[Provider]:
        """All providers offering `service`, in catalog order."""
        return [provider for provider in self._providers.values() if provider.service == service]

    def get(self, provider_id: str) -> Provider | None:
        """Look up a provider by id, or None when unknown."""
        return self._providers.get(provider_id)

    def count(self) -> int:
        """Total number of providers in the catalog."""
        return len(self._providers)
