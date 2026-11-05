"""Random policy — baseline for sanity checks.

Returns random actions within the action space bounds.
Used to verify the training loop works before MAPPO convergence.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

NDArray = npt.NDArray[np.float32]


class RandomPolicy:
    """Random action policy for sanity checking."""

    def __init__(self, action_dim: int = 2, seed: int | None = None) -> None:
        self.action_dim = action_dim
        self._rng = np.random.default_rng(seed)

    def act(self, _obs: NDArray) -> NDArray:
        return self._rng.uniform(low=-0.5, high=1.0, size=self.action_dim).astype(np.float32)
