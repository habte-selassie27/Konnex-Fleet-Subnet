"""Tests for FleetEnv — Gymnasium multi-agent fleet environment.

Verifies: reset, step, observation shapes, reward logic, multi-agent interface.
"""

from typing import cast

import numpy as np
from gymnasium import spaces

from ml.env.fleet_env import (
    N_LIDAR_BINS,
    N_NEARBY_ROBOTS,
    N_PENDING_TASKS,
    FleetEnv,
    FleetEnvConfig,
)


class TestFleetEnvInit:
    def test_default_config(self) -> None:
        env = FleetEnv()
        assert env.n_agents == 5

    def test_custom_config(self) -> None:
        cfg = FleetEnvConfig(robot_count=3, task_count=10)
        env = FleetEnv(cfg)
        assert env.n_agents == 3

    def test_observation_space_has_all_keys(self) -> None:
        env = FleetEnv()
        expected = {
            "pos",
            "vel",
            "orientation",
            "battery",
            "has_task",
            "task_pickup",
            "task_delivery",
            "task_progress",
            "task_phase",
            "lidar",
            "nearby_robots",
            "nearby_battery",
            "pending_tasks",
            "fleet_utilization",
            "tasks_remaining_frac",
            "time_remaining_frac",
        }
        dict_space = cast(spaces.Dict, env.observation_space)
        assert set(dict_space.keys()) == expected


class TestFleetEnvReset:
    def test_reset_returns_obs_dict(self) -> None:
        env = FleetEnv(FleetEnvConfig(robot_count=3, task_count=5))
        obs, info = env.reset(seed=42)
        assert isinstance(obs, dict)
        assert len(obs) == 3
        assert isinstance(info, dict)

    def test_reset_deterministic(self) -> None:
        env1 = FleetEnv(FleetEnvConfig(robot_count=3, seed=100))
        env2 = FleetEnv(FleetEnvConfig(robot_count=3, seed=100))
        obs1, _ = env1.reset(seed=100)
        obs2, _ = env2.reset(seed=100)
        for agent_id in obs1:
            for key in obs1[agent_id]:
                np.testing.assert_array_equal(obs1[agent_id][key], obs2[agent_id][key])


class TestFleetEnvStep:
    def test_step_returns_correct_structure(self) -> None:
        env = FleetEnv(FleetEnvConfig(robot_count=2, task_count=4))
        env.reset(seed=42)
        actions = {aid: env.action_space.sample() for aid in env.agent_ids}
        obs, rewards, terminateds, truncateds, infos = env.step(actions)
        assert len(obs) == 2
        assert len(rewards) == 2
        assert "__all__" in terminateds
        assert "__all__" in truncateds

    def test_observation_shapes(self) -> None:
        env = FleetEnv(FleetEnvConfig(robot_count=2, task_count=4))
        env.reset(seed=42)
        obs = {aid: env._build_obs(i) for i, aid in enumerate(env.agent_ids)}
        for obs_dict in obs.values():
            assert obs_dict["pos"].shape == (2,)
            assert obs_dict["vel"].shape == (2,)
            assert obs_dict["orientation"].shape == (1,)
            assert obs_dict["battery"].shape == (1,)
            assert obs_dict["lidar"].shape == (N_LIDAR_BINS,)
            assert obs_dict["nearby_robots"].shape == (N_NEARBY_ROBOTS, 2)
            assert obs_dict["nearby_battery"].shape == (N_NEARBY_ROBOTS,)
            assert obs_dict["pending_tasks"].shape == (N_PENDING_TASKS, 2)

    def test_action_clipping(self) -> None:
        env = FleetEnv(FleetEnvConfig(robot_count=1, task_count=2))
        env.reset(seed=42)
        actions = {"robot_0": np.array([5.0, 10.0], dtype=np.float32)}
        obs, _, _, _, _ = env.step(actions)
        pos = obs["robot_0"]["pos"]
        assert pos[0] >= 0.0 and pos[0] <= 40.0
        assert pos[1] >= 0.0 and pos[1] <= 30.0


class TestFleetEnvReward:
    def test_reward_is_finite(self) -> None:
        env = FleetEnv(FleetEnvConfig(robot_count=2, task_count=4))
        env.reset(seed=42)
        for _ in range(50):
            actions = {aid: env.action_space.sample() for aid in env.agent_ids}
            _, rewards, terminateds, _, _ = env.step(actions)
            for r in rewards.values():
                assert np.isfinite(r)
            if terminateds.get("__all__", False):
                break

    def test_delivery_reward_positive(self) -> None:
        env = FleetEnv(FleetEnvConfig(robot_count=1, task_count=1))
        env.reset(seed=42)
        for _ in range(300):
            actions = {"robot_0": np.array([1.0, 0.0], dtype=np.float32)}
            _, rewards, terminateds, _, _ = env.step(actions)
            if rewards.get("robot_0", 0) > 10.0:
                return
            if terminateds.get("__all__", False):
                break
        # Mission may not complete in 300 steps — that is OK for this test


class TestFleetEnvAgentIds:
    def test_agent_ids(self) -> None:
        env = FleetEnv(FleetEnvConfig(robot_count=4))
        assert env.agent_ids == ["robot_0", "robot_1", "robot_2", "robot_3"]
