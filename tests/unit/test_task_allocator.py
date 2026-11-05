"""Task allocator unit tests (TESTING_PLAN.md §3.1).

Status: COMPLETE (Phase 5).
"""

from fleet.task_allocator.cost_optimizer import CostOptimizerAllocator, CostWeights
from fleet.task_allocator.hungarian import HungarianAllocator
from fleet.task_allocator.nearest import NearestTaskAllocator
from robotics.models.robot_state import CommState, NavState, RobotState, Vector2D
from robotics.models.task import Priority, Task


def make_robot(
    robot_id: str, x: float, y: float, battery: float = 1.0, task_id: str | None = None
) -> RobotState:
    return RobotState(
        id=robot_id,
        position=Vector2D(x=x, y=y),
        battery_pct=battery,
        current_task_id=task_id,
        nav_state=NavState.IDLE,
        comm_state=CommState.ONLINE,
    )


def make_task(task_id: str, x: float, y: float, priority: Priority = Priority.MEDIUM) -> Task:
    return Task(
        id=task_id,
        pickup=Vector2D(x=x, y=y),
        delivery=Vector2D(x=x + 1, y=y + 1),
        priority=priority,
    )


class TestNearestAllocator:
    def test_single_robot_single_task(self) -> None:
        assignments = NearestTaskAllocator().assign(
            [make_robot("a", 0, 0)], [make_task("t1", 5, 0)]
        )
        assert len(assignments) == 1
        assert assignments[0].robot_id == "a"
        assert assignments[0].task_id == "t1"

    def test_multiple_robots_choose_nearest(self) -> None:
        assignments = NearestTaskAllocator().assign(
            [make_robot("a", 1, 0), make_robot("b", 10, 0)],
            [make_task("t1", 2, 0)],
        )
        assert assignments[0].robot_id == "a"

    def test_more_tasks_than_robots(self) -> None:
        robots = [make_robot("a", 0, 0), make_robot("b", 10, 0), make_robot("c", 20, 0)]
        tasks = [make_task(f"t{i}", float(i * 5), 0.0) for i in range(10)]
        assignments = NearestTaskAllocator().assign(robots, tasks)
        assert len(assignments) == 3  # one per available robot

    def test_more_robots_than_tasks(self) -> None:
        robots = [make_robot(f"r{i}", float(i), 0.0) for i in range(5)]
        assignments = NearestTaskAllocator().assign(
            robots, [make_task("t1", 0, 0), make_task("t2", 4, 0)]
        )
        assert len(assignments) == 2

    def test_robots_with_active_tasks_excluded(self) -> None:
        robots = [make_robot("a", 0, 0, task_id="busy"), make_robot("b", 10, 0)]
        assignments = NearestTaskAllocator().assign(robots, [make_task("t1", 5, 0)])
        assert len(assignments) == 1
        assert assignments[0].robot_id == "b"

    def test_does_not_mutate_inputs(self) -> None:
        robots = [make_robot("a", 0, 0)]
        tasks = [make_task("t1", 5, 0)]
        NearestTaskAllocator().assign(robots, tasks)
        assert tasks[0].status.value == "pending"
        assert robots[0].current_task_id is None


class TestHungarianAllocator:
    def test_optimal_assignment(self) -> None:
        robots = [make_robot("a", 0, 0), make_robot("b", 100, 100)]
        tasks = [make_task("t1", 1, 0), make_task("t2", 99, 100)]
        nearest_total = sum(a.distance for a in NearestTaskAllocator().assign(robots, tasks))
        hungarian_total = sum(a.distance for a in HungarianAllocator().assign(robots, tasks))
        assert hungarian_total <= nearest_total

    def test_empty_fleet(self) -> None:
        assert HungarianAllocator().assign([], [make_task("t1", 0, 0)]) == []

    def test_empty_task_queue(self) -> None:
        assert HungarianAllocator().assign([make_robot("a", 0, 0)], []) == []

    def test_cost_matrix_never_negative(self) -> None:
        robots = [make_robot("a", 0, 0), make_robot("b", 5, 5)]
        assignments = HungarianAllocator().assign(robots, [make_task("t1", 2, 2)])
        assert all(a.distance >= 0.0 for a in assignments)


class TestCostOptimizerAllocator:
    def test_prefers_high_battery_robot_all_else_equal(self) -> None:
        low = make_robot("low", 0, 0, battery=0.2)
        high = make_robot("high", 1.0, 0, battery=0.9)
        assignments = CostOptimizerAllocator().assign([low, high], [make_task("t1", 5, 5)])
        assert assignments[0].robot_id == "high"

    def test_penalizes_congested_path(self) -> None:
        crowd = [make_robot(f"c{i}", float(i), 0.0) for i in range(4)]  # near robot "a"
        a = make_robot("a", 0.0, 0.0, battery=0.8)
        b = make_robot("b", 0.0, 10.0, battery=0.8)
        robots = [a, *crowd, b]
        assignments = CostOptimizerAllocator().assign(robots, [make_task("t1", 1, 10)])
        assert assignments[0].robot_id == "b"  # uncongested robot wins

    def test_respects_task_priority(self) -> None:
        allocator = CostOptimizerAllocator()
        robot_a = make_robot("a", 0, 0)
        high = make_task("high", 50, 50, priority=Priority.HIGH)
        low = make_task("low", 50, 50, priority=Priority.LOW)
        assignments = allocator.assign([robot_a], [low, high])
        assert assignments[0].task_id == "high"  # high priority assigned first

    def test_custom_weights_applied(self) -> None:
        allocator = CostOptimizerAllocator(
            CostWeights(distance=1.0, battery=0.0, priority=0.0, congestion=0.0, collision_risk=0.0)
        )
        robots = [make_robot("a", 0, 0), make_robot("b", 50, 0)]
        assignments = allocator.assign(robots, [make_task("t1", 1, 0)])
        assert assignments[0].robot_id == "a"  # pure distance behavior

    def test_normalized_components(self) -> None:
        allocator = CostOptimizerAllocator()
        fleet = [make_robot("a", 0, 0), make_robot("b", 3, 0)]
        cost = allocator.cost(fleet[0], make_task("t1", 40, 30), fleet)
        assert 0.0 <= cost <= 1.0
