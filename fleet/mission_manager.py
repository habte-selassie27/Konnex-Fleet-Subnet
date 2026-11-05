"""MissionManager — mission lifecycle and task bookkeeping.

Status: COMPLETE (Phase 5).
States: PENDING -> RUNNING -> COMPLETE | FAILED | TIMED_OUT (TESTING_PLAN.md §4.2).
"""

import time
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum

from robotics.models.task import Task, TaskStatus
from simulation.scenarios.scenario_generator import Scenario, ScenarioGenerator


class MissionStatus(str, Enum):
    """Mission lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class MissionConfig:
    """Mission execution parameters."""

    time_limit_s: float = 600.0
    robot_count: int = 5
    task_count: int = 20
    world: str = "warehouse_v1"
    seed: int = 42
    scenario_id: str = "warehouse_v1_20tasks"


@dataclass
class Mission:
    """A single mission record."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))  # noqa: A003
    scenario_id: str = ""
    seed: int = 0
    robot_count: int = 0
    task_count: int = 0
    status: MissionStatus = MissionStatus.PENDING
    tasks: list[Task] = field(default_factory=list)
    completed_tasks: int = 0
    collision_count: int = 0
    elapsed_seconds: float = 0.0
    energy_consumed: float = 0.0
    time_limit_s: float = 600.0
    failure_count: int = 0
    halted_reason: str | None = None
    popw_score: float | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None


class MissionManager:
    """Owns mission records, task generation and task status transitions."""

    def __init__(self, generator: ScenarioGenerator | None = None) -> None:
        self._generator = generator or ScenarioGenerator()
        self._missions: dict[str, Mission] = {}

    def create_mission(self, config: MissionConfig) -> tuple[Mission, Scenario]:
        """Generate a deterministic scenario and register a new mission."""
        scenario = self._generator.generate(
            seed=config.seed,
            robot_count=config.robot_count,
            task_count=config.task_count,
        )
        mission = Mission(
            scenario_id=config.scenario_id,
            seed=config.seed,
            robot_count=config.robot_count,
            task_count=config.task_count,
            tasks=[replace(task) for task in scenario.tasks],
            time_limit_s=config.time_limit_s,
        )
        self._missions[mission.id] = mission
        return mission, scenario

    def get_mission(self, mission_id: str) -> Mission | None:
        """Fetch a mission by id."""
        return self._missions.get(mission_id)

    def start(self, mission: Mission) -> None:
        """Transition PENDING -> RUNNING."""
        if mission.status != MissionStatus.PENDING:
            return
        mission.status = MissionStatus.RUNNING
        mission.started_at = time.time()

    def complete_task(self, mission: Mission, task_id: str, timestamp: float) -> None:
        """Mark a task COMPLETED and bump mission progress."""
        for task in mission.tasks:
            if task.id == task_id and task.status != TaskStatus.COMPLETED:
                task.status = TaskStatus.COMPLETED
                task.completed_at = timestamp
                mission.completed_tasks += 1
                return

    def recover_tasks_from_robot(self, mission: Mission, robot_id: str) -> list[Task]:
        """Unassign all tasks held by `robot_id` and mark them PENDING again.

        Returns the recovered tasks so the orchestrator can reassign them
        through the current policy.
        """
        recovered: list[Task] = []
        for task in mission.tasks:
            if task.assigned_robot_id == robot_id and task.status in (
                TaskStatus.ASSIGNED,
                TaskStatus.IN_PROGRESS,
            ):
                task.status = TaskStatus.PENDING
                task.assigned_robot_id = None
                recovered.append(task)
        return recovered

    def tick(self, mission: Mission, elapsed_seconds: float) -> None:
        """Advance mission bookkeeping: completion and timeout checks."""
        mission.elapsed_seconds = elapsed_seconds
        if mission.status == MissionStatus.COMPLETE:
            return
        if all(task.status == TaskStatus.COMPLETED for task in mission.tasks):
            mission.status = MissionStatus.COMPLETE
            mission.completed_at = time.time()
            return
        if elapsed_seconds >= mission.time_limit_s:
            mission.status = MissionStatus.TIMED_OUT
            mission.completed_at = time.time()

    def halt(self, mission: Mission, reason: str) -> None:
        """Fail the mission with a halt reason (e.g., NO_ROBOTS)."""
        mission.status = MissionStatus.FAILED
        mission.halted_reason = reason
        mission.completed_at = time.time()

    def task_completion_rate(self, mission: Mission) -> float:
        """Fraction of tasks completed in [0.0, 1.0]."""
        if mission.task_count == 0:
            return 0.0
        return mission.completed_tasks / mission.task_count
