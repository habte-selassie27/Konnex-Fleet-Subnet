"""FleetAppState — owns the live fleet exposed by the robots API.

Status: COMPLETE (Phase 6 + Phase 2 Gazebo wiring).
Backs the failure-injection API endpoint (POST /robots/{id}/fail) with the fleet
orchestrator. When a live ROS bridge is attached (`SIM_MODE=gazebo`), robots are
backed by `GazeboRobotAdapter` over ROS 2 topics, so the fleet loop consumes
Gazebo telemetry instead of the headless stub. Without a bridge the deterministic
headless adapter is used and `sim_backend` reports which one is live — the app
never claims Gazebo when it is not connected.
"""

import asyncio
import random
from typing import Any

import structlog

from backend.config import Settings
from fleet.mission_manager import Mission, MissionConfig
from fleet.orchestrator import FleetOrchestrator, RobotFactory
from fleet.task_allocator import allocator_by_name
from robotics.adapters.base import RobotAdapter
from robotics.adapters.gazebo import GazeboRobotAdapter
from robotics.adapters.simulation import SimulationRobotAdapter
from robotics.models.robot_state import Vector2D
from validator.scoring.engine import MissionResult, PoPWScoringEngine

_SCORING = PoPWScoringEngine()
_logger = structlog.get_logger(__name__)


def live_popw_score(mission: Mission) -> float:
    """Provisional PoPW score from the current mission state.

    Uses the same PoPWScoringEngine + weights as post-mission validator scoring,
    evaluated against partial data. It converges to the final score when the
    mission ends, so the dashboard and API never show a number that contradicts
    the evaluation artifact (AGENTS.md Law 1).
    """
    result = MissionResult(
        tasks_completed=mission.completed_tasks,
        tasks_total=mission.task_count,
        elapsed_s=mission.elapsed_seconds,
        time_limit_s=mission.time_limit_s,
        collision_count=mission.collision_count,
        energy_consumed=mission.energy_consumed,
        energy_budget=mission.robot_count * 100.0,
        failure_count=mission.failure_count,
    )
    return _SCORING.score(result).final


class FleetAppState:
    """Application-level fleet singleton."""

    def __init__(self, settings: Settings, ros_bridge: Any | None = None) -> None:
        self._settings = settings
        self._rng = random.Random(settings.seed)
        self._ros_bridge = ros_bridge
        self._gazebo_robots = 0
        self._robot_factory: RobotFactory | None = self._build_robot_factory()
        self._orchestrator = FleetOrchestrator(
            allocator=allocator_by_name(settings.policy),
            rng=self._rng,
            robot_factory=self._robot_factory,
        )
        self._mission: Mission | None = None
        self._task: asyncio.Task[None] | None = None

    # ── Simulation backend ─────────────────────────────────────────────────

    @property
    def sim_backend(self) -> str:
        """Which adapter actually drives the fleet (never a guess).

        "gazebo" only when a running ROS bridge is attached and at least one
        robot adapter was built over it; otherwise "headless".
        """
        if self._robot_factory is None or self._gazebo_robots == 0:
            return "headless"
        return "gazebo"

    def attach_bridge(self, bridge: Any) -> None:
        """Attach a started ROS bridge and rebuild the orchestrator over it.

        Called from the app lifespan after `ROSBridge.start()` succeeds. The
        orchestrator is rebuilt (not mutated) so the new robot factory applies
        to the very next `configure()` and no half-wired fleet can run.
        """
        self._ros_bridge = bridge
        self._gazebo_robots = 0
        self._robot_factory = self._build_robot_factory()
        self._orchestrator = FleetOrchestrator(
            allocator=allocator_by_name(self._settings.policy),
            rng=self._rng,
            robot_factory=self._robot_factory,
        )
        _logger.info("fleet_bridge_attached", sim_backend=self.sim_backend)

    def _build_robot_factory(self) -> RobotFactory | None:
        """Build the Gazebo robot factory, or None to keep the headless fleet."""
        bridge = self._ros_bridge
        if self._settings.sim_mode != "gazebo":
            return None
        if bridge is None or not getattr(bridge, "is_running", False):
            _logger.warning(
                "gazebo_bridge_unavailable",
                sim_mode=self._settings.sim_mode,
                fallback="headless SimulationRobotAdapter",
            )
            return None

        from backend.ros.gazebo_transport import RosGazeboTransport

        def factory(robot_id: str, position: Vector2D, battery_pct: float) -> RobotAdapter:
            transport = RosGazeboTransport(robot_id, bridge)
            if not transport.attach():
                _logger.warning("gazebo_transport_attach_failed", robot=robot_id)
                return SimulationRobotAdapter(
                    robot_id=robot_id,
                    start_position=position,
                    battery_pct=battery_pct,
                )
            self._gazebo_robots += 1
            _logger.info("gazebo_robot_adapter", robot=robot_id)
            return GazeboRobotAdapter(robot_id, transport)

        return factory

    @property
    def orchestrator(self) -> FleetOrchestrator:
        """The live fleet orchestrator."""
        return self._orchestrator

    @property
    def mission(self) -> Mission | None:
        """The active mission record (None before configure())."""
        return self._mission

    def configure(self) -> Mission:
        """Generate and start a demo mission (deterministic from settings.seed)."""
        config = MissionConfig(
            robot_count=self._settings.robot_count,
            task_count=self._settings.task_count,
            seed=self._settings.seed,
            scenario_id=f"warehouse_v1_{self._settings.task_count}tasks",
        )
        self._mission = self._orchestrator.start_mission(self._settings.seed, config)
        return self._mission

    async def start(self) -> None:
        """Start the live orchestration loop.

        Does NOT auto-start a mission. Missions are started explicitly via
        start_mission() (Policy Runner or POST /api/v1/missions/). The run()
        loop is a no-op until a mission exists, so the backend boots cleanly
        with no running mission.
        """
        self._task = asyncio.create_task(self._orchestrator.run())

    def start_mission(
        self,
        robot_count: int,
        task_count: int,
        seed: int,
        policy: str,
        time_limit_s: float,
    ) -> Mission:
        """Replace the live mission with a new one (rebuilt orchestrator).

        Stops the current orchestration loop, rebuilds the orchestrator with the
        requested policy (so `policy` is honored at runtime), configures a
        deterministic mission, and restarts the loop. The WS broadcaster reads
        `self.orchestrator` / `self.mission` per tick, so it picks up the new
        mission on the next broadcast.
        """
        # Resolve the allocator BEFORE touching the live fleet: an unknown
        # policy must not cancel the running mission loop or leave the app
        # mission-less (ValueError surfaces to the API as a 422).
        allocator = allocator_by_name(policy)
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._orchestrator = FleetOrchestrator(
            allocator=allocator,
            rng=random.Random(seed),
            robot_factory=self._robot_factory,
        )
        config = MissionConfig(
            robot_count=robot_count,
            task_count=task_count,
            seed=seed,
            time_limit_s=time_limit_s,
            scenario_id=f"warehouse_v1_{task_count}tasks",
        )
        self._mission = self._orchestrator.start_mission(seed, config)
        self._task = asyncio.create_task(self._orchestrator.run())
        _logger.info("mission_started", mission_id=self._mission.id, policy=policy, seed=seed)
        return self._mission

    async def stop(self) -> None:
        """Stop the live orchestration loop."""
        if self._task is not None:
            self._task.cancel()
            self._task = None
