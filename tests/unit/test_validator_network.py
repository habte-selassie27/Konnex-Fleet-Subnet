"""Unit tests for the role-based validator network (validator/network.py)."""

from fleet.mission_manager import Mission, MissionStatus
from robotics.models.robot_state import Vector2D
from robotics.models.task import Priority, Task, TaskStatus
from validator.network import (
    VALIDATORS,
    Assessment,
    MissionEvidence,
    reach_consensus,
    verify_mission,
)


def _mission(
    *,
    task_count: int = 20,
    completed: int = 20,
    collisions: int = 0,
    elapsed: float = 135.6,
    energy: float = 18.0,
    status: MissionStatus = MissionStatus.COMPLETE,
    time_limit: float = 600.0,
) -> Mission:
    tasks = [
        Task(
            id=f"task_{i:03d}",
            pickup=Vector2D(1.0, 1.0),
            delivery=Vector2D(2.0, 2.0),
            priority=Priority.MEDIUM,
            status=(
                TaskStatus.COMPLETED if i < completed else TaskStatus.PENDING
            ),
        )
        for i in range(task_count)
    ]
    return Mission(
        scenario_id="warehouse_v1_20tasks",
        seed=42,
        robot_count=5,
        task_count=task_count,
        tasks=tasks,
        completed_tasks=completed,
        collision_count=collisions,
        elapsed_seconds=elapsed,
        energy_consumed=energy,
        time_limit_s=time_limit,
        status=status,
    )


def _verify(mission: Mission):
    evidence = MissionEvidence.from_mission(mission, policy="nearest")
    return verify_mission(evidence)


def test_registry_has_three_distinct_role_validators() -> None:
    assert [spec.role for spec in VALIDATORS] == ["execution", "safety", "performance"]
    assert len({spec.id for spec in VALIDATORS}) == 3


def test_complete_clean_mission_is_accepted() -> None:
    verification = _verify(_mission())

    assert verification.consensus.decision == "ACCEPTED"
    assert verification.consensus.accept_votes == 3
    assert [a.verdict for a in verification.assessments] == ["PASS", "PASS", "PASS"]
    assert all(a.score is not None for a in verification.assessments)


def test_collision_triggers_safety_veto_even_when_mission_completes() -> None:
    verification = _verify(_mission(collisions=2))

    safety = next(a for a in verification.assessments if a.role == "safety")
    execution = next(a for a in verification.assessments if a.role == "execution")

    assert execution.verdict == "PASS"
    assert safety.verdict == "FAIL"
    assert verification.consensus.decision == "REJECTED"
    assert "veto" in verification.consensus.reason.lower()
    # The veto must win even though the other two roles accepted.
    assert verification.consensus.accept_votes == 2


def test_running_mission_is_pending_not_accepted() -> None:
    verification = _verify(
        _mission(
            completed=8,
            elapsed=120.0,
            status=MissionStatus.RUNNING,
        )
    )

    by_role = {a.role: a for a in verification.assessments}
    assert by_role["execution"].verdict == "PENDING"
    assert by_role["performance"].verdict == "PENDING"
    assert by_role["execution"].score is None
    assert verification.consensus.decision == "PENDING"


def test_incomplete_terminal_mission_is_rejected() -> None:
    verification = _verify(
        _mission(
            completed=10,
            elapsed=600.0,
            status=MissionStatus.TIMED_OUT,
        )
    )

    execution = next(a for a in verification.assessments if a.role == "execution")
    assert execution.verdict == "FAIL"
    assert execution.score == 50.0
    assert verification.consensus.decision == "REJECTED"


def test_empty_mission_evidence_is_inconclusive() -> None:
    verification = _verify(_mission(task_count=0, completed=0))

    by_role = {a.role: a for a in verification.assessments}
    assert by_role["execution"].verdict == "INCONCLUSIVE"
    assert by_role["safety"].verdict == "INCONCLUSIVE"
    assert verification.consensus.decision == "INCONCLUSIVE"


def test_conflicting_votes_are_disputed() -> None:
    assessments = tuple(
        Assessment(
            validator_id=f"validator-{role}-01",
            role=role,
            verdict=verdict,
            score=score,
            checks=(),
            reason="test",
            evidence_hash="0" * 64,
        )
        for role, verdict, score in (
            ("execution", "PASS", 100.0),
            ("safety", "INCONCLUSIVE", None),
            ("performance", "FAIL", 42.0),
        )
    )

    consensus = reach_consensus(assessments)

    assert consensus.decision == "DISPUTED"


def test_evidence_hash_is_deterministic_and_state_sensitive() -> None:
    mission = _mission()
    first = MissionEvidence.from_mission(mission, policy="nearest")
    second = MissionEvidence.from_mission(mission, policy="nearest")

    assert first.evidence_hash() == second.evidence_hash()

    mission.completed_tasks = 19
    mission.tasks[-1].status = TaskStatus.PENDING
    changed = MissionEvidence.from_mission(mission, policy="nearest")

    assert changed.evidence_hash() != first.evidence_hash()
    assert changed.evidence_hash() != second.evidence_hash()
