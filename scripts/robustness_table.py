#!/usr/bin/env python3
"""Generate robustness table: success rate under each failure mode, per policy.

Usage:
    python scripts/robustness_table.py
Writes experiments/results/robustness_table.md
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from collections.abc import Callable

from fleet.mission_manager import MissionConfig
from fleet.orchestrator import FailurePlan, FleetOrchestrator, MissionOutcome, OrchestratorConfig
from fleet.task_allocator.base import TaskAllocator
from fleet.task_allocator.cost_optimizer import CostOptimizerAllocator
from fleet.task_allocator.hungarian import HungarianAllocator
from fleet.task_allocator.nearest import NearestTaskAllocator
from robotics.models.failure import FailureType

ALLOCATORS: dict[str, Callable[[], TaskAllocator]] = {
    "nearest": NearestTaskAllocator,
    "hungarian": HungarianAllocator,
    "cost_optimizer": CostOptimizerAllocator,
}
BASE_CONFIG = MissionConfig(
    robot_count=5, task_count=10, seed=42, time_limit_s=300.0, scenario_id="warehouse_v1_10tasks"
)
FAILURE_MODES = {
    "none": None,
    "comm_loss": (FailureType.COMMUNICATION_LOSS, 10.0),
    "nav_failure": (FailureType.NAVIGATION_FAILURE, 8.0),
    "shutdown": (FailureType.SHUTDOWN, 5.0),
}


def run(policy_name: str, mode: str) -> MissionOutcome:
    allocator = ALLOCATORS[policy_name]()
    orch = FleetOrchestrator(
        allocator=allocator,
        config=OrchestratorConfig(max_steps=30_000),
    )
    plan = None
    if mode != "none":
        ft, after = FAILURE_MODES[mode]  # type: ignore[misc]
        plan = FailurePlan(robot_id="robot_1", failure_type=ft, after_elapsed_s=after)
    return orch.run_mission(42, BASE_CONFIG, failure_plan=plan)


def main() -> None:
    rows = []
    for policy in ALLOCATORS:
        for mode in FAILURE_MODES:
            outcome = run(policy, mode)
            sr = outcome.tasks_completed / outcome.tasks_total if outcome.tasks_total else 0.0
            rows.append(
                (policy, mode, outcome.status, sr, outcome.collision_count, outcome.elapsed_s)
            )
    lines = [
        "| Policy | Failure mode | Status | Success | Collisions | Time (s) |",
        "|--------|--------------|--------|---------|-----------|----------|",
    ]
    for policy, mode, status, sr, coll, t in rows:
        lines.append(f"| {policy} | {mode} | {status} | {sr:.1%} | {coll} | {t:.1f} |")
    out = Path("experiments/results/robustness_table.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
