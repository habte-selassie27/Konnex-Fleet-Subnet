"""Mission lifecycle integration tests (Phase 5).

Covers MissionManager lifecycle transitions and task recovery bookkeeping:
PENDING -> RUNNING -> COMPLETE | FAILED | TIMED_OUT, plus
recover_tasks_from_robot unassignment semantics.

Status: COMPLETE (Phase 5).
"""

from fleet.mission_manager import MissionConfig, MissionManager, MissionStatus
from robotics.models.task import TaskStatus

CONFIG = MissionConfig(robot_count=5, task_count=10, seed=42, time_limit_s=600.0)


class TestMissionLifecycle:
    def test_create_mission_is_pending(self) -> None:
        mission, _scenario = MissionManager().create_mission(CONFIG)
        assert mission.status == MissionStatus.PENDING
        assert len(mission.tasks) == 10
        assert mission.task_count == 10
        assert mission.completed_tasks == 0

    def test_start_mission_runs(self) -> None:
        manager = MissionManager()
        mission, _ = manager.create_mission(CONFIG)
        manager.start(mission)
        assert mission.status == MissionStatus.RUNNING
        assert mission.started_at is not None

    def test_same_config_same_tasks(self) -> None:
        manager = MissionManager()
        first, _ = manager.create_mission(CONFIG)
        second, _ = manager.create_mission(CONFIG)
        assert [(task.id, task.pickup, task.delivery) for task in first.tasks] == [
            (task.id, task.pickup, task.delivery) for task in second.tasks
        ]

    def test_mission_completes_when_all_tasks_done(self) -> None:
        manager = MissionManager()
        mission, _ = manager.create_mission(CONFIG)
        manager.start(mission)
        for index, task in enumerate(mission.tasks):
            manager.complete_task(mission, task.id, float(index))
        assert mission.completed_tasks == 10
        manager.tick(mission, 10.0)
        assert mission.status == MissionStatus.COMPLETE
        assert mission.completed_at is not None

    def test_mission_times_out(self) -> None:
        manager = MissionManager()
        mission, _ = manager.create_mission(CONFIG)
        manager.start(mission)
        manager.tick(mission, CONFIG.time_limit_s + 1.0)
        assert mission.status == MissionStatus.TIMED_OUT
        assert mission.completed_at is not None

    def test_mission_halt_with_reason(self) -> None:
        manager = MissionManager()
        mission, _ = manager.create_mission(CONFIG)
        manager.start(mission)
        manager.halt(mission, "NO_ROBOTS")
        assert mission.status == MissionStatus.FAILED
        assert mission.halted_reason == "NO_ROBOTS"

    def test_recover_tasks_from_robot(self) -> None:
        manager = MissionManager()
        mission, _ = manager.create_mission(CONFIG)
        manager.start(mission)

        target = mission.tasks[0]
        target.status = TaskStatus.ASSIGNED
        target.assigned_robot_id = "robot_a"
        other = mission.tasks[1]
        other.status = TaskStatus.IN_PROGRESS
        other.assigned_robot_id = "robot_b"
        untouched = mission.tasks[2]  # still PENDING

        recovered = manager.recover_tasks_from_robot(mission, "robot_a")
        assert [task.id for task in recovered] == [target.id]
        assert target.status == TaskStatus.PENDING
        assert target.assigned_robot_id is None
        # Tasks held by other robots are untouched.
        assert other.status == TaskStatus.IN_PROGRESS
        assert other.assigned_robot_id == "robot_b"
        assert untouched.status == TaskStatus.PENDING

    def test_recover_does_not_uncomplete_tasks(self) -> None:
        manager = MissionManager()
        mission, _ = manager.create_mission(CONFIG)
        done = mission.tasks[0]
        done.status = TaskStatus.COMPLETED
        done.assigned_robot_id = "robot_a"
        recovered = manager.recover_tasks_from_robot(mission, "robot_a")
        assert recovered == []
        assert done.status == TaskStatus.COMPLETED

    def test_task_completion_rate(self) -> None:
        manager = MissionManager()
        mission, _ = manager.create_mission(CONFIG)
        manager.complete_task(mission, mission.tasks[0].id, 1.0)
        assert manager.task_completion_rate(mission) == 0.1
