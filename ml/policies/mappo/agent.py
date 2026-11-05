"""MAPPO agent — Multi-Agent Proximal Policy Optimization.

Spec (AGENTS.md §8.1):
    Actor (decentralized): local_obs -> MLP(256,256) -> action_mean, log_std
    Critic (centralized): global_state -> MLP(256,256) -> value
    Both use layer normalization and orthogonal initialization.

Checkpoints carry their observation/state dimensions so a loader can fail
loudly instead of silently using mismatched weights (the previous
``MAPPOTaskAllocator`` hard-coded 256 and fell back to nearest-task without
logging — see ``docs/ml.md``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import torch
import torch.nn as nn

from ml.policies.mappo.network import MLPNetwork

NDArray = npt.NDArray[np.float32]


class CheckpointMismatchError(RuntimeError):
    """Raised when a checkpoint does not match the requested network shape."""


class MAPPOActor(nn.Module):
    """Decentralized actor: maps local observation to action distribution."""

    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        hidden_sizes: list[int] | None = None,
    ) -> None:
        super().__init__()
        hidden_sizes = hidden_sizes or [256, 256]
        self.backbone = MLPNetwork(obs_dim, hidden_sizes, hidden_sizes[-1])
        self.action_mean = nn.Linear(hidden_sizes[-1], action_dim)
        self.log_std = nn.Parameter(torch.zeros(action_dim))

        nn.init.orthogonal_(self.action_mean.weight, gain=0.01)
        nn.init.constant_(self.action_mean.bias, 0)

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.backbone(obs)
        mean = self.action_mean(features)
        std = torch.exp(self.log_std.clamp(-4, 15))
        return mean, std

    def get_action(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Sample a squashed action and return it with its pre-tanh log-prob.

        The log-prob is computed on the pre-tanh Gaussian sample. PPO must
        update using the same pre-tanh action (``MAPPOAgent.act_with_logprob``
        returns it), otherwise the policy ratio is inconsistent.
        """
        mean, std = self.forward(obs)
        dist = torch.distributions.Normal(mean, std)
        raw_action = dist.sample()  # type: ignore[no-untyped-call]
        log_prob = dist.log_prob(raw_action).sum(-1)  # type: ignore[no-untyped-call]
        return raw_action.tanh(), log_prob


class MAPPOCritic(nn.Module):
    """Centralized critic: maps global state to value estimate.

    Only used during training — NOT deployed on robots.
    """

    def __init__(
        self,
        state_dim: int,
        hidden_sizes: list[int] | None = None,
    ) -> None:
        super().__init__()
        hidden_sizes = hidden_sizes or [256, 256]
        self.net = MLPNetwork(state_dim, hidden_sizes, 1)
        nn.init.orthogonal_(self.net.net[-1].weight, gain=1.0)  # type: ignore[arg-type]

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        result: torch.Tensor = self.net(state).squeeze(-1)
        return result


class MAPPOAgent:
    """Container for MAPPO actor + critic with training utilities."""

    def __init__(
        self,
        obs_dim: int,
        state_dim: int,
        action_dim: int,
        lr: float = 3e-4,
        device: str = "cpu",
    ) -> None:
        self.obs_dim = obs_dim
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = torch.device(device)
        self.actor = MAPPOActor(obs_dim, action_dim).to(self.device)
        self.critic = MAPPOCritic(state_dim).to(self.device)

        self.actor_optimizer = torch.optim.Adam(self.actor.parameters(), lr=lr, eps=1e-5)
        self.critic_optimizer = torch.optim.Adam(self.critic.parameters(), lr=lr, eps=1e-5)

    @torch.no_grad()
    def act(self, obs: NDArray, deterministic: bool = False) -> NDArray:
        """Inference-time action. Uses local obs only. No critic.

        Args:
            obs: Observation array, shape (obs_dim,) or (batch, obs_dim).
            deterministic: If True, return mean action (no sampling).

        Returns:
            Squashed action(s) in [-1, 1], shape (action_dim,) or
            (batch, action_dim).
        """
        action, _, _ = self.act_with_logprob(obs, deterministic=deterministic)
        return action

    @torch.no_grad()
    def act_with_logprob(
        self,
        obs: NDArray,
        deterministic: bool = False,
    ) -> tuple[NDArray, NDArray, NDArray]:
        """Return ``(squashed_action, raw_action, log_prob)`` for PPO rollouts.

        ``raw_action`` is the pre-tanh Gaussian sample. Store it in the
        rollout buffer and pass it back to :meth:`evaluate_actions`.
        """
        obs_t = self._as_batch(obs)
        mean, std = self.actor(obs_t)
        dist = torch.distributions.Normal(mean, std)
        raw = mean if deterministic else dist.sample()  # type: ignore[no-untyped-call]
        log_prob = dist.log_prob(raw).sum(-1)  # type: ignore[no-untyped-call]
        action = raw.tanh()

        squeeze = np.ndim(obs) == 1
        action_np = action.cpu().numpy().astype(np.float32)
        raw_np = raw.cpu().numpy().astype(np.float32)
        log_prob_np = log_prob.cpu().numpy().astype(np.float32)
        if squeeze:
            return action_np[0], raw_np[0], log_prob_np[0]
        return action_np, raw_np, log_prob_np

    @torch.no_grad()
    def value(self, state: NDArray) -> float:
        """Centralized value estimate(s) for a global state."""
        state_t = self._as_batch(state)
        value = np.asarray(self.critic(state_t).cpu().numpy(), dtype=np.float32)
        return float(value.reshape(-1)[0])

    def evaluate_actions(
        self,
        obs: NDArray,
        raw_actions: NDArray,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return ``(log_prob, entropy)`` for PPO updates."""
        obs_t = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
        actions_t = torch.as_tensor(raw_actions, dtype=torch.float32, device=self.device)
        mean, std = self.actor(obs_t)
        dist = torch.distributions.Normal(mean, std)
        log_prob = dist.log_prob(actions_t).sum(-1)  # type: ignore[no-untyped-call]
        entropy = dist.entropy().sum(-1)  # type: ignore[no-untyped-call]
        return log_prob, entropy

    def _as_batch(self, obs: NDArray) -> torch.Tensor:
        arr = np.asarray(obs, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr[None, :]
        return torch.as_tensor(arr, dtype=torch.float32, device=self.device)

    def save(self, path: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "obs_dim": self.obs_dim,
                "state_dim": self.state_dim,
                "action_dim": self.action_dim,
                "actor_state_dict": self.actor.state_dict(),
                "critic_state_dict": self.critic.state_dict(),
                "actor_optimizer": self.actor_optimizer.state_dict(),
                "critic_optimizer": self.critic_optimizer.state_dict(),
            },
            target,
        )

    def load(self, path: str) -> None:
        # weights_only=True prevents arbitrary code execution via pickle payloads.
        checkpoint: dict[str, Any] = torch.load(path, map_location=self.device, weights_only=True)
        self._check_dims(checkpoint, path)

        self.actor.load_state_dict(checkpoint["actor_state_dict"])
        self.critic.load_state_dict(checkpoint["critic_state_dict"])
        self.actor_optimizer.load_state_dict(checkpoint["actor_optimizer"])
        self.critic_optimizer.load_state_dict(checkpoint["critic_optimizer"])

    @classmethod
    def from_checkpoint(
        cls,
        path: str,
        device: str = "cpu",
    ) -> MAPPOAgent:
        """Load an agent using the dimensions stored in its checkpoint."""
        checkpoint: dict[str, Any] = torch.load(path, map_location=device, weights_only=True)
        missing = {"obs_dim", "state_dim", "action_dim"} - set(checkpoint)
        if missing:
            raise CheckpointMismatchError(
                f"Checkpoint {path} is missing dimensions {sorted(missing)}. "
                "Legacy checkpoints from the random-rollout runs cannot be "
                "safely loaded; retrain with ml/training/train.py."
            )
        agent = cls(
            obs_dim=int(checkpoint["obs_dim"]),
            state_dim=int(checkpoint["state_dim"]),
            action_dim=int(checkpoint["action_dim"]),
            device=device,
        )
        agent.load(path)
        return agent

    def _check_dims(self, checkpoint: dict[str, Any], path: str) -> None:
        for key, expected in (
            ("obs_dim", self.obs_dim),
            ("state_dim", self.state_dim),
            ("action_dim", self.action_dim),
        ):
            actual = checkpoint.get(key)
            if actual is not None and int(actual) != expected:
                raise CheckpointMismatchError(
                    f"Checkpoint {path} has {key}={actual}, "
                    f"but the agent expects {key}={expected}. Refusing to load "
                    "mismatched weights (this is what caused the silent "
                    "nearest-task fallback in exp_004)."
                )


def checkpoint_dims(path: str | Path) -> dict[str, int]:
    """Read shape metadata from a checkpoint without constructing an agent."""
    checkpoint: dict[str, Any] = torch.load(str(path), map_location="cpu", weights_only=True)
    return {
        key: int(cast(int, checkpoint[key]))
        for key in ("obs_dim", "state_dim", "action_dim")
        if key in checkpoint
    }
