"""Communication model — latency + packet loss simulation.

Status: COMPLETE (Phase 5).
"""

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class CommConfig:
    """Communication channel parameters."""

    base_latency_ms: float = 50.0
    jitter_ms: float = 20.0
    packet_loss_rate: float = 0.0  # 0.0 = no loss, 1.0 = total loss


@dataclass
class CommStats:
    """Aggregate channel statistics."""

    messages_sent: int = 0
    messages_delivered: int = 0
    packets_lost: int = 0
    total_latency_ms: float = 0.0

    @property
    def delivery_rate(self) -> float:
        """Fraction of sent messages that were delivered."""
        if self.messages_sent == 0:
            return 1.0
        return self.messages_delivered / self.messages_sent

    @property
    def mean_latency_ms(self) -> float:
        """Mean latency of delivered messages."""
        if self.messages_delivered == 0:
            return 0.0
        return self.total_latency_ms / self.messages_delivered


class CommunicationModel:
    """Simulates a lossy, latent command channel."""

    def __init__(self, config: CommConfig | None = None) -> None:
        self._config = config or CommConfig()
        self._stats = CommStats()

    @property
    def config(self) -> CommConfig:
        """Channel configuration."""
        return self._config

    @property
    def stats(self) -> CommStats:
        """Channel statistics."""
        return self._stats

    def transmit(self, rng: random.Random) -> float | None:
        """Transmit one message.

        Returns the latency in ms when delivered, or None when the packet is
        dropped by the loss model.
        """
        self._stats.messages_sent += 1
        if rng.random() < self._config.packet_loss_rate:
            self._stats.packets_lost += 1
            return None
        latency = self._config.base_latency_ms + rng.uniform(0.0, self._config.jitter_ms)
        self._stats.messages_delivered += 1
        self._stats.total_latency_ms += latency
        return latency

    def reset_stats(self) -> None:
        """Reset channel statistics."""
        self._stats = CommStats()
