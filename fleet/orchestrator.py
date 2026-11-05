"""FleetOrchestrator — central fleet coordinator with failure recovery.

Status: COMPLETE (Phase 5).
Contract (BUILD.md §5):
- Owns task assignment, monitoring, failure recovery.
- Does NOT control individual robot actuators beyond the RobotAdapter interface.
- Does NOT implement ML policy logic — delegation to the current allocator.
- Health monitoring polls at 5 Hz (health_poll_interval_s = 0.2 s).
"""

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass, field

import structlog

from fleet.collision.monitor import CollisionMonitor
from fleet.communication.model import CommunicationModel
from fleet.failure.detector import FailureDetector
from fleet.mission_manager import Mission, MissionConfig, MissionManager, MissionStatus
from fleet.task_allocator.base import TaskAllocator
from robotics.adapters.base import RobotAdapter
from robotics.adapters.simulation import SimulationRobotAdapter
from robotics.models.failure import FailureEvent, FailureType
from robotics.models.fleet_state import FleetState
from robotics.models.robot_state import CommState, NavState, RobotState, Vector2D
from robotics.models.task import Task, TaskStatus
from robotics.models.telemetry import (
    CollisionEvent,
    EnergyEntry,
    TaskOutcome,
    TrajectoryFrame,
)
from simulation.scenarios.scenario_generator import Scenario, ScenarioGenerator

_logger = structlog.get_logger(__name__)

_HISTORY_LENGTH = 200
_HOLD_DISTANCE_M = 1.2

# (robot_id, scenario start position, initial battery) -> adapter.
# Lets the app inject Gazebo-backed robots without the orchestrator knowing
# anything about ROS 2 (AGENTS.md Law 2).
RobotFactory = Callable[[str, Vector2D, float], RobotAdapter]


@dataclass(frozen=True)
class OrchestratorConfig:
    """Orchestrator behavior parameters."""

    health_poll_interval_s: float = 0.2  # 5 Hz health poll
    time_limit_s: float = 600.0
    charging_station: Vector2D = Vector2D(2.0, 2.0)
    max_steps: int = 20_000


@dataclass(frozen=True)
class FailurePlan:
    """Deterministic failure injection plan for a mission run."""

    robot_id: str
    failure_type: FailureType
    after_elapsed_s: float
    duration_s: float | None = None


@dataclass
class MissionOutcome:
    """Aggregate result of a completed mission run."""

    mission_id: str
    status: str
    tasks_completed: int
    tasks_total: int
    elapsed_s: float
    collision_count: int
    energy_consumed: float
    failure_count: int
    recovery_time_s: float | None
    task_outcomes: list[TaskOutcome] = field(default_factory=list)
    trajectory: list[TrajectoryFrame] = field(default_factory=list)
    collision_log: list[CollisionEvent] = field(default_factory=list)
    energy_log: list[EnergyEntry] = field(default_factory=list)


class FleetOrchestrator:
    """Coordinates the fleet: assignment, health monitoring, failure recovery."""

    def __init__(
        self,
        allocator: TaskAllocator,
        mission_manager: MissionManager | None = None,
        config: OrchestratorConfig | None = None,
        detector: FailureDetector | None = None,
        comm: CommunicationModel | None = None,
        rng: random.Random | None = None,
        robot_factory: RobotFactory | None = None,
    ) -> None:
        self._allocator = allocator
        # Default stays the deterministic headless adapter; the app injects a
        # Gazebo-backed factory when SIM_MODE=gazebo is actually wired (Phase 2).
        self._robot_factory = robot_factory
        self._mission_manager = mission_manager or MissionManager()
        self._config = config or OrchestratorConfig()
        self._detector = detector or FailureDetector()
        self._comm = comm or CommunicationModel()
        # Fixed default seed keeps the comm-degradation model deterministic so
        # validator runs stay reproducible even when packet loss is configured.
        self._rng = rng or random.Random(0)
        self._collision_monitor = CollisionMonitor()
        self._robots: list[RobotAdapter] = []
        self._mission: Mission | None = None
        self._clock = 0.0
        self._history: dict[str, list[RobotState]] = {}
        self._trajectory: list[TrajectoryFrame] = []
        self._collision_log: list[CollisionEvent] = []
        self._energy_log: list[EnergyEntry] = []
        self._recovered_task_ids: set[str] = set()
        self._recovery_started_at: float | None = None
        self._recovered_at: float | None = None

    # ─── Setup ────────────────────────────────────────────────────────────

    def configure(self, scenario: Scenario, config: MissionConfig) -> Mission:
        """Configure the fleet from a scenario and start a mission."""
        if self._robot_factory is not None:
            self._robots = [
                self._robot_factory(f"robot_{index}", position, scenario.robot_battery_pcts[index])
                for index, position in enumerate(scenario.robot_positions)
            ]
            _logger.info(
                "fleet_configured",
                robots=len(self._robots),
                adapter=type(self._robots[0]).__name__ if self._robots else "none",
            )
        else:
            self._robots = [
                SimulationRobotAdapter(
                    robot_id=f"robot_{index}",
                    start_position=position,
                    battery_pct=scenario.robot_battery_pcts[index],
                    charging_station=self._config.charging_station,
                )
                for index, position in enumerate(scenario.robot_positions)
            ]
        mission, _ = self._mission_manager.create_mission(config)
        self._mission = mission
        self._mission_manager.start(mission)
        self._clock = 0.0
        self._detector.reset()
        self._comm.reset_stats()
        self._history.clear()
        self._collision_monitor.reset()
        self._trajectory.clear()
        self._collision_log.clear()
        self._energy_log.clear()
        self._recovered_task_ids.clear()
        self._recovery_started_at = None
        self._recovered_at = None
        return mission

    def start_mission(self, seed: int, config: MissionConfig) -> Mission:
        """Generate a scenario from `seed` and configure the fleet."""
        scenario = ScenarioGenerator().generate(
            seed=seed,
            robot_count=config.robot_count,
            task_count=config.task_count,
        )
        return self.configure(scenario, config)

    # ─── Accessors ────────────────────────────────────────────────────────

    @property
    def policy_name(self) -> str:
        """Name of the policy (allocator) currently driving the fleet."""
        return self._allocator.name

    def get_mission(self) -> Mission | None:
        """Current mission record."""
        return self._mission

    def get_fleet_state(self) -> FleetState:
        """Aggregate fleet snapshot."""
        mission = self._mission
        return FleetState(
            robots=[robot.get_state() for robot in self._robots],
            active_tasks=list(mission.tasks) if mission else [],
            mission_id=mission.id if mission else None,
            mission_status=mission.status.value if mission else "none",
            completed_tasks=mission.completed_tasks if mission else 0,
            total_tasks=mission.task_count if mission else 0,
            collision_count=mission.collision_count if mission else 0,
            elapsed_seconds=mission.elapsed_seconds if mission else 0.0,
            timestamp=self._clock,
        )

    def inject_failure(
        self, robot_id: str, failure_type: FailureType, duration_s: float | None = None
    ) -> bool:
        """Inject a failure into a robot. Returns False when the robot is unknown."""
        robot = self._robot_by_id(robot_id)
        if robot is None:
            return False
        robot.inject_failure(failure_type, duration_s)
        return True

    def recover_tasks_from_robot(self, robot_id: str) -> list[Task]:
        """Unassign a failed robot's tasks (delegates to the MissionManager)."""
        mission = self._mission
        if mission is None:
            return []
        recovered = self._mission_manager.recover_tasks_from_robot(mission, robot_id)
        for task in recovered:
            self._recovered_task_ids.add(task.id)
        if recovered and self._recovery_started_at is None:
            self._recovery_started_at = self._clock
        return recovered

    # ─── Execution ────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Live non-blocking orchestration loop at the 5 Hz health poll rate."""
        while self._mission is not None and self._mission.status in (
            MissionStatus.PENDING,
            MissionStatus.RUNNING,
        ):
            await asyncio.sleep(self._config.health_poll_interval_s)
            self.step(self._config.health_poll_interval_s)

    def step(self, dt: float = 0.1) -> None:
        """Advance the fleet one tick. Deterministic when driven directly."""
        mission = self._mission
        if mission is None or mission.status not in (MissionStatus.PENDING, MissionStatus.RUNNING):
            return
        self._clock += dt

        states = [robot.get_state() for robot in self._robots]
        self._monitor_collisions(states, mission)
        self._apply_holds(states)

        for robot in self._robots:
            robot.tick(dt)
        self._collect_completions(mission)
        self._run_health_checks()
        self._assign_pending(mission)

        mission.energy_consumed = sum(robot.energy_consumed_units for robot in self._robots)
        if self._operational_count() == 0 and mission.completed_tasks < mission.task_count:
            self._mission_manager.halt(mission, "NO_ROBOTS")
        self._mission_manager.tick(mission, self._clock)
        self._record_telemetry()

    def run_mission(
        self,
        seed: int,
        config: MissionConfig,
        failure_plan: FailurePlan | None = None,
        dt: float = 0.1,
    ) -> MissionOutcome:
        """Run a deterministic mission to completion and return its outcome.

        Used by robustness tests and the validator executor.
        """
        mission = self.start_mission(seed, config)
        injected = False
        steps = 0
        while mission.status in (MissionStatus.PENDING, MissionStatus.RUNNING):
            if (
                failure_plan is not None
                and not injected
                and self._clock >= failure_plan.after_elapsed_s
            ):
                robot = self._robot_by_id(failure_plan.robot_id)
                if robot is not None:
                    robot.inject_failure(failure_plan.failure_type, failure_plan.duration_s)
                injected = True
            self.step(dt)
            steps += 1
            if steps > self._config.max_steps:  # pragma: no cover - safety guard
                self._mission_manager.halt(mission, "MAX_STEPS")
                break
        return self._build_outcome(mission)

    # ─── Internals ────────────────────────────────────────────────────────

    def _monitor_collisions(self, states: list[RobotState], mission: Mission) -> None:
        for event in self._collision_monitor.detect(states):
            if not event.near_miss:
                mission.collision_count += 1
            self._collision_log.append(event)

    def _apply_holds(self, states: list[RobotState]) -> None:
        for robot in self._robots:
            robot.set_hold(False)
        for index, left in enumerate(states):
            for right in states[index + 1 :]:
                if left.position.distance_to(right.position) < _HOLD_DISTANCE_M:
                    # Hold exactly one robot per pair (deterministic by id) so
                    # the other can maneuver past — prevents mutual-hold
                    # deadlocks that would stall the mission.
                    holder = left if left.id < right.id else right
                    held = self._robot_by_id(holder.id)
                    if held is not None:
                        held.set_hold(True)

    def _collect_completions(self, mission: Mission) -> None:
        for robot in self._robots:
            task_id = robot.take_completed_task()
            if task_id is not None:
                self._mission_manager.complete_task(mission, task_id, self._clock)

    def _run_health_checks(self) -> None:
        for robot in self._robots:
            if self._comm.transmit(self._rng) is None:
                # Telemetry packet dropped by the comm degradation model — this
                # robot's state is not processed this tick (lossy channel).
                continue
            state = robot.get_state()
            history = self._history.get(state.id, [])
            for event in self._detector.check(state, history):
                self._handle_failure_event(robot, event)
            history.append(state)
            if len(history) > _HISTORY_LENGTH:
                del history[: len(history) - _HISTORY_LENGTH]
            self._history[state.id] = history

    def _handle_failure_event(self, robot: RobotAdapter, event: FailureEvent) -> None:
        mission = self._mission
        if mission is None:
            return
        mission.failure_count += 1
        if event.failure_type == FailureType.BATTERY_CRITICAL:
            robot.go_charge()
        else:
            robot.stop()
        self.recover_tasks_from_robot(robot.robot_id)

    def _assign_pending(self, mission: Mission) -> None:
        states = [robot.get_state() for robot in self._robots]
        available = [
            state
            for state in states
            if state.comm_state == CommState.ONLINE
            and state.nav_state not in (NavState.FAILED, NavState.CHARGING)
            and state.current_task_id is None
            and state.battery_pct >= 0.10
        ]
        pending = [task for task in mission.tasks if task.status == TaskStatus.PENDING]
        if not available or not pending:
            return
        for assignment in self._allocator.assign(available, pending):
            task = self._task_by_id(mission, assignment.task_id)
            robot = self._robot_by_id(assignment.robot_id)
            if task is None or robot is None:
                continue
            if robot.assign_task(task):
                task.status = TaskStatus.ASSIGNED
                task.assigned_robot_id = assignment.robot_id
                if task.id in self._recovered_task_ids and self._recovered_at is None:
                    self._recovered_at = self._clock

    def _record_telemetry(self) -> None:
        for state in [robot.get_state() for robot in self._robots]:
            self._trajectory.append(
                TrajectoryFrame(
                    t=self._clock, robot_id=state.id, x=state.position.x, y=state.position.y
                )
            )
            self._energy_log.append(
                EnergyEntry(robot_id=state.id, t=self._clock, battery_pct=state.battery_pct)
            )

    def _build_outcome(self, mission: Mission) -> MissionOutcome:
        recovery_time = (
            round(self._recovered_at - self._recovery_started_at, 3)
            if self._recovered_at is not None and self._recovery_started_at is not None
            else None
        )
        return MissionOutcome(
            mission_id=mission.id,
            status=mission.status.value,
            tasks_completed=mission.completed_tasks,
            tasks_total=mission.task_count,
            elapsed_s=mission.elapsed_seconds,
            collision_count=mission.collision_count,
            energy_consumed=mission.energy_consumed,
            failure_count=mission.failure_count,
            recovery_time_s=recovery_time,
            task_outcomes=[
                TaskOutcome(
                    task_id=task.id,
                    robot_id=task.assigned_robot_id,
                    status=task.status.value,
                    completed_at=task.completed_at,
                )
                for task in mission.tasks
            ],
            trajectory=list(self._trajectory),
            collision_log=list(self._collision_log),
            energy_log=list(self._energy_log),
        )

    def _operational_count(self) -> int:
        return sum(
            1
            for robot in self._robots
            if (state := robot.get_state()).comm_state == CommState.ONLINE
            and state.nav_state not in (NavState.FAILED, NavState.CHARGING)
        )

    def _robot_by_id(self, robot_id: str) -> RobotAdapter | None:
        for robot in self._robots:
            if robot.robot_id == robot_id:
                return robot
        return None

    @staticmethod
    def _task_by_id(mission: Mission, task_id: str) -> Task | None:
        for task in mission.tasks:
            if task.id == task_id:
                return task
        return None
