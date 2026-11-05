"""Fleet orchestration integration tests — Phase 5 gates.

Gates (Phase 5 task spec):
- mission completes with 1 robot failure mid-execution, success_rate > 0.5
- tasks reassigned to the remaining robots; fleet recovery time measured
- fleet halts gracefully when all robots fail (BATTERY_CRITICAL / NO_ROBOTS)
- collision rate stays acceptable during failure recovery

Status: COMPLETE (Phase 5, headless simulation).
"""

import random

from fleet.communication.model import CommConfig, CommunicationModel
from fleet.mission_manager import MissionConfig, MissionStatus
from fleet.orchestrator import (
    FailurePlan,
    FleetOrchestrator,
    MissionOutcome,
    OrchestratorConfig,
)
from fleet.task_allocator.nearest import NearestTaskAllocator
from robotics.models.failure import FailureType
from robotics.models.robot_state import NavState
from simulation.scenarios.scenario_generator import ScenarioGenerator

BASE_CONFIG = MissionConfig(
    robot_count=5,
    task_count=10,
    seed=42,
    time_limit_s=300.0,
    scenario_id="warehouse_v1_10tasks",
)


def make_orchestrator() -> FleetOrchestrator:
    """A fresh orchestrator with a generous step budget."""
    return FleetOrchestrator(
        allocator=NearestTaskAllocator(),
        config=OrchestratorConfig(max_steps=30_000),
    )


def run_with_failure(failure_type: FailureType, after_elapsed_s: float) -> MissionOutcome:
    """Run the seeded mission with one injected failure and return the outcome."""
    return make_orchestrator().run_mission(
        42,
        BASE_CONFIG,
        failure_plan=FailurePlan(
            robot_id="robot_1",
            failure_type=failure_type,
            after_elapsed_s=after_elapsed_s,
        ),
    )


class TestPartialFailureRecovery:
    def test_mission_completes_with_partial_failure(self) -> None:
        outcome = run_with_failure(FailureType.COMMUNICATION_LOSS, 10.0)
        assert outcome.status == "complete"
        assert outcome.tasks_completed == outcome.tasks_total
        success_rate = outcome.tasks_completed / outcome.tasks_total
        assert success_rate > 0.5
        assert outcome.failure_count >= 1

    def test_tasks_reassigned_to_remaining_robots(self) -> None:
        outcome = run_with_failure(FailureType.COMMUNICATION_LOSS, 10.0)
        remaining = {"robot_0", "robot_2", "robot_3", "robot_4"}
        completed_by = {
            task.robot_id for task in outcome.task_outcomes if task.status == "completed"
        }
        assert completed_by
        assert completed_by & remaining  # recovered tasks picked up by the remaining robots
        assert outcome.recovery_time_s is not None
        assert 0.0 <= outcome.recovery_time_s < outcome.elapsed_s

    def test_collision_rate_acceptable_during_recovery(self) -> None:
        outcome = run_with_failure(FailureType.COMMUNICATION_LOSS, 10.0)
        collision_rate = outcome.collision_count / outcome.tasks_total
        assert collision_rate < 0.5

    def test_communication_loss_fleet_continues(self) -> None:
        # Inject RobotCommunicationLoss: the robot stops accepting commands,
        # the fleet continues and still completes the mission.
        outcome = run_with_failure(FailureType.COMMUNICATION_LOSS, 5.0)
        assert outcome.status == "complete"
        assert outcome.tasks_completed == outcome.tasks_total

    def test_comm_degradation_wired_into_health_checks(self) -> None:
        # Phase 5: the communication degradation model (latency + packet loss)
        # must affect missions end-to-end. A lossy channel drops telemetry in
        # the orchestrator's 5 Hz health poll, yet the fleet still completes.
        orchestrator = FleetOrchestrator(
            allocator=NearestTaskAllocator(),
            config=OrchestratorConfig(max_steps=30_000),
            comm=CommunicationModel(CommConfig(packet_loss_rate=0.3)),
            rng=random.Random(7),
        )
        outcome = orchestrator.run_mission(
            42,
            BASE_CONFIG,
            failure_plan=FailurePlan(
                robot_id="robot_1",
                failure_type=FailureType.COMMUNICATION_LOSS,
                after_elapsed_s=10.0,
            ),
        )
        assert orchestrator._comm.stats.packets_lost > 0  # channel was actually lossy
        assert outcome.status == "complete"
        assert outcome.tasks_completed == outcome.tasks_total

    def test_navigation_failure_reroutes_tasks(self) -> None:
        # Inject RobotNavigationFailure: the orchestrator reroutes the robot's
        # tasks to the remaining fleet.
        outcome = run_with_failure(FailureType.NAVIGATION_FAILURE, 8.0)
        assert outcome.status == "complete"
        assert outcome.tasks_completed == outcome.tasks_total
        assert outcome.failure_count >= 1


class TestFleetHaltBehavior:
    def test_orchestrator_handles_all_robots_low_battery(self) -> None:
        # All robots start below the critical 10% battery: the orchestrator
        # sends them to charge and halts the mission with NO_ROBOTS instead of
        # failing silently or looping forever.
        orchestrator = make_orchestrator()
        scenario = ScenarioGenerator().generate(
            seed=42, robot_count=5, task_count=10, battery_range=(0.04, 0.04)
        )
        mission = orchestrator.configure(scenario, BASE_CONFIG)
        for _ in range(50):
            orchestrator.step(0.1)
            if mission.status != MissionStatus.RUNNING:
                break
        assert mission.status == MissionStatus.FAILED
        assert mission.halted_reason == "NO_ROBOTS"
        assert mission.completed_tasks < mission.task_count

    def test_fleet_halts_when_all_robots_fail(self) -> None:
        # Inject RobotShutdown into every robot: the mission halts with
        # NO_ROBOTS rather than spinning forever.
        orchestrator = make_orchestrator()
        mission = orchestrator.start_mission(42, BASE_CONFIG)
        for index in range(5):
            orchestrator.inject_failure(f"robot_{index}", FailureType.SHUTDOWN)
        for _ in range(200):
            orchestrator.step(0.1)
            if mission.status != MissionStatus.RUNNING:
                break
        assert mission.status == MissionStatus.FAILED
        assert mission.halted_reason == "NO_ROBOTS"
        assert mission.completed_tasks < mission.task_count

    def test_battery_critical_sends_robot_to_charger(self) -> None:
        # Inject RobotBatteryCritical on one robot: it navigates to the
        # charging station while the rest of the fleet keeps working.
        orchestrator = make_orchestrator()
        scenario = ScenarioGenerator().generate(seed=42, robot_count=5, task_count=10)
        scenario.robot_battery_pcts = [0.05, 0.9, 0.9, 0.9, 0.9]
        mission = orchestrator.configure(scenario, BASE_CONFIG)
        for _ in range(3):
            orchestrator.step(0.1)
        states = {state.id: state for state in orchestrator.get_fleet_state().robots}
        assert states["robot_0"].nav_state == NavState.CHARGING
        for _ in range(5000):
            orchestrator.step(0.1)
            if mission.status != MissionStatus.RUNNING:
                break
        assert mission.status == MissionStatus.COMPLETE
        assert mission.completed_tasks == mission.task_count
