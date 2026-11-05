"""Tests for MAPPO agent, critic, and trainer.

Verifies: forward pass, action sampling, save/load, GAE computation, PPO update.
"""

from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="PyTorch not installed")

from ml.policies.mappo.agent import (
    CheckpointMismatchError,
    MAPPOActor,
    MAPPOAgent,
    MAPPOCritic,
)
from ml.policies.mappo.network import MLPNetwork
from ml.policies.mappo.trainer import MAPPOTrainer, RolloutBuffer, TrainingConfig


class TestMLPNetwork:
    def test_output_shape(self) -> None:
        net = MLPNetwork(input_dim=10, hidden_sizes=[64, 32], output_dim=5)
        x = torch.randn(4, 10)
        out = net(x)
        assert out.shape == (4, 5)

    def test_deterministic(self) -> None:
        net = MLPNetwork(input_dim=5, hidden_sizes=[32], output_dim=3)
        x = torch.randn(2, 5)
        out1 = net(x)
        out2 = net(x)
        torch.testing.assert_close(out1, out2)


class TestMAPPOActor:
    def test_get_action_shape(self) -> None:
        actor = MAPPOActor(obs_dim=20, action_dim=2)
        obs = torch.randn(1, 20)
        action, log_prob = actor.get_action(obs)
        assert action.shape == (1, 2)
        assert log_prob.shape == (1,)

    def test_log_std_range(self) -> None:
        actor = MAPPOActor(obs_dim=10, action_dim=2)
        assert actor.log_std.shape == (2,)


class TestMAPPOCritic:
    def test_value_shape(self) -> None:
        critic = MAPPOCritic(state_dim=50)
        state = torch.randn(1, 50)
        value = critic(state)
        assert value.shape == (1,)

    def test_batch_value(self) -> None:
        critic = MAPPOCritic(state_dim=30)
        state = torch.randn(8, 30)
        value = critic(state)
        assert value.shape == (8,)


class TestMAPPOAgent:
    def test_act_returns_action(self) -> None:
        agent = MAPPOAgent(obs_dim=20, state_dim=100, action_dim=2)
        obs = np.random.randn(20).astype(np.float32)
        action = agent.act(obs)
        assert action.shape == (2,)

    def test_save_load(self, tmp_path: Path) -> None:
        agent = MAPPOAgent(obs_dim=10, state_dim=50, action_dim=2)
        path = str(tmp_path / "agent.pt")
        agent.save(path)
        agent2 = MAPPOAgent(obs_dim=10, state_dim=50, action_dim=2)
        agent2.load(path)
        obs = np.random.randn(10).astype(np.float32)
        np.testing.assert_array_equal(
            agent.act(obs, deterministic=True),
            agent2.act(obs, deterministic=True),
        )

    def test_from_checkpoint_reads_dims(self, tmp_path: Path) -> None:
        agent = MAPPOAgent(obs_dim=69, state_dim=345, action_dim=2)
        path = str(tmp_path / "agent.pt")
        agent.save(path)
        loaded = MAPPOAgent.from_checkpoint(path)
        assert loaded.obs_dim == 69
        assert loaded.state_dim == 345
        assert loaded.action_dim == 2

    def test_mismatched_checkpoint_fails_loudly(self, tmp_path: Path) -> None:
        agent = MAPPOAgent(obs_dim=69, state_dim=345, action_dim=2)
        path = str(tmp_path / "agent.pt")
        agent.save(path)
        wrong = MAPPOAgent(obs_dim=256, state_dim=1280, action_dim=2)
        with pytest.raises(CheckpointMismatchError):
            wrong.load(path)

    def test_act_with_logprob_shapes(self) -> None:
        agent = MAPPOAgent(obs_dim=10, state_dim=50, action_dim=2)
        action, raw, log_prob = agent.act_with_logprob(np.random.randn(10).astype(np.float32))
        assert action.shape == (2,)
        assert raw.shape == (2,)
        assert np.isfinite(log_prob)


class TestMAPPOTrainer:
    def test_gae_computation(self) -> None:
        trainer = MAPPOTrainer(
            agent=MAPPOAgent(obs_dim=5, state_dim=10, action_dim=2),
            n_agents=1,
        )
        rewards = np.array([1.0, 0.5, 2.0], dtype=np.float32)
        values = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        dones = np.array([0, 0, 0], dtype=np.float32)
        next_value = np.array([0.4], dtype=np.float32)
        advantages, returns = trainer.compute_gae(rewards, values, dones, next_value)
        assert advantages.shape == rewards.shape
        assert returns.shape == rewards.shape

    def test_ppo_update_uses_global_states(self) -> None:
        obs_dim, state_dim, action_dim = 10, 40, 2
        agent = MAPPOAgent(obs_dim=obs_dim, state_dim=state_dim, action_dim=action_dim)
        trainer = MAPPOTrainer(agent=agent, n_agents=4, config=TrainingConfig(n_epochs=1))
        buffer = RolloutBuffer(
            observations=np.random.randn(32, obs_dim).astype(np.float32),
            states=np.random.randn(32, state_dim).astype(np.float32),
            actions=np.random.randn(32, action_dim).astype(np.float32),
            rewards=np.random.randn(32).astype(np.float32),
            dones=np.zeros(32, dtype=np.float32),
            values=np.random.randn(32).astype(np.float32),
            log_probs=np.random.randn(32).astype(np.float32),
            advantages=np.random.randn(32).astype(np.float32),
            returns=np.random.randn(32).astype(np.float32),
        )
        metrics = trainer.ppo_update(buffer)
        assert "policy_loss" in metrics
        assert "value_loss" in metrics
        assert "entropy" in metrics
        assert np.isfinite(metrics["value_loss"])
