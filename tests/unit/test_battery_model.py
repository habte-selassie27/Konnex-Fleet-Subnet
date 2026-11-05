"""Battery model unit tests (TESTING_PLAN.md §3.3).

Status: COMPLETE (Phase 5).
"""

from robotics.battery.battery_model import BatteryModel


class TestBatteryModel:
    def test_drains_during_movement(self) -> None:
        battery = BatteryModel()
        battery.drain(10.0, moving=True)
        assert battery.charge_pct < 1.0

    def test_drains_slower_when_idle(self) -> None:
        moving = BatteryModel()
        idle = BatteryModel()
        moving.drain(10.0, moving=True)
        idle.drain(10.0, moving=False)
        assert moving.charge_pct < idle.charge_pct

    def test_never_goes_below_zero(self) -> None:
        battery = BatteryModel(initial_pct=0.01)
        consumed = battery.drain(100.0, moving=True)
        assert battery.charge_pct == 0.0
        assert consumed <= 0.01 * battery.capacity_units

    def test_charging_restores_energy(self) -> None:
        battery = BatteryModel(initial_pct=0.5)
        battery.charge(25.0)
        assert battery.charge_pct > 0.5
        assert battery.charge_pct <= 1.0

    def test_charging_caps_at_full(self) -> None:
        battery = BatteryModel(initial_pct=0.99)
        battery.charge(500.0)
        assert battery.charge_pct == 1.0
