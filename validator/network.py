"""Konnex-aligned validator network for fleet missions.

Three role-separated validators assess the *same* mission evidence
independently and a consensus layer turns their votes into one verdict:

  execution    — did the fleet complete the assigned tasks?
  safety       — were there collisions / dangerous outcomes?
  performance  — time and energy quality of the execution

Design rules (from the Konnex validator guide):
  - Missing / incomplete evidence is PENDING or INCONCLUSIVE, never an accept.
  - A safety violation vetoes the mission regardless of the other votes.
  - Conflicting role verdicts become DISPUTED (needs extra verification),
    not a silent majority win.
  - Assessments are deterministic functions of the evidence hash; no model
    calls, no fabricated numbers.

These are the *fleet subnet's* validators (`docs/validator.md`). They are not
Konnex protocol validators: `protocol/konnex/adapter.py` stays a STUB until
the Konnex SDK is verified (AGENTS.md §5.6).

Status: COMPLETE (Phase 7 role verification + consensus)
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

TERMINAL_STATUSES = frozenset({"complete", "failed", "timed_out"})

# Energy budget used by the live PoPW score (`backend.services.fleet_service`),
# so the performance validator and the dashboard gauge agree on the same basis.
ENERGY_BUDGET_PER_ROBOT = 100.0


class _TaskLike(Protocol):
    """Minimal task shape the validator needs (no fleet import, no coupling)."""

    @property
    def id(self) -> str: ...

    @property
    def status(self) -> object: ...  # enum with .value

    @property
    def assigned_robot_id(self) -> str | None: ...


class _MissionLike(Protocol):
    """Minimal mission shape the validator needs (no fleet import)."""

    @property
    def id(self) -> str: ...

    @property
    def scenario_id(self) -> str: ...

    @property
    def seed(self) -> int: ...

    @property
    def robot_count(self) -> int: ...

    @property
    def task_count(self) -> int: ...

    @property
    def completed_tasks(self) -> int: ...

    @property
    def collision_count(self) -> int: ...

    @property
    def failure_count(self) -> int: ...

    @property
    def elapsed_seconds(self) -> float: ...

    @property
    def time_limit_s(self) -> float: ...

    @property
    def energy_consumed(self) -> float: ...

    @property
    def status(self) -> object: ...  # enum with .value

    @property
    def tasks(self) -> Sequence[_TaskLike]: ...


def _value(raw: object) -> str:
    """Return the string value of an enum-like field."""
    return str(getattr(raw, "value", raw))


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


@dataclass(frozen=True)
class Check:
    """One named assertion made by a validator."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class MissionEvidence:
    """Canonical evidence package every validator receives.

    Built from the live mission record only — the same object for all three
    validators. `evidence_hash` is the SHA-256 of the canonical manifest, so
    any assessment can be tied back to exactly this evidence.
    """

    mission_id: str
    scenario_id: str
    seed: int
    policy: str
    robot_count: int
    task_count: int
    tasks_completed: int
    collision_count: int
    failure_count: int
    elapsed_s: float
    time_limit_s: float
    energy_consumed: float
    mission_status: str
    task_states: tuple[tuple[str, str], ...]

    @classmethod
    def from_mission(cls, mission: _MissionLike, policy: str) -> MissionEvidence:
        """Snapshot a live mission into an immutable evidence package."""
        return cls(
            mission_id=mission.id,
            scenario_id=mission.scenario_id,
            seed=mission.seed,
            policy=policy,
            robot_count=mission.robot_count,
            task_count=mission.task_count,
            tasks_completed=mission.completed_tasks,
            collision_count=mission.collision_count,
            failure_count=mission.failure_count,
            elapsed_s=_round(mission.elapsed_seconds),
            time_limit_s=_round(mission.time_limit_s),
            energy_consumed=_round(mission.energy_consumed),
            mission_status=_value(mission.status),
            task_states=tuple((task.id, _value(task.status)) for task in mission.tasks),
        )

    @property
    def is_terminal(self) -> bool:
        """True once the mission can no longer change its outcome."""
        return self.mission_status in TERMINAL_STATUSES

    def manifest(self) -> dict[str, object]:
        """Canonical, JSON-serializable evidence manifest."""
        return {
            "mission_id": self.mission_id,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "policy": self.policy,
            "robot_count": self.robot_count,
            "task_count": self.task_count,
            "tasks_completed": self.tasks_completed,
            "collision_count": self.collision_count,
            "failure_count": self.failure_count,
            "elapsed_s": self.elapsed_s,
            "time_limit_s": self.time_limit_s,
            "energy_consumed": self.energy_consumed,
            "mission_status": self.mission_status,
            "task_states": [list(state) for state in self.task_states],
        }

    def evidence_hash(self) -> str:
        """SHA-256 over the canonical manifest (stable across processes)."""
        canonical = json.dumps(self.manifest(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ValidatorSpec:
    """Registry entry: identity + the checks this validator is responsible for."""

    id: str
    role: str
    operator: str
    capabilities: tuple[str, ...]
    implementation: str = "deterministic-rule-engine"

    @property
    def status(self) -> str:
        """In-process validators are available whenever the backend is up."""
        return "READY"


VALIDATORS: tuple[ValidatorSpec, ...] = (
    ValidatorSpec(
        id="validator-execution-01",
        role="execution",
        operator="fleet-subnet",
        capabilities=("mission_completion", "task_accounting"),
    ),
    ValidatorSpec(
        id="validator-safety-01",
        role="safety",
        operator="fleet-subnet",
        capabilities=("collision_free", "telemetry_present"),
    ),
    ValidatorSpec(
        id="validator-performance-01",
        role="performance",
        operator="fleet-subnet",
        capabilities=("time_budget", "energy_budget"),
    ),
)


@dataclass(frozen=True)
class Assessment:
    """One validator's independent verdict on the evidence."""

    validator_id: str
    role: str
    verdict: str  # PASS | FAIL | PENDING | INCONCLUSIVE
    score: float | None  # 0-100, None until the evidence is final
    checks: tuple[Check, ...]
    reason: str
    evidence_hash: str


@dataclass(frozen=True)
class Consensus:
    """Aggregated decision over the three assessments."""

    decision: str  # ACCEPTED | REJECTED | DISPUTED | INCONCLUSIVE | PENDING
    accept_votes: int
    reject_votes: int
    validator_count: int
    reason: str


@dataclass(frozen=True)
class Verification:
    """Full verification package for one mission snapshot."""

    evidence: MissionEvidence
    assessments: tuple[Assessment, ...]
    consensus: Consensus

    @property
    def evidence_hash(self) -> str:
        return self.evidence.evidence_hash()


def _assess_execution(evidence: MissionEvidence, evidence_hash: str) -> Assessment:
    """Did the fleet complete the tasks it was assigned?"""
    spec = VALIDATORS[0]
    if evidence.task_count <= 0:
        return Assessment(
            spec.id,
            spec.role,
            "INCONCLUSIVE",
            None,
            (Check("task_count", False, "mission has no tasks"),),
            "No tasks in the evidence package — nothing to verify.",
            evidence_hash,
        )

    ratio = evidence.tasks_completed / evidence.task_count
    pending = sum(1 for _, status in evidence.task_states if status == "pending")
    states_completed = sum(1 for _, status in evidence.task_states if status == "completed")
    unfinished = evidence.task_count - evidence.tasks_completed
    complete_check = Check(
        "mission_completion",
        ratio >= 1.0,
        f"{evidence.tasks_completed}/{evidence.task_count} tasks completed",
    )
    accounting_check = Check(
        "task_accounting",
        states_completed == evidence.tasks_completed,
        f"{states_completed} task records completed, counter reports "
        f"{evidence.tasks_completed} ({unfinished} unfinished, {pending} pending)",
    )
    checks = (complete_check, accounting_check)

    if not evidence.is_terminal:
        return Assessment(
            spec.id,
            spec.role,
            "PENDING",
            None,
            checks,
            f"Mission {evidence.mission_status}; completion not final yet.",
            evidence_hash,
        )
    if ratio >= 1.0:
        return Assessment(
            spec.id,
            spec.role,
            "PASS",
            100.0,
            checks,
            f"All {evidence.task_count} assigned tasks completed.",
            evidence_hash,
        )
    return Assessment(
        spec.id,
        spec.role,
        "FAIL",
        _round(100.0 * ratio, 2),
        checks,
        f"Only {evidence.tasks_completed}/{evidence.task_count} tasks completed "
        f"({evidence.mission_status}).",
        evidence_hash,
    )


def _assess_safety(evidence: MissionEvidence, evidence_hash: str) -> Assessment:
    """Were there collisions or other physical-safety violations?"""
    spec = VALIDATORS[1]
    collision_check = Check(
        "collision_free",
        evidence.collision_count == 0,
        f"{evidence.collision_count} collision event(s) recorded",
    )
    telemetry_check = Check(
        "telemetry_present",
        evidence.task_count > 0 and evidence.robot_count > 0,
        f"{evidence.robot_count} robot(s), {len(evidence.task_states)} task record(s)",
    )
    checks = (collision_check, telemetry_check)

    if not telemetry_check.passed:
        return Assessment(
            spec.id,
            spec.role,
            "INCONCLUSIVE",
            None,
            checks,
            "Evidence package has no robot/task telemetry to assess.",
            evidence_hash,
        )
    if evidence.collision_count > 0:
        score = max(0.0, 100.0 - 25.0 * evidence.collision_count)
        return Assessment(
            spec.id,
            spec.role,
            "FAIL",
            _round(score, 2),
            checks,
            f"{evidence.collision_count} collision(s) violate the zero-collision "
            "target — safety veto.",
            evidence_hash,
        )
    if not evidence.is_terminal:
        return Assessment(
            spec.id,
            spec.role,
            "PENDING",
            None,
            checks,
            "No collisions so far; safety is certified when the mission ends.",
            evidence_hash,
        )
    return Assessment(
        spec.id,
        spec.role,
        "PASS",
        100.0,
        checks,
        "No collisions recorded for the whole mission.",
        evidence_hash,
    )


def _assess_performance(evidence: MissionEvidence, evidence_hash: str) -> Assessment:
    """Operational quality: time and energy within budget."""
    spec = VALIDATORS[2]
    budget = evidence.robot_count * ENERGY_BUDGET_PER_ROBOT
    limit = evidence.time_limit_s
    within_time = limit > 0 and evidence.elapsed_s <= limit
    within_energy = budget > 0 and evidence.energy_consumed <= budget

    time_check = Check(
        "time_budget",
        within_time,
        f"{evidence.elapsed_s:.1f}s of {limit:.0f}s limit",
    )
    energy_check = Check(
        "energy_budget",
        within_energy,
        f"{evidence.energy_consumed:.1f} of {budget:.0f} energy units",
    )
    checks = (time_check, energy_check)

    if limit <= 0 or budget <= 0:
        return Assessment(
            spec.id,
            spec.role,
            "INCONCLUSIVE",
            None,
            checks,
            "Mission time limit or energy budget is missing.",
            evidence_hash,
        )
    if not evidence.is_terminal:
        return Assessment(
            spec.id,
            spec.role,
            "PENDING",
            None,
            checks,
            f"Mission {evidence.mission_status}; efficiency is scored at completion.",
            evidence_hash,
        )

    time_score = min(1.0, max(0.0, 1.0 - evidence.elapsed_s / limit))
    energy_score = min(1.0, max(0.0, 1.0 - evidence.energy_consumed / budget))
    score = _round(100.0 * (0.6 * time_score + 0.4 * energy_score), 2)

    passed = within_time and score >= 60.0
    if passed:
        reason = (
            f"Finished in {evidence.elapsed_s:.1f}s ({time_score:.0%} time budget left) "
            f"with {1.0 - energy_score:.0%} of the energy budget used."
        )
    else:
        reason = (
            f"Below the operational bar: {evidence.elapsed_s:.1f}s of {limit:.0f}s, "
            f"{evidence.energy_consumed:.1f} of {budget:.0f} energy units."
        )
    return Assessment(
        spec.id,
        spec.role,
        "PASS" if passed else "FAIL",
        score,
        checks,
        reason,
        evidence_hash,
    )


_ASSESSORS = {
    "execution": _assess_execution,
    "safety": _assess_safety,
    "performance": _assess_performance,
}


def assess(evidence: MissionEvidence) -> tuple[Assessment, ...]:
    """Run every registered validator independently over the same evidence."""
    evidence_hash = evidence.evidence_hash()
    return tuple(_ASSESSORS[spec.role](evidence, evidence_hash) for spec in VALIDATORS)


def reach_consensus(assessments: Sequence[Assessment]) -> Consensus:
    """Aggregate role verdicts: 2-of-3 quorum, safety veto, honest gaps."""
    count = len(assessments)
    safety = next((a for a in assessments if a.role == "safety"), None)
    accepts = sum(1 for a in assessments if a.verdict == "PASS")
    rejects = sum(1 for a in assessments if a.verdict == "FAIL")
    pending = any(a.verdict == "PENDING" for a in assessments)
    inconclusive = any(a.verdict == "INCONCLUSIVE" for a in assessments)

    if safety is not None and safety.verdict == "FAIL":
        return Consensus(
            "REJECTED",
            accepts,
            rejects,
            count,
            "Safety validator vetoed the mission: " + safety.reason,
        )
    if pending:
        return Consensus(
            "PENDING",
            accepts,
            rejects,
            count,
            "Mission still running — verdict is final when execution ends.",
        )
    if inconclusive:
        if accepts > 0 and rejects > 0:
            return Consensus(
                "DISPUTED",
                accepts,
                rejects,
                count,
                "Validators disagree and evidence is incomplete — additional "
                "verification required.",
            )
        return Consensus(
            "INCONCLUSIVE",
            accepts,
            rejects,
            count,
            "Evidence is incomplete; no verdict can be certified.",
        )
    if accepts >= 2:
        return Consensus(
            "ACCEPTED",
            accepts,
            rejects,
            count,
            f"{accepts}/{count} validators accepted the mission.",
        )
    if rejects >= 2:
        return Consensus(
            "REJECTED",
            accepts,
            rejects,
            count,
            f"{rejects}/{count} validators rejected the mission.",
        )
    return Consensus(
        "DISPUTED",
        accepts,
        rejects,
        count,
        "Validators disagree — additional verification required.",
    )


def verify_mission(evidence: MissionEvidence) -> Verification:
    """Assess the evidence with all validators, then reach consensus."""
    assessments = assess(evidence)
    return Verification(
        evidence=evidence,
        assessments=assessments,
        consensus=reach_consensus(assessments),
    )
