"""Shared pytest fixtures (TESTING_PLAN.md §11).

Status: COMPLETE (Phase 5/6).
"""

import os
from dataclasses import replace

import pytest

# ─── Test isolation: never let a test spend real money ───────────────────────
# ``Settings`` reads ``.env``, so a developer checkout configured with
# ``PAYMENT_PROVIDER=real`` + funded Circle credentials would make the payment
# tests execute live USDC transfers on Arc testnet. Environment variables take
# precedence over the ``.env`` file, so pinning the provider here guarantees
# every test runs against ``MockCircleProvider`` regardless of local config.
# (Observed before this guard: a ``test_payment_bridge`` run broadcast a real
# Circle transfer and settled it on Arc.)
os.environ["PAYMENT_PROVIDER"] = "mock"

from robotics.models.robot_state import CommState, NavState, RobotState, Vector2D
from simulation.scenarios.scenario_generator import Scenario, ScenarioGenerator
from validator.scoring.engine import PoPWScoringEngine


@pytest.fixture
def mock_robot_state() -> RobotState:
    """A single default robot state."""
    return RobotState(
        id="robot_0",
        position=Vector2D(x=0.0, y=0.0),
        orientation=0.0,
        velocity=Vector2D(x=0.0, y=0.0),
        battery_pct=1.0,
        nav_state=NavState.IDLE,
        comm_state=CommState.ONLINE,
    )


@pytest.fixture
def mock_fleet(mock_robot_state: RobotState) -> list[RobotState]:
    """Five robots spaced 2 m apart."""
    return [
        replace(mock_robot_state, id=f"robot_{i}", position=Vector2D(x=float(i * 2), y=0.0))
        for i in range(5)
    ]


@pytest.fixture
def simple_scenario() -> Scenario:
    """A deterministic 5-robot / 10-task scenario (seed 42)."""
    return ScenarioGenerator().generate(seed=42, robot_count=5, task_count=10)


@pytest.fixture
def scoring_engine() -> PoPWScoringEngine:
    """Default PoPW scoring engine."""
    return PoPWScoringEngine()
