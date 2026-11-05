"""Shared MLP backbone for actor/critic networks.

Spec (AGENTS.md §8.1): Linear(in, hidden) -> LayerNorm -> Tanh, repeated.
Orthogonal initialization with gain=sqrt(2), zero bias.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn


class MLPNetwork(nn.Module):
    """Shared MLP backbone used by both actor and critic."""

    def __init__(
        self,
        input_dim: int,
        hidden_sizes: list[int],
        output_dim: int,
        use_layer_norm: bool = True,
    ) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        in_size = input_dim
        for hidden_size in hidden_sizes:
            layers.append(nn.Linear(in_size, hidden_size))
            if use_layer_norm:
                layers.append(nn.LayerNorm(hidden_size))
            layers.append(nn.Tanh())
            in_size = hidden_size
        layers.append(nn.Linear(in_size, output_dim))
        self.net = nn.Sequential(*layers)

        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, gain=np.sqrt(2))
                nn.init.constant_(module.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        result: torch.Tensor = self.net(x)
        return result
