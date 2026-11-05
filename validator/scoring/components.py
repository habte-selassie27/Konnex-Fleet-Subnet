"""Individual PoPW score components.

Status: COMPLETE (Phase 7 prototype formula, implemented in Phase 6).
All components are normalized to [0, 1] (TESTING_PLAN.md §3.4).
"""


def coordination_score(collisions: int, tasks_total: int) -> float:
    """Coordination component — penalizes collisions per task.

    1.0 with zero collisions; decreases toward 0.0 as collisions approach the
    task count. Prototype formula (PLAN.md §8) — adapt to the Konnex SDK after
    Phase 8 research.
    """
    if tasks_total <= 0:
        return 1.0
    return max(0.0, 1.0 - min(1.0, collisions / tasks_total))


def robustness_score(mission_success: float, failure_count: int) -> float:
    """Robustness component — performance under failure conditions.

    With no failures the fleet performed nominally, so the component is 1.0;
    under failures it reflects how well the fleet still completed its work.
    """
    if failure_count == 0:
        return 1.0
    return max(0.0, min(1.0, mission_success))
