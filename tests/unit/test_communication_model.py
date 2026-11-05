"""Communication degradation model unit tests (Phase 5).

Contract: latency within [base, base + jitter] when delivered; packet loss
drops messages at the configured rate; statistics track sent/delivered/lost
and mean latency.

Status: COMPLETE (Phase 5).
"""

import random

import pytest

from fleet.communication.model import CommConfig, CommunicationModel


class TestCommunicationModel:
    def test_clean_channel_delivers_everything(self) -> None:
        model = CommunicationModel(CommConfig(packet_loss_rate=0.0))
        rng = random.Random(1)
        latencies = [model.transmit(rng) for _ in range(200)]
        assert all(latency is not None for latency in latencies)
        assert model.stats.messages_delivered == 200
        assert model.stats.packets_lost == 0
        assert model.stats.delivery_rate == 1.0

    def test_latency_within_bounds(self) -> None:
        model = CommunicationModel(CommConfig(base_latency_ms=50.0, jitter_ms=20.0))
        rng = random.Random(2)
        for _ in range(100):
            latency = model.transmit(rng)
            assert latency is not None
            assert 50.0 <= latency <= 70.0

    def test_total_loss_drops_every_packet(self) -> None:
        model = CommunicationModel(CommConfig(packet_loss_rate=1.0))
        assert model.transmit(random.Random(3)) is None
        assert model.stats.packets_lost == 1
        assert model.stats.delivery_rate == 0.0

    def test_partial_loss_matches_rate(self) -> None:
        model = CommunicationModel(CommConfig(packet_loss_rate=0.5))
        rng = random.Random(7)
        results = [model.transmit(rng) for _ in range(200)]
        lost = sum(1 for result in results if result is None)
        assert 60 < lost < 140  # approximately half, with headroom
        assert model.stats.packets_lost == lost
        assert model.stats.delivery_rate == pytest.approx(1.0 - lost / 200)

    def test_mean_latency_tracks_delivered_messages(self) -> None:
        model = CommunicationModel(CommConfig(packet_loss_rate=0.25))
        rng = random.Random(11)
        latencies = [lat for lat in (model.transmit(rng) for _ in range(100)) if lat is not None]
        assert latencies
        assert model.stats.mean_latency_ms == sum(latencies) / len(latencies)

    def test_reset_stats(self) -> None:
        model = CommunicationModel(CommConfig(packet_loss_rate=0.5))
        model.transmit(random.Random(5))
        model.reset_stats()
        assert model.stats.messages_sent == 0
        assert model.stats.messages_delivered == 0
        assert model.stats.packets_lost == 0
        assert model.stats.delivery_rate == 1.0  # no traffic yet
