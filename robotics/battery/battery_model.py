"""Battery model — linear drain + task cost.

Status: COMPLETE (Phase 5 domain layer).
Spec (BUILD.md §4): capacity 100 units; drain 0.1 unit/s moving, 0.02 unit/s idle.
"""


class BatteryModel:
    """Deterministic battery model with linear drain and charging."""

    CAPACITY_UNITS: float = 100.0
    DRAIN_RATE_MOVING: float = 0.1  # units per second
    DRAIN_RATE_IDLE: float = 0.02  # units per second
    CHARGE_RATE_UNITS: float = 1.0  # units per second while charging

    def __init__(self, capacity_units: float = CAPACITY_UNITS, initial_pct: float = 1.0) -> None:
        self._capacity = capacity_units
        self._units = max(0.0, min(1.0, initial_pct)) * capacity_units

    @property
    def capacity_units(self) -> float:
        """Total battery capacity in units."""
        return self._capacity

    @property
    def charge_pct(self) -> float:
        """Current charge as a fraction in [0.0, 1.0]."""
        return self._units / self._capacity

    @property
    def units_consumed(self) -> float:
        """Units consumed since model creation."""
        return self._capacity - self._units

    def drain(self, dt: float, moving: bool) -> float:
        """Drain battery for dt seconds; returns units actually consumed.

        Never drops below zero.
        """
        rate = self.DRAIN_RATE_MOVING if moving else self.DRAIN_RATE_IDLE
        consumed = min(rate * dt, self._units)
        self._units -= consumed
        return consumed

    def charge(self, dt: float) -> float:
        """Charge the battery for dt seconds; returns units added."""
        added = min(self.CHARGE_RATE_UNITS * dt, self._capacity - self._units)
        self._units += added
        return added
