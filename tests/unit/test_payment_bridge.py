"""FleetPaymentBridge tests — live fleet telemetry -> policy-gated payments.

Two layers are covered:
  * stubbed fleet state for the classification/episode logic (arming,
    de-duplication, recovery, mission changes),
  * the real FleetAppState + orchestrator for the failure-injection path,
    proving a genuinely reported robot failure becomes a persisted payment.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

from backend.config import Settings
from backend.db.database import Database
from backend.services.fleet_payment_bridge import FleetPaymentBridge
from backend.services.fleet_service import FleetAppState
from backend.services.payment_service import PaymentAppState
from payments.models import EventType
from robotics.models.failure import FailureType
from robotics.models.fleet_state import FleetState
from robotics.models.robot_state import NavState, RobotState, Vector2D


def _settings(tmp_path: Path, name: str = "bridge.db", **overrides: object) -> Settings:
    """Test settings pointing at a throwaway SQLite DB (bridge disabled)."""
    values: dict[str, object] = {
        "database_url": f"sqlite+aiosqlite:///{tmp_path}/{name}",
        "artifact_dir": tmp_path / "artifacts",
        "payment_live_bridge": False,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _robot(
    robot_id: str,
    *,
    battery: float = 0.9,
    nav_state: NavState = NavState.IDLE,
) -> RobotState:
    return RobotState(
        id=robot_id,
        position=Vector2D(1.0, 2.0),
        battery_pct=battery,
        nav_state=nav_state,
    )


def _state(robots: list[RobotState], mission_id: str | None = "mission-1") -> FleetState:
    return FleetState(
        robots=robots,
        active_tasks=[],
        mission_id=mission_id,
        mission_status="running" if mission_id else "none",
    )


class _StubOrchestrator:
    """Returns a mutable FleetState snapshot (tests edit it in place)."""

    def __init__(self, state: FleetState) -> None:
        self.state = state

    def get_fleet_state(self) -> FleetState:
        return self.state


class _StubFleet:
    def __init__(self, state: FleetState) -> None:
        self.orchestrator = _StubOrchestrator(state)


async def _open_payments(
    tmp_path: Path,
    name: str = "bridge.db",
) -> tuple[PaymentAppState, Database]:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/{name}")
    await db.create_all()
    return PaymentAppState(db, _settings(tmp_path, name)), db


def test_low_battery_pays_once_per_episode(tmp_path: Path) -> None:
    async def scenario() -> None:
        payments, db = await _open_payments(tmp_path)
        settings = _settings(tmp_path)
        state = _state([_robot("robot_0", battery=0.15)])
        bridge = FleetPaymentBridge(cast(FleetAppState, _StubFleet(state)), payments, settings)

        await bridge.tick()
        transactions = await payments.list_transactions()
        assert len(transactions) == 1
        assert transactions[0].vehicle_id == "robot_0"
        assert transactions[0].service == "charging"
        assert transactions[0].is_mock is True
        assert bridge.armed == {"robot_0": EventType.CHARGING_REQUIRED}

        # Same low-battery episode — no duplicate payment.
        await bridge.tick()
        assert len(await payments.list_transactions()) == 1

        # Recovery closes the episode; a later drop pays again.
        state.robots[0].battery_pct = 0.9
        await bridge.tick()
        assert bridge.armed == {}
        state.robots[0].battery_pct = 0.12
        await bridge.tick()
        assert len(await payments.list_transactions()) == 2
        await db.dispose()

    asyncio.run(scenario())


def test_healthy_fleet_generates_no_payments(tmp_path: Path) -> None:
    async def scenario() -> None:
        payments, db = await _open_payments(tmp_path)
        settings = _settings(tmp_path)
        state = _state([_robot("robot_0", battery=0.9), _robot("robot_1", battery=0.65)])
        bridge = FleetPaymentBridge(cast(FleetAppState, _StubFleet(state)), payments, settings)

        await bridge.tick()
        assert await payments.list_transactions() == []
        assert bridge.armed == {}
        await db.dispose()

    asyncio.run(scenario())


def test_failed_robot_generates_a_maintenance_payment(tmp_path: Path) -> None:
    async def scenario() -> None:
        payments, db = await _open_payments(tmp_path)
        settings = _settings(tmp_path)
        state = _state([_robot("robot_0", nav_state=NavState.FAILED)])
        bridge = FleetPaymentBridge(cast(FleetAppState, _StubFleet(state)), payments, settings)

        await bridge.tick()
        transactions = await payments.list_transactions()
        assert len(transactions) == 1
        assert transactions[0].vehicle_id == "robot_0"
        assert transactions[0].service == "maintenance"
        assert transactions[0].status == "settled"
        await db.dispose()

    asyncio.run(scenario())


def test_new_mission_reopens_the_payment_episode(tmp_path: Path) -> None:
    async def scenario() -> None:
        payments, db = await _open_payments(tmp_path)
        settings = _settings(tmp_path)
        state = _state([_robot("robot_0", nav_state=NavState.FAILED)], mission_id="mission-1")
        bridge = FleetPaymentBridge(cast(FleetAppState, _StubFleet(state)), payments, settings)

        await bridge.tick()
        assert len(await payments.list_transactions()) == 1

        # A new mission must not inherit the previous mission's arming state.
        state.mission_id = "mission-2"
        await bridge.tick()
        assert len(await payments.list_transactions()) == 2
        await db.dispose()

    asyncio.run(scenario())


def test_no_mission_means_no_payments(tmp_path: Path) -> None:
    async def scenario() -> None:
        payments, db = await _open_payments(tmp_path)
        settings = _settings(tmp_path)
        state = _state([_robot("robot_0", battery=0.05)], mission_id=None)
        bridge = FleetPaymentBridge(cast(FleetAppState, _StubFleet(state)), payments, settings)

        await bridge.tick()
        assert await payments.list_transactions() == []
        assert bridge.armed == {}
        await db.dispose()

    asyncio.run(scenario())


def test_real_orchestrator_failure_becomes_a_persisted_payment(tmp_path: Path) -> None:
    """End-to-end: injected robot failure -> agent decision -> DB transaction."""

    async def scenario() -> None:
        settings = _settings(tmp_path, name="real_fleet.db")
        db = Database(settings.database_url)
        await db.create_all()
        payments = PaymentAppState(db, settings)

        fleet = FleetAppState(settings)
        fleet.configure()  # builds the deterministic 5-robot mission (no loop)
        assert fleet.orchestrator.inject_failure("robot_1", FailureType.NAVIGATION_FAILURE)

        bridge = FleetPaymentBridge(fleet, payments, settings)
        await bridge.tick()

        transactions = await payments.list_transactions()
        assert len(transactions) == 1
        assert transactions[0].vehicle_id == "robot_1"
        assert transactions[0].service == "maintenance"
        assert transactions[0].tx_hash.startswith("0xMOCK")
        assert bridge.armed == {"robot_1": EventType.MAINTENANCE_REQUIRED}
        await db.dispose()

    asyncio.run(scenario())


def test_start_and_stop_lifecycle(tmp_path: Path) -> None:
    async def scenario() -> None:
        payments, db = await _open_payments(tmp_path)
        settings = _settings(tmp_path, payment_bridge_interval_s=0.2)
        state = _state([_robot("robot_0")])
        bridge = FleetPaymentBridge(cast(FleetAppState, _StubFleet(state)), payments, settings)

        assert bridge.running is False
        await bridge.start()
        assert bridge.running is True
        await bridge.start()  # idempotent
        assert bridge.running is True
        await bridge.stop()
        assert bridge.running is False
        await db.dispose()

    asyncio.run(scenario())
