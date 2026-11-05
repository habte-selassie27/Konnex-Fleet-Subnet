"""Observation encoding shared by training, evaluation, and loading.

The order is stable (sorted agent ids, sorted observation keys) so a
checkpoint trained in one process can be evaluated in another.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

NDArray = npt.NDArray[np.float32]


def flatten_obs(obs_dict: dict[str, Any]) -> NDArray:
    """Flatten one agent's Dict observation in a deterministic key order."""
    parts: list[NDArray] = []
    for key in sorted(obs_dict.keys()):
        parts.append(np.asarray(obs_dict[key], dtype=np.float32).flatten())
    return np.concatenate(parts).astype(np.float32)


def global_state(observations: dict[str, dict[str, Any]]) -> NDArray:
    """Concatenate every agent's local observation in sorted agent-id order."""
    parts = [flatten_obs(observations[agent_id]) for agent_id in sorted(observations)]
    return np.concatenate(parts).astype(np.float32)


def observation_dim(observation_space: Any) -> int:
    """Sum the flattened sizes of a Gymnasium Dict observation space."""
    total = 0
    for value in observation_space.sample().values():
        if hasattr(value, "size"):
            total += int(value.size)
        else:
            total += 1
    return total


def state_dim(observation_space: Any, n_agents: int) -> int:
    return observation_dim(observation_space) * n_agents
