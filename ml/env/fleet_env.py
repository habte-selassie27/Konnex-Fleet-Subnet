"""FleetEnv — multi-agent Gymnasium environment.

Spec (AGENTS.md §8.0, BUILD.md §7):
    One agent per robot. CTDE: centralized training, decentralized execution.
    Dict observation space per agent. High-level continuous action: a target
    waypoint relative to the robot (normalized to [-1, 1], scaled to ±20 m).
    A deterministic potential-field controller turns walls and shelves into
    repulsive forces and drives the robot toward the target.
    Reward: task completion + dense shaping + collision penalties.

The battery model is normalized to a mission-length episode: a robot starting
at 100% lasts ~1200 s of continuous movement, so a 600 s mission does not end
because every robot died after ~100 steps. This was the main reason the
previous "5M timestep" run completed in only ~31k short episodes without
learning any useful task behaviour.
"""

from __future__ import annotations

import heapq
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Any

import gymnasium as gym
import numpy as np
import numpy.typing as npt
from gymnasium import spaces

from ml.env.assignment import (
    AssignmentProvider,
    RobotView,
    TaskView,
)
from simulation.scenarios.scenario_generator import ScenarioGenerator

NDArray = npt.NDArray[np.float32]

# Environment actions are a target waypoint relative to the robot, normalized
# to [-1, 1] and scaled by this distance (see `_step_robot`). Harness policies
# that emit waypoints (expert, allocator-driven) must use the same scale.
ACTION_SCALE_M = 20.0

N_LIDAR_BINS = 36
N_NEARBY_ROBOTS = 4
N_PENDING_TASKS = 3
_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

# Battery is a fraction in [0, 1]. A full charge lasts ~1200 s of movement,
# i.e. two full 600 s mission limits.
BATTERY_DRAIN_MOVING_PER_S = 1.0 / 1200.0
BATTERY_DRAIN_IDLE_PER_S = 0.2 / 1200.0

REWARD_PICKUP = 5.0
REWARD_DELIVERY = 10.0
REWARD_COLLISION = -1.0
REWARD_MISSION_COMPLETE = 20.0
SHAPING_SCALE = 1.0
# Per-step cost of mission time (efficiency pressure; must stay negative).
STEP_COST = 0.01

# ── Navigation / obstacle model ────────────────────────────────────────────
# The env keeps a coarse occupancy grid (0.5 m cells) built from world walls
# and shelf rectangles. The low-level controller uses a repulsive potential
# field over that grid, so the learned policy only has to pick a target.
WORLD_WIDTH_M = 40.0
WORLD_HEIGHT_M = 30.0
GRID_RES_M = 0.5
ROBOT_RADIUS_M = 0.35
MAX_LINEAR_MPS = 1.0
MAX_ANGULAR_RPS = 1.5
REPULSE_RADIUS_M = 1.8
REPULSE_GAIN = 1.0
REPULSE_MAX = 2.5
FORWARD_STOP_M = 0.3
DOCK_RADIUS_M = 2.5
ROBOT_AVOID_RADIUS_M = 1.2
ROBOT_AVOID_GAIN = 1.2
ROBOT_AVOID_MAX = 2.0
ROBOT_YIELD_DIST_M = 1.0
ROBOT_YIELD_SPEED = 0.35
STUCK_WINDOW_STEPS = 20
STUCK_MIN_MOVEMENT_M = 0.15
RECOVERY_STEPS = 15
GOAL_TOLERANCE_M = 0.15


@dataclass
class FleetEnvConfig:
    robot_count: int = 5
    task_count: int = 20
    obstacle_count: int = 15
    seed: int = 42
    time_limit_s: float = 600.0
    sim_frequency_hz: float = 10.0
    world: str = "warehouse_v1"


class FleetEnv(gym.Env[Any, Any]):
    """Multi-agent fleet environment.

    Each agent controls one robot. Agents receive local observations
    and return [linear_vel, angular_vel] actions.
    """

    metadata = {"render_modes": ["human"], "render_fps": 10}

    def __init__(self, config: FleetEnvConfig | None = None) -> None:
        super().__init__()
        self.config = config or FleetEnvConfig()
        self.n_agents = self.config.robot_count

        self.observation_space = spaces.Dict(
            {
                "pos": spaces.Box(-60.0, 60.0, (2,), np.float32),
                "vel": spaces.Box(-2.0, 2.0, (2,), np.float32),
                "orientation": spaces.Box(-math.pi, math.pi, (1,), np.float32),
                "battery": spaces.Box(0.0, 1.0, (1,), np.float32),
                "has_task": spaces.Discrete(2),
                "task_pickup": spaces.Box(-60.0, 60.0, (2,), np.float32),
                "task_delivery": spaces.Box(-60.0, 60.0, (2,), np.float32),
                "task_progress": spaces.Box(0.0, 1.0, (1,), np.float32),
                "task_phase": spaces.Box(-1.0, 1.0, (1,), np.float32),
                "lidar": spaces.Box(0.0, 15.0, (N_LIDAR_BINS,), np.float32),
                "nearby_robots": spaces.Box(-60.0, 60.0, (N_NEARBY_ROBOTS, 2), np.float32),
                "nearby_battery": spaces.Box(0.0, 1.0, (N_NEARBY_ROBOTS,), np.float32),
                "pending_tasks": spaces.Box(-60.0, 60.0, (N_PENDING_TASKS, 2), np.float32),
                "fleet_utilization": spaces.Box(0.0, 1.0, (1,), np.float32),
                "tasks_remaining_frac": spaces.Box(0.0, 1.0, (1,), np.float32),
                "time_remaining_frac": spaces.Box(0.0, 1.0, (1,), np.float32),
            }
        )

        self.action_space = spaces.Box(
            low=np.array([-1.0, -1.0], dtype=np.float32),
            high=np.array([1.0, 1.0], dtype=np.float32),
            dtype=np.float32,
        )

        self._robots: list[_RobotState] = []
        self._tasks: list[_TaskState] = []
        self._shelves: list[tuple[float, float, float, float]] = []
        self._occupancy = np.zeros(
            (int(WORLD_HEIGHT_M / GRID_RES_M), int(WORLD_WIDTH_M / GRID_RES_M)), dtype=bool
        )
        self._recent_positions: dict[str, deque[tuple[float, float]]] = {}
        self._recent_moving: dict[str, deque[bool]] = {}
        self._recovery_steps: dict[str, int] = {}
        self._paths: dict[str, list[tuple[float, float]]] = {}
        self._path_goals: dict[str, tuple[float, float]] = {}
        self._path_age: dict[str, int] = {}
        self._episode_steps = 0
        self._max_steps = int(self.config.time_limit_s * self.config.sim_frequency_hz)
        self._collision_count = 0
        self._mission_complete = False
        self._initial_battery: list[float] = []
        self._events: dict[str, list[str]] = {}
        self._shaping: dict[str, float] = {}
        self._active_collisions: set[tuple[str, str]] = set()
        self._assignment_provider: AssignmentProvider | None = None

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,  # noqa: ARG002 -- Gymnasium override contract
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        super().reset(seed=seed)
        scenario_seed = seed if seed is not None else self.config.seed
        self._init_scenario(scenario_seed)
        self._episode_steps = 0
        self._mission_complete = False
        self._events = {r.id: [] for r in self._robots}
        self._shaping = {r.id: 0.0 for r in self._robots}
        self._active_collisions = set()
        self._recent_positions = {r.id: deque(maxlen=STUCK_WINDOW_STEPS) for r in self._robots}
        self._recent_moving = {r.id: deque(maxlen=STUCK_WINDOW_STEPS) for r in self._robots}
        self._recovery_steps = {r.id: 0 for r in self._robots}
        self._paths = {}
        self._path_goals = {}
        self._path_age = {}

        # A benchmark provider must see assignments before the first action,
        # otherwise every episode pays a wasted tick. Only do this when a
        # provider is installed so trained-policy dynamics stay byte-identical.
        if self._assignment_provider is not None:
            unassigned = [t for t in self._tasks if not t.completed and not t.assigned_to]
            idle_robots = [r for r in self._robots if not r.failed]
            self._assign_pending(idle_robots, unassigned)

        obs_dict = {self._agent_id(i): self._build_obs(i) for i in range(self.n_agents)}
        return obs_dict, {}

    def step(  # type: ignore[override]  # multi-agent env returns per-agent dicts
        self, actions: dict[str, NDArray]
    ) -> tuple[
        dict[str, Any],
        dict[str, float],
        dict[str, bool],
        dict[str, bool],
        dict[str, Any],
    ]:
        self._episode_steps += 1
        self._events = {r.id: [] for r in self._robots}
        self._shaping = {r.id: 0.0 for r in self._robots}

        previous_distances = {r.id: self._distance_to_target(i) for i, r in enumerate(self._robots)}

        for agent_id, action in actions.items():
            idx = self._agent_idx(agent_id)
            if idx is not None:
                self._step_robot(idx, action)

        self._update_tasks()
        self._check_collisions()

        obs: dict[str, Any] = {}
        rewards: dict[str, float] = {}
        terminated: dict[str, bool] = {}
        for agent_id in actions:
            idx = self._agent_idx(agent_id)
            if idx is None:
                continue
            obs[agent_id] = self._build_obs(idx)
            robot = self._robots[idx]
            new_distance = self._distance_to_target(idx)
            task_changed = any(
                event in {"pickup", "delivery"} for event in self._events.get(robot.id, [])
            )
            if (
                not self._mission_complete
                and not task_changed
                and math.isfinite(previous_distances[robot.id])
                and math.isfinite(new_distance)
            ):
                self._shaping[robot.id] = SHAPING_SCALE * (
                    previous_distances[robot.id] - new_distance
                )
            rewards[agent_id] = self._compute_reward(idx)
            terminated[agent_id] = robot.failed or self._mission_complete

        all_agents_failed = bool(terminated) and all(terminated.values())
        mission_over = self._mission_complete or all_agents_failed
        for agent_id in terminated:
            if mission_over:
                terminated[agent_id] = True
        at_time_limit = not mission_over and self._episode_steps >= self._max_steps
        truncated = dict.fromkeys(actions, at_time_limit)
        terminated["__all__"] = mission_over
        truncated["__all__"] = at_time_limit

        info: dict[str, Any] = {
            "__all__": {
                "tasks_completed": sum(1 for t in self._tasks if t.completed),
                "tasks_total": len(self._tasks),
                "collision_count": self._collision_count,
                "episode_steps": self._episode_steps,
                "elapsed_s": self._episode_steps / self.config.sim_frequency_hz,
                "energy_consumed": self.energy_consumed(),
                "mission_complete": self._mission_complete,
            }
        }

        return obs, rewards, terminated, truncated, info

    @property
    def agent_ids(self) -> list[str]:
        return [self._agent_id(i) for i in range(self.n_agents)]

    @property
    def mission_complete(self) -> bool:
        return self._mission_complete

    def tasks_completed(self) -> int:
        return sum(1 for t in self._tasks if t.completed)

    def tasks_total(self) -> int:
        return len(self._tasks)

    def energy_consumed(self) -> float:
        """Battery percentage points consumed, summed over robots."""
        return float(
            sum(
                max(0.0, initial - robot.battery) * 100.0
                for initial, robot in zip(self._initial_battery, self._robots, strict=False)
            )
        )

    def _agent_id(self, idx: int) -> str:
        return f"robot_{idx}"

    def _agent_idx(self, agent_id: str) -> int | None:
        try:
            return int(agent_id.split("_")[1])
        except (IndexError, ValueError):
            return None

    def _init_scenario(self, seed: int) -> None:
        gen = ScenarioGenerator()
        scenario = gen.generate(
            seed=seed,
            robot_count=self.config.robot_count,
            task_count=self.config.task_count,
        )
        self._robots = [
            _RobotState(
                id=f"robot_{i}",
                x=scenario.robot_positions[i].x,
                y=scenario.robot_positions[i].y,
                theta=0.0,
                battery=scenario.robot_battery_pcts[i],
            )
            for i in range(scenario.robot_count)
        ]
        self._tasks = [
            _TaskState(
                id=task.id,
                pickup_x=task.pickup.x,
                pickup_y=task.pickup.y,
                delivery_x=task.delivery.x,
                delivery_y=task.delivery.y,
                priority=_PRIORITY_RANK[task.priority.value],
            )
            for task in scenario.tasks
        ]
        self._collision_count = 0
        self._initial_battery = [r.battery for r in self._robots]
        self._shelves = self._generate_shelves(seed)
        self._build_occupancy()

    def _generate_shelves(self, seed: int) -> list[tuple[float, float, float, float]]:
        """Deterministically place shelf rectangles clear of robots and tasks.

        Shelves are generated inside the env (not the shared ScenarioGenerator)
        so the orchestrator's scenario contract is untouched. Any shelf that
        would overlap a robot start or a task endpoint is rejected, which keeps
        every task reachable.
        """
        rng = random.Random(seed ^ 0x5EED)
        shelves: list[tuple[float, float, float, float]] = []
        attempts = 0
        while len(shelves) < self.config.obstacle_count and attempts < 1000:
            attempts += 1
            long_side = rng.uniform(2.5, 4.5)
            short_side = rng.uniform(0.6, 1.0)
            if rng.random() < 0.5:
                width, depth = long_side, short_side
            else:
                width, depth = short_side, long_side
            cx = rng.uniform(2.5, WORLD_WIDTH_M - 2.5)
            cy = rng.uniform(2.5, WORLD_HEIGHT_M - 2.5)
            rect = (cx - width / 2, cy - depth / 2, cx + width / 2, cy + depth / 2)

            if any(_rect_contains_point(rect, r.x, r.y, margin=0.8) for r in self._robots):
                continue
            if any(
                _rect_contains_point(rect, t.pickup_x, t.pickup_y, margin=0.8)
                or _rect_contains_point(rect, t.delivery_x, t.delivery_y, margin=0.8)
                for t in self._tasks
            ):
                continue
            if any(_rects_overlap(rect, other, margin=0.6) for other in shelves):
                continue
            shelves.append(rect)
        return shelves

    def _build_occupancy(self) -> None:
        """Rasterize walls and robot-inflated shelves into the occupancy grid."""
        height, width = self._occupancy.shape
        self._occupancy[:] = False
        self._occupancy[0, :] = True
        self._occupancy[-1, :] = True
        self._occupancy[:, 0] = True
        self._occupancy[:, -1] = True
        for x0, y0, x1, y1 in self._shelves:
            ix0 = max(0, int((x0 - ROBOT_RADIUS_M) / GRID_RES_M))
            ix1 = min(width - 1, int((x1 + ROBOT_RADIUS_M) / GRID_RES_M))
            iy0 = max(0, int((y0 - ROBOT_RADIUS_M) / GRID_RES_M))
            iy1 = min(height - 1, int((y1 + ROBOT_RADIUS_M) / GRID_RES_M))
            self._occupancy[iy0 : iy1 + 1, ix0 : ix1 + 1] = True

    def _build_obs(self, robot_idx: int) -> dict[str, NDArray]:
        r = self._robots[robot_idx]
        task = self._get_assigned_task(robot_idx)

        # Relative to the robot so the policy can learn "move toward target"
        # without having to discover the subtraction itself.
        if task:
            pickup = np.array([task.pickup_x - r.x, task.pickup_y - r.y], dtype=np.float32)
            delivery = np.array([task.delivery_x - r.x, task.delivery_y - r.y], dtype=np.float32)
        else:
            pickup = np.zeros(2, dtype=np.float32)
            delivery = np.zeros(2, dtype=np.float32)

        progress = 0.0
        if task:
            if not task.picked_up:
                dist = math.dist((r.x, r.y), (task.pickup_x, task.pickup_y))
                progress = 0.5 * max(0.0, 1.0 - min(1.0, dist / 20.0))
            else:
                dist = math.dist((r.x, r.y), (task.delivery_x, task.delivery_y))
                progress = 0.5 + 0.5 * max(0.0, 1.0 - min(1.0, dist / 20.0))

        nearby = self._get_nearby_robots(robot_idx)
        nearby_pos = np.zeros((N_NEARBY_ROBOTS, 2), dtype=np.float32)
        nearby_bat = np.zeros(N_NEARBY_ROBOTS, dtype=np.float32)
        for i, (nx, ny, nb) in enumerate(nearby[:N_NEARBY_ROBOTS]):
            nearby_pos[i] = [nx - r.x, ny - r.y]
            nearby_bat[i] = nb

        pending = self._get_nearest_pending_tasks(robot_idx)
        pending_pos = np.zeros((N_PENDING_TASKS, 2), dtype=np.float32)
        for i, (px, py) in enumerate(pending[:N_PENDING_TASKS]):
            pending_pos[i] = [px - r.x, py - r.y]

        pending_total = sum(1 for t in self._tasks if not t.completed and not t.assigned_to)
        elapsed_frac = self._episode_steps / self._max_steps if self._max_steps > 0 else 0.0

        return {
            "pos": np.array([r.x, r.y], dtype=np.float32),
            "vel": np.array([r.vx, r.vy], dtype=np.float32),
            "orientation": np.array([r.theta], dtype=np.float32),
            "battery": np.array([r.battery], dtype=np.float32),
            "has_task": np.array(1 if task is not None else 0, dtype=np.int64),
            "task_pickup": pickup,
            "task_delivery": delivery,
            "task_progress": np.array([progress], dtype=np.float32),
            "task_phase": np.array(
                [-1.0 if task is None else (1.0 if task.picked_up else 0.0)], dtype=np.float32
            ),
            "lidar": self._simulate_lidar(robot_idx),
            "nearby_robots": nearby_pos,
            "nearby_battery": nearby_bat,
            "pending_tasks": pending_pos,
            "fleet_utilization": np.array([self._fleet_utilization()], dtype=np.float32),
            "tasks_remaining_frac": np.array(
                [pending_total / max(1, len(self._tasks))], dtype=np.float32
            ),
            "time_remaining_frac": np.array([1.0 - elapsed_frac], dtype=np.float32),
        }

    def _step_robot(self, idx: int, action: NDArray) -> None:
        r = self._robots[idx]
        if r.failed:
            return

        dt = 1.0 / self.config.sim_frequency_hz

        # High-level: action is a target waypoint relative to the robot.
        target_dx = float(np.clip(action[0], -1.0, 1.0)) * 20.0
        target_dy = float(np.clip(action[1], -1.0, 1.0)) * 20.0
        target = (
            max(0.5, min(WORLD_WIDTH_M - 0.5, r.x + target_dx)),
            max(0.5, min(WORLD_HEIGHT_M - 0.5, r.y + target_dy)),
        )
        # Docking assist: when the requested waypoint is near the assigned
        # task's current dock (pickup before pickup, delivery after), snap to
        # the exact dock so a coarse policy waypoint still enters the 0.5 m
        # pickup/delivery radius. Real AMRs use fiducials for the same job.
        task = self._get_assigned_task(idx)
        if task is not None:
            dock = (
                (task.pickup_x, task.pickup_y)
                if not task.picked_up
                else (task.delivery_x, task.delivery_y)
            )
            if math.dist(target, dock) < DOCK_RADIUS_M:
                target = dock
        goal_dist = math.hypot(target[0] - r.x, target[1] - r.y)

        # Stuck detection: if the robot barely moved over the last window while
        # it was supposed to be driving, rotate away from the nearest obstacle
        # to escape corners and local minima.
        recent = self._recent_positions.setdefault(r.id, deque(maxlen=STUCK_WINDOW_STEPS))
        recent.append((r.x, r.y))
        moving = self._recent_moving.setdefault(r.id, deque(maxlen=STUCK_WINDOW_STEPS))
        recovering = self._recovery_steps.get(r.id, 0) > 0
        if not recovering and (
            len(recent) >= STUCK_WINDOW_STEPS
            and sum(moving) >= STUCK_WINDOW_STEPS - 5
            and goal_dist > GOAL_TOLERANCE_M
            and _path_length(recent) < STUCK_MIN_MOVEMENT_M
        ):
            self._recovery_steps[r.id] = RECOVERY_STEPS
            self._paths.pop(r.id, None)
            recovering = True

        if recovering:
            self._recovery_steps[r.id] = max(0, self._recovery_steps.get(r.id, 0) - 1)
            rx, ry = self._repulsion(r.x, r.y)
            if abs(rx) + abs(ry) > 1e-6:
                escape = math.atan2(ry, rx)
                direction = 1.0 if _wrap_pi(escape - r.theta) >= 0 else -1.0
            else:
                direction = 1.0
            r.theta = _wrap_pi(r.theta + direction * MAX_ANGULAR_RPS * dt)
            lin_vel = 0.0
        elif goal_dist <= GOAL_TOLERANCE_M:
            lin_vel = 0.0
        else:
            waypoint = self._next_waypoint(r, target)
            wx, wy = waypoint
            wdx, wdy = wx - r.x, wy - r.y
            wdist = math.hypot(wdx, wdy)
            if wdist < 1e-6:
                lin_vel = 0.0
            else:
                gx, gy = wdx / wdist, wdy / wdist
                # Reciprocal robot-robot repulsion: a low-level safety layer,
                # like the LiDAR-based avoidance a real AMR runs under Nav2.
                rx, ry = self._robot_repulsion(idx, r.x, r.y)
                desired = math.atan2(gy + ry, gx + rx)
                err = _wrap_pi(desired - r.theta)
                r.theta = _wrap_pi(
                    r.theta + float(np.clip(4.0 * err, -MAX_ANGULAR_RPS, MAX_ANGULAR_RPS)) * dt
                )
                # Stop-and-turn: driving while badly misaligned makes the
                # robot orbit its target instead of converging on it.
                if abs(err) > 0.5:
                    lin_vel = 0.0
                else:
                    on_final_leg = not self._paths.get(r.id)
                    slow = min(1.0, goal_dist / 0.8) if on_final_leg else 1.0
                    lin_vel = MAX_LINEAR_MPS * slow
                if self._robot_ahead(idx, r.x, r.y, r.theta, ROBOT_YIELD_DIST_M):
                    lin_vel = min(lin_vel, ROBOT_YIELD_SPEED)
                if self._blocked_ahead(r.x, r.y, r.theta, FORWARD_STOP_M):
                    lin_vel = 0.0

        r.vx = lin_vel * math.cos(r.theta)
        r.vy = lin_vel * math.sin(r.theta)
        r.x = max(0.5, min(WORLD_WIDTH_M - 0.5, r.x + r.vx * dt))
        r.y = max(0.5, min(WORLD_HEIGHT_M - 0.5, r.y + r.vy * dt))
        moving.append(lin_vel > 0.01)

        rate = BATTERY_DRAIN_MOVING_PER_S if abs(lin_vel) > 0.01 else BATTERY_DRAIN_IDLE_PER_S
        r.battery = max(0.0, r.battery - rate * dt)
        if r.battery <= 0.0:
            r.failed = True

    def _robot_repulsion(self, idx: int, x: float, y: float) -> tuple[float, float]:
        """Repulsion from nearby robots (reciprocal collision avoidance)."""
        rx = 0.0
        ry = 0.0
        for j, other in enumerate(self._robots):
            if j == idx or other.failed:
                continue
            dx, dy = x - other.x, y - other.y
            dist = math.hypot(dx, dy)
            if dist < 1e-6 or dist >= ROBOT_AVOID_RADIUS_M:
                continue
            magnitude = ROBOT_AVOID_GAIN * (1.0 / dist - 1.0 / ROBOT_AVOID_RADIUS_M)
            rx += magnitude * dx / dist
            ry += magnitude * dy / dist
        norm = math.hypot(rx, ry)
        if norm > ROBOT_AVOID_MAX:
            rx *= ROBOT_AVOID_MAX / norm
            ry *= ROBOT_AVOID_MAX / norm
        return rx, ry

    def _robot_ahead(self, idx: int, x: float, y: float, theta: float, distance: float) -> bool:
        """True when another robot is inside the forward cone within `distance`."""
        ca, sa = math.cos(theta), math.sin(theta)
        for j, other in enumerate(self._robots):
            if j == idx or other.failed:
                continue
            dx, dy = other.x - x, other.y - y
            dist = math.hypot(dx, dy)
            if dist < 1e-6 or dist > distance:
                continue
            if (dx * ca + dy * sa) / dist > 0.5:
                return True
        return False

    def _next_waypoint(
        self, robot: _RobotState, target: tuple[float, float]
    ) -> tuple[float, float]:
        """Return the next A* waypoint toward `target`, replanning when stale."""
        path = self._paths.get(robot.id)
        cached_goal = self._path_goals.get(robot.id)
        age = self._path_age.get(robot.id, 0)
        stale = (
            path is None or cached_goal is None or math.dist(cached_goal, target) > 3.0 or age > 150
        )
        if stale:
            path = self._plan_path((robot.x, robot.y), target)
            self._paths[robot.id] = path
            self._path_goals[robot.id] = target
            self._path_age[robot.id] = 0
        else:
            self._path_age[robot.id] = age + 1

        while path and math.dist((robot.x, robot.y), path[0]) < 0.4:
            path.pop(0)
        if not path:
            # Path exhausted but target not reached (clamped / shifted goal):
            # force a replan on the next step.
            if math.dist((robot.x, robot.y), target) > GOAL_TOLERANCE_M:
                self._paths.pop(robot.id, None)
            return target
        return path[0]

    def _plan_path(
        self, start: tuple[float, float], goal: tuple[float, float]
    ) -> list[tuple[float, float]]:
        """A* over the occupancy grid, simplified with line-of-sight shortcuts."""
        height, width = self._occupancy.shape
        start_cell = (
            min(height - 1, max(0, int(start[1] / GRID_RES_M))),
            min(width - 1, max(0, int(start[0] / GRID_RES_M))),
        )
        goal_cell = (
            min(height - 1, max(0, int(goal[1] / GRID_RES_M))),
            min(width - 1, max(0, int(goal[0] / GRID_RES_M))),
        )
        if self._occupancy[start_cell]:
            start_cell = self._nearest_free(start_cell)
        if self._occupancy[goal_cell]:
            goal_cell = self._nearest_free(goal_cell)
        if start_cell == goal_cell:
            return [goal]

        open_heap: list[tuple[float, float, tuple[int, int]]] = [(0.0, 0.0, start_cell)]
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        g_score: dict[tuple[int, int], float] = {start_cell: 0.0}
        closed: set[tuple[int, int]] = set()
        diagonal = math.sqrt(2.0)

        while open_heap:
            _, current_g, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            closed.add(current)
            if current == goal_cell:
                cells = [current]
                while current in came_from:
                    current = came_from[current]
                    cells.append(current)
                cells.reverse()
                points = [((ix + 0.5) * GRID_RES_M, (iy + 0.5) * GRID_RES_M) for iy, ix in cells]
                points[-1] = goal
                return self._simplify_path(start, points)
            for diy in (-1, 0, 1):
                for dix in (-1, 0, 1):
                    if dix == 0 and diy == 0:
                        continue
                    iy, ix = current[0] + diy, current[1] + dix
                    if not (0 <= iy < height and 0 <= ix < width):
                        continue
                    if self._occupancy[iy, ix]:
                        continue
                    # No diagonal corner cutting.
                    if dix != 0 and diy != 0:
                        if self._occupancy[current[0], ix] or self._occupancy[iy, current[1]]:
                            continue
                    step = diagonal if dix != 0 and diy != 0 else 1.0
                    tentative = current_g + step
                    neighbor = (iy, ix)
                    if tentative < g_score.get(neighbor, float("inf")):
                        g_score[neighbor] = tentative
                        came_from[neighbor] = current
                        heuristic = math.hypot(ix - goal_cell[1], iy - goal_cell[0])
                        heapq.heappush(open_heap, (tentative + heuristic, tentative, neighbor))
        return [goal]

    def _simplify_path(
        self, start: tuple[float, float], points: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        """String-pull the A* path so the robot drives long straight segments."""
        if not points:
            return points
        simplified: list[tuple[float, float]] = []
        cursor = start
        index = 0
        while index < len(points):
            farthest = len(points) - 1
            while farthest > index and not self._line_clear(cursor, points[farthest]):
                farthest -= 1
            simplified.append(points[farthest])
            cursor = points[farthest]
            index = farthest + 1
        return simplified

    def _line_clear(self, a: tuple[float, float], b: tuple[float, float]) -> bool:
        """True when the straight segment a→b crosses no blocked grid cell."""
        distance = math.dist(a, b)
        if distance < 1e-6:
            return True
        height, width = self._occupancy.shape
        samples = int(distance / (GRID_RES_M * 0.5)) + 1
        for k in range(1, samples):
            t = k / samples
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t
            if x < 0.0 or x >= WORLD_WIDTH_M or y < 0.0 or y >= WORLD_HEIGHT_M:
                return False
            if self._occupancy[int(y / GRID_RES_M), int(x / GRID_RES_M)]:
                return False
        return True

    def _nearest_free(self, cell: tuple[int, int]) -> tuple[int, int]:
        """Nearest free cell to `cell` (ring search, used when a goal is blocked)."""
        height, width = self._occupancy.shape
        if not self._occupancy[cell]:
            return cell
        for radius in range(1, 12):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    iy, ix = cell[0] + dy, cell[1] + dx
                    if 0 <= iy < height and 0 <= ix < width and not self._occupancy[iy, ix]:
                        return (iy, ix)
        return cell

    def _repulsion(self, x: float, y: float) -> tuple[float, float]:
        """Repulsive potential-field vector from nearby blocked grid cells."""
        rx = 0.0
        ry = 0.0
        cx = int(x / GRID_RES_M)
        cy = int(y / GRID_RES_M)
        radius_cells = int(math.ceil(REPULSE_RADIUS_M / GRID_RES_M))
        height, width = self._occupancy.shape
        for iy in range(max(0, cy - radius_cells), min(height, cy + radius_cells + 1)):
            for ix in range(max(0, cx - radius_cells), min(width, cx + radius_cells + 1)):
                if not self._occupancy[iy, ix]:
                    continue
                cell_x = (ix + 0.5) * GRID_RES_M
                cell_y = (iy + 0.5) * GRID_RES_M
                dx, dy = x - cell_x, y - cell_y
                dist = math.hypot(dx, dy)
                if dist < 1e-6:
                    dx, dy, dist = 1.0, 0.0, 1.0
                if dist < REPULSE_RADIUS_M:
                    magnitude = REPULSE_GAIN * (1.0 / dist - 1.0 / REPULSE_RADIUS_M)
                    rx += magnitude * dx / dist
                    ry += magnitude * dy / dist
        norm = math.hypot(rx, ry)
        if norm > REPULSE_MAX:
            rx *= REPULSE_MAX / norm
            ry *= REPULSE_MAX / norm
        return rx, ry

    def _blocked_ahead(self, x: float, y: float, theta: float, distance: float) -> bool:
        """True when a blocked cell lies within `distance` straight ahead."""
        ca, sa = math.cos(theta), math.sin(theta)
        height, width = self._occupancy.shape
        step = GRID_RES_M
        d = step
        while d <= distance + 1e-9:
            gx = x + d * ca
            gy = y + d * sa
            if gx < 0.0 or gx >= WORLD_WIDTH_M or gy < 0.0 or gy >= WORLD_HEIGHT_M:
                return True
            if self._occupancy[int(gy / GRID_RES_M), int(gx / GRID_RES_M)]:
                return True
            d += step
        return False

    def _distance_to_target(self, robot_idx: int) -> float:
        robot = self._robots[robot_idx]
        task = self._get_assigned_task(robot_idx)
        if task is None:
            return float("inf")
        target = (
            (task.pickup_x, task.pickup_y)
            if not task.picked_up
            else (
                task.delivery_x,
                task.delivery_y,
            )
        )
        return math.dist((robot.x, robot.y), target)

    def _get_assigned_task(self, robot_idx: int) -> _TaskState | None:
        robot_id = self._robots[robot_idx].id
        for t in self._tasks:
            if t.assigned_to == robot_id and not t.completed:
                return t
        return None

    # ── Benchmark seam: external task allocation ────────────────────────────

    def set_assignment_provider(self, provider: AssignmentProvider | None) -> None:
        """Install (or clear) an external task-assignment provider.

        When installed, idle robots are assigned by `provider` instead of the
        env's internal greedy nearest-pickup rule. Agent observations are
        unchanged, so a trained policy behaves identically whether or not a
        provider is installed. Used by the unified cross-harness benchmark to
        score classical allocators in the same simulator as MAPPO.
        """
        self._assignment_provider = provider

    @property
    def assignment_provider(self) -> AssignmentProvider | None:
        """The installed assignment provider, if any."""
        return self._assignment_provider

    def target_vector(self, agent_id: str) -> NDArray:
        """Waypoint action (normalized to [-1, 1]) toward the robot's task target.

        Mirrors the expert action convention: aim at the delivery point once the
        pickup is done, otherwise at the pickup point. Returns zeros when the
        robot has no assigned task.
        """
        idx = self._agent_idx(agent_id)
        if idx is None:
            return np.zeros(2, dtype=np.float32)
        task = self._get_assigned_task(idx)
        if task is None:
            return np.zeros(2, dtype=np.float32)
        robot = self._robots[idx]
        if task.picked_up:
            dx, dy = task.delivery_x - robot.x, task.delivery_y - robot.y
        else:
            dx, dy = task.pickup_x - robot.x, task.pickup_y - robot.y
        return np.clip(np.array([dx, dy], dtype=np.float32) / ACTION_SCALE_M, -1.0, 1.0)

    def _assign_pending(self, idle_robots: list[_RobotState], unassigned: list[_TaskState]) -> None:
        """Assign pending tasks to idle robots (provider, else greedy nearest)."""
        if not unassigned or not idle_robots:
            return

        provider = self._assignment_provider
        if provider is not None:
            robot_views = [
                RobotView(id=r.id, x=r.x, y=r.y, battery_pct=r.battery, busy=False)
                for r in idle_robots
            ]
            task_views = [
                TaskView(
                    id=t.id,
                    pickup_x=t.pickup_x,
                    pickup_y=t.pickup_y,
                    delivery_x=t.delivery_x,
                    delivery_y=t.delivery_y,
                    priority=t.priority,
                )
                for t in unassigned
            ]
            assignments = list(provider(robot_views, task_views))
            by_robot = {r.id: r for r in idle_robots}
            by_task = {t.id: t for t in unassigned}
            for robot_id, task_id in assignments:
                robot = by_robot.get(robot_id)
                task = by_task.get(task_id)
                # Fail loudly: a benchmark that silently ignores bad
                # assignments would again measure something other than the
                # policy under test (the exp_004 nearest-fallback bug).
                if robot is None:
                    raise ValueError(f"assignment provider returned unknown robot {robot_id!r}")
                if task is None:
                    raise ValueError(f"assignment provider returned unknown task {task_id!r}")
                task.assigned_to = robot.id
            return

        # Greedy nearest assignment: each idle robot takes its closest
        # unassigned pickup. This keeps travel short and is deterministic.
        remaining = list(unassigned)
        for r in idle_robots:
            if not remaining:
                break
            nearest = min(
                remaining,
                key=lambda t: math.dist((r.x, r.y), (t.pickup_x, t.pickup_y)),
            )
            nearest.assigned_to = r.id
            remaining.remove(nearest)

    def _update_tasks(self) -> None:
        for r in self._robots:
            if r.failed:
                continue
            for t in self._tasks:
                if t.assigned_to == r.id and not t.completed:
                    if not t.picked_up:
                        dist = math.dist((r.x, r.y), (t.pickup_x, t.pickup_y))
                        if dist < 0.5:
                            t.picked_up = True
                            self._events[r.id].append("pickup")
                    else:
                        dist = math.dist((r.x, r.y), (t.delivery_x, t.delivery_y))
                        if dist < 0.5:
                            t.completed = True
                            self._events[r.id].append("delivery")
                    break

        unassigned = [t for t in self._tasks if not t.completed and not t.assigned_to]
        idle_robots = [
            r
            for r in self._robots
            if not r.failed
            and not any(t.assigned_to == r.id and not t.completed for t in self._tasks)
        ]
        self._assign_pending(idle_robots, unassigned)

        self._mission_complete = bool(self._tasks) and all(t.completed for t in self._tasks)

    def _check_collisions(self) -> None:
        current_pairs: set[tuple[str, str]] = set()
        for i, r1 in enumerate(self._robots):
            for r2 in self._robots[i + 1 :]:
                if r1.failed or r2.failed:
                    continue
                dist = math.dist((r1.x, r1.y), (r2.x, r2.y))
                if dist < 0.7:
                    pair: tuple[str, str] = (r1.id, r2.id) if r1.id <= r2.id else (r2.id, r1.id)
                    current_pairs.add(pair)
                    if pair not in self._active_collisions:
                        self._collision_count += 1
                        self._events[r1.id].append("collision")
                        self._events[r2.id].append("collision")
        self._active_collisions = current_pairs

    def _simulate_lidar(self, robot_idx: int) -> NDArray:
        """Ray-march the occupancy grid to produce a 36-bin 360° scan."""
        r = self._robots[robot_idx]
        scans = np.full(N_LIDAR_BINS, 10.0, dtype=np.float32)
        height, width = self._occupancy.shape
        for i in range(N_LIDAR_BINS):
            angle = r.theta + (2 * math.pi * i / N_LIDAR_BINS)
            ca, sa = math.cos(angle), math.sin(angle)
            dist_m = GRID_RES_M
            while dist_m <= 10.0:
                gx = r.x + dist_m * ca
                gy = r.y + dist_m * sa
                if gx < 0.0 or gx >= WORLD_WIDTH_M or gy < 0.0 or gy >= WORLD_HEIGHT_M:
                    scans[i] = float(dist_m)
                    break
                if self._occupancy[int(gy / GRID_RES_M), int(gx / GRID_RES_M)]:
                    scans[i] = float(dist_m)
                    break
                dist_m += GRID_RES_M
        return scans

    def _get_nearby_robots(self, robot_idx: int) -> list[tuple[float, float, float]]:
        r = self._robots[robot_idx]
        others = []
        for i, other in enumerate(self._robots):
            if i == robot_idx or other.failed:
                continue
            dist = math.dist((r.x, r.y), (other.x, other.y))
            others.append((other.x, other.y, other.battery, dist))
        others.sort(key=lambda x: x[3])
        return [(x, y, b) for x, y, b, _ in others]

    def _get_nearest_pending_tasks(self, robot_idx: int) -> list[tuple[float, float]]:
        r = self._robots[robot_idx]
        pending = [
            (t.pickup_x, t.pickup_y, math.dist((r.x, r.y), (t.pickup_x, t.pickup_y)))
            for t in self._tasks
            if not t.completed and not t.assigned_to
        ]
        pending.sort(key=lambda x: x[2])
        return [(x, y) for x, y, _ in pending]

    def _fleet_utilization(self) -> float:
        active = sum(1 for r in self._robots if not r.failed)
        return active / max(1, len(self._robots))

    def _compute_reward(self, robot_idx: int) -> float:
        r = self._robots[robot_idx]
        if r.failed:
            return 0.0

        reward = self._shaping.get(r.id, 0.0)
        for event in self._events.get(r.id, []):
            if event == "pickup":
                reward += REWARD_PICKUP
            elif event == "delivery":
                reward += REWARD_DELIVERY
            elif event == "collision":
                reward += REWARD_COLLISION

        if self._mission_complete:
            time_efficiency = max(0.0, 1.0 - self._episode_steps / self._max_steps)
            reward += REWARD_MISSION_COMPLETE * time_efficiency
        # Terminal bonus proportional to tasks completed (dense-ish signal).
        if self._episode_steps == self._max_steps or self._mission_complete:
            reward += 2.0 * sum(1 for t in self._tasks if t.completed)

        reward -= 0.001 * (1.0 - r.battery)
        # Per-step time cost. A flat *positive* per-step term (previously +0.01)
        # pays for inaction: over a 600 s / 6000-step episode it totals ~+60 per
        # agent (~+300 for the fleet), which is more than the ~300 fleet reward
        # for completing all 20 tasks — so "stand still" was the greedy
        # optimum and the policy never learned to pick anything up. The cost is
        # now negative, so idling is never profitable.
        reward -= STEP_COST
        return reward


def _wrap_pi(angle: float) -> float:
    """Wrap an angle to [-pi, pi]."""
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def _path_length(points: deque[tuple[float, float]]) -> float:
    """Total travelled distance across a window of positions."""
    total = 0.0
    pts = list(points)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        total += math.hypot(x1 - x0, y1 - y0)
    return total


def _rect_contains_point(
    rect: tuple[float, float, float, float], x: float, y: float, margin: float = 0.0
) -> bool:
    x0, y0, x1, y1 = rect
    return x0 - margin <= x <= x1 + margin and y0 - margin <= y <= y1 + margin


def _rects_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    margin: float = 0.0,
) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return (
        ax0 - margin <= bx1 and bx0 <= ax1 + margin and ay0 - margin <= by1 and by0 <= ay1 + margin
    )


@dataclass
class _RobotState:
    id: str
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    battery: float = 1.0
    failed: bool = False


@dataclass
class _TaskState:
    id: str
    pickup_x: float = 0.0
    pickup_y: float = 0.0
    delivery_x: float = 0.0
    delivery_y: float = 0.0
    priority: int = 2
    assigned_to: str | None = None
    picked_up: bool = False
    completed: bool = False
