"""Tests for RandomPolicy and training callbacks."""

import numpy as np

from ml.policies.random import RandomPolicy
from ml.training.callbacks import MLflowTrainingCallback


class TestRandomPolicy:
    def test_act_shape(self) -> None:
        policy = RandomPolicy(action_dim=2)
        obs = np.zeros(10, dtype=np.float32)
        action = policy.act(obs)
        assert action.shape == (2,)

    def test_act_in_bounds(self) -> None:
        policy = RandomPolicy(action_dim=2, seed=42)
        for _ in range(100):
            action = policy.act(np.zeros(5, dtype=np.float32))
            assert action[0] >= -0.5 and action[0] <= 1.0
            assert action[1] >= -0.5 and action[1] <= 1.0

    def test_deterministic_seed(self) -> None:
        p1 = RandomPolicy(action_dim=3, seed=10)
        p2 = RandomPolicy(action_dim=3, seed=10)
        obs = np.ones(5, dtype=np.float32)
        np.testing.assert_array_equal(p1.act(obs), p2.act(obs))


class TestMLflowCallback:
    def test_init_without_mlflow(self) -> None:
        cb = MLflowTrainingCallback(experiment_name="test", run_name="test_run")
        assert cb._mlflow is None

    def test_context_manager(self) -> None:
        with MLflowTrainingCallback("test", "run") as cb:
            cb.log_params({"lr": 0.001})
            cb.on_step_end(100, {"loss": 0.5})
        # Should not raise

    def test_git_commit(self) -> None:
        cb = MLflowTrainingCallback("test", "run")
        commit = cb.get_git_commit()
        assert isinstance(commit, str)
        assert len(commit) > 0
