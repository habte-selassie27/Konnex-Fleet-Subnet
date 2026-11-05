"""Integrity guards for the MAPPO / benchmark boundary.

These tests exist because exp_004/exp_005 were once silently produced by the
nearest-task allocator after MAPPO failed to load. Any regression should fail
here before it can reach experiments/results/.
"""

from __future__ import annotations

import numpy as np
import pytest

from fleet.task_allocator.mappo import (
    MAPPOIsNotATaskAllocatorError,
    MAPPOTaskAllocator,
)
from ml.env.encoding import flatten_obs, global_state, observation_dim, state_dim
from ml.env.fleet_env import FleetEnv, FleetEnvConfig


def test_mappo_allocator_refuses_to_impersonate_an_allocator() -> None:
    with pytest.raises(MAPPOIsNotATaskAllocatorError):
        MAPPOTaskAllocator()


def test_mappo_not_registered_in_benchmark_policy_map() -> None:
    from experiments.scripts.run_experiment import POLICY_MAP

    assert "mappo" not in POLICY_MAP
    assert set(POLICY_MAP) == {"nearest", "hungarian", "cost_optimizer"}


def test_observation_encoding_matches_fleet_env_dimensions() -> None:
    env = FleetEnv(FleetEnvConfig(robot_count=5, task_count=20))
    obs, _ = env.reset(seed=1000)
    flat = flatten_obs(obs["robot_0"])
    state = global_state(obs)
    assert flat.shape == (observation_dim(env.observation_space),)
    assert state.shape == (state_dim(env.observation_space, env.n_agents),)
    assert flat.shape[0] == 70
    assert state.shape[0] == 350


def test_battery_survives_a_600_step_mission() -> None:
    """The old drain rate killed every robot after ~100 steps."""
    env = FleetEnv(FleetEnvConfig(robot_count=1, task_count=1))
    env.reset(seed=42)
    for _ in range(600):
        actions = {"robot_0": np.array([1.0, 0.0], dtype=np.float32)}
        _, _, terminateds, truncateds, _ = env.step(actions)
        if terminateds.get("__all__") or truncateds.get("__all__"):
            break
    assert not env.mission_complete
    info = env.step({"robot_0": np.array([0.0, 0.0], dtype=np.float32)})[4]["__all__"]
    assert info["energy_consumed"] > 0.0
    assert info["energy_consumed"] < 100.0
