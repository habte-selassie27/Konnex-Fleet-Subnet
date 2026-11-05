"""InProcessPolicyExecutor — deterministic headless policy execution.

Status: COMPLETE (Phase 6).
Executes a policy against a seeded, deterministic mission using only the policy
interface (TaskAllocator) and the robot adapter contract — the validator never
imports FleetOrchestrator internals (AGENTS.md §3.2). The Docker sandbox
(validator/sandbox/container.py) is the STUB production replacement.

Determinism: same (policy_id, policy_hash, scenario_id, seed) -> same outcome,
which is what makes the ±0.5 reproducibility gate achievable.
"""

import hashlib
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from fleet.collision.monitor import CollisionMonitor
from fleet.task_allocator.base import TaskAllocator
from robotics.adapters.simulation import SimulationRobotAdapter
from robotics.models.robot_state import NavState, RobotState
from robotics.models.task import Assignment, Task, TaskStatus
from robotics.models.telemetry import CollisionEvent, EnergyEntry, TrajectoryFrame
from simulation.scenarios.scenario_generator import Scenario, ScenarioGenerator
from validator.runner import PolicyError, PolicyExecutionResult, ValidationRequest

_MISSION_TIME_LIMIT_S = 600.0
_DT = 0.1
_ROBOT_COUNT = 5
_TASK_COUNT = 20


class PolicyExecutionError(PolicyError):
    """Base for policy-execution-time failures."""


class ResourceExceededError(PolicyExecutionError):
    """Policy exceeded the sandbox resource limits."""


class InvalidPolicyActionsError(PolicyExecutionError):
    """Policy returned assignments for unknown robots or tasks."""


@dataclass(frozen=True)
class PolicyEntry:
    """Registry entry: policy weights (for hash verification) + factory."""

    weights: bytes
    factory: Callable[[], TaskAllocator]


AssignFn = Callable[[list[RobotState], list[Task]], list[Assignment]]


def run_headless_mission(
    assign: AssignFn, scenario: Scenario, request: ValidationRequest
) -> PolicyExecutionResult:
    """Drive one deterministic mission, delegating assignment to ``assign``.

    Shared by the in-process executor (``assign`` = a policy's ``assign``
    method) and the Docker sandbox (``assign`` = a call into the policy
    container), so both produce the same mission outcome for the same policy
    behaviour — which is what keeps sandbox and headless scores comparable.

    Raises ``InvalidPolicyActionsError`` when ``assign`` references unknown
    robots or tasks, and whatever ``assign`` itself raises.
    """
    robots = [
        SimulationRobotAdapter(
            robot_id=f"robot_{index}",
            start_position=position,
            battery_pct=scenario.robot_battery_pcts[index],
        )
        for index, position in enumerate(scenario.robot_positions)
    ]
    tasks = list(scenario.tasks)
    time_limit = _MISSION_TIME_LIMIT_S
    cap = min(request.resource_limits.timeout_s * 2.0, time_limit)
    monitor = CollisionMonitor()

    trajectory: list[TrajectoryFrame] = []
    energy_log: list[EnergyEntry] = []
    collision_events: list[CollisionEvent] = []
    completed = 0
    clock = 0.0

    while completed < len(tasks) and clock < cap:
        states = [robot.get_state() for robot in robots]
        collision_events.extend(monitor.detect(states))

        pending = [task for task in tasks if task.status == TaskStatus.PENDING]
        if pending:
            available = [
                state
                for state in states
                if state.current_task_id is None
                and state.comm_state == "online"
                and state.nav_state not in (NavState.FAILED, NavState.CHARGING)
                and state.battery_pct >= 0.10
            ]
            for assignment in assign(available, pending):
                task = next((t for t in tasks if t.id == assignment.task_id), None)
                robot = next((r for r in robots if r.robot_id == assignment.robot_id), None)
                if task is None or robot is None:
                    raise InvalidPolicyActionsError(
                        f"assignment references unknown robot/task: {assignment}"
                    )
                if robot.assign_task(task):
                    task.status = TaskStatus.ASSIGNED
                    task.assigned_robot_id = assignment.robot_id

        for robot in robots:
            robot.tick(_DT)
            task_id = robot.take_completed_task()
            if task_id is not None:
                for task in tasks:
                    if task.id == task_id and task.status != TaskStatus.COMPLETED:
                        task.status = TaskStatus.COMPLETED
                        task.completed_at = clock
                        completed += 1

        clock += _DT
        for state in [robot.get_state() for robot in robots]:
            trajectory.append(
                TrajectoryFrame(t=clock, robot_id=state.id, x=state.position.x, y=state.position.y)
            )
            energy_log.append(
                EnergyEntry(robot_id=state.id, t=clock, battery_pct=state.battery_pct)
            )

    status = "COMPLETE" if completed >= len(tasks) else "TIMEOUT"
    return PolicyExecutionResult(
        status=status,
        tasks_completed=completed,
        tasks_total=len(tasks),
        completion_time_s=clock,
        time_limit_s=time_limit,
        collision_count=sum(1 for event in collision_events if not event.near_miss),
        energy_consumed=sum(robot.energy_consumed_units for robot in robots),
        robot_count=len(robots),
        failure_count=0,
        trajectory=trajectory,
        collision_log=collision_events,
        energy_log=energy_log,
    )


class InProcessPolicyExecutor:
    """Deterministic headless executor backed by the simulated mission driver."""

    def __init__(
        self, policy_registry: Mapping[str, PolicyEntry], rng_seed: int | None = None
    ) -> None:
        self._registry = dict(policy_registry)
        self._rng_seed = rng_seed if rng_seed is not None else 0
        self._rng = random.Random(self._rng_seed)

    def execute(self, request: ValidationRequest) -> PolicyExecutionResult:
        """Execute a policy; raises PolicyError on identity/hash problems."""
        entry = self._registry.get(request.policy_id)
        if entry is None:
            raise PolicyError(f"unknown policy: {request.policy_id!r}")
        if hashlib.sha256(entry.weights).hexdigest() != request.policy_hash:
            raise PolicyError("policy hash mismatch: weights do not match submitted hash")

        try:
            policy = entry.factory()
        except PolicyExecutionError as exc:
            return self._failed_result("POLICY_CRASH", request, str(exc))

        scenario = ScenarioGenerator().generate(
            seed=request.seed,
            robot_count=_ROBOT_COUNT,
            task_count=_TASK_COUNT,
        )
        try:
            return self._run_mission(policy, scenario, request)
        except InvalidPolicyActionsError as exc:
            return self._failed_result("INVALID_ACTIONS", request, str(exc))
        except ResourceExceededError as exc:
            return self._failed_result("RESOURCE_EXCEEDED", request, str(exc))

    # ─── Internals ────────────────────────────────────────────────────────

    def _run_mission(
        self, policy: TaskAllocator, scenario: Scenario, request: ValidationRequest
    ) -> PolicyExecutionResult:
        return run_headless_mission(policy.assign, scenario, request)

    def _failed_result(
        self, status: str, _request: ValidationRequest, message: str
    ) -> PolicyExecutionResult:
        return PolicyExecutionResult(
            status=status,
            tasks_completed=0,
            tasks_total=_TASK_COUNT,
            completion_time_s=0.0,
            time_limit_s=_MISSION_TIME_LIMIT_S,
            collision_count=0,
            energy_consumed=0.0,
            robot_count=_ROBOT_COUNT,
            failure_count=0,
            error_message=message,
        )
