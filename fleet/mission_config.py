"""MissionConfig — mission parameters.

Spec (AGENTS.md §7.1):
    Defines a mission's configuration: seed, robot count, task count,
    time limit, failure injection, etc.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MissionConfig:
    """Configuration for a fleet mission.

    All scenario randomization derives from (scenario_id, seed),
    ensuring deterministic reproduction by any validator.
    """

    mission_id: str = ""
    scenario_id: str = "warehouse_v1"
    seed: int = 42
    robot_count: int = 5
    task_count: int = 20
    obstacle_count: int = 15
    time_limit_s: float = 600.0
    failure_injection: bool = False
    comm_degradation: bool = False
    energy_budget_per_robot: float = 100.0
