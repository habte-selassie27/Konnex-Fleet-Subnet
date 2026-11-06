"""Fleet mission synapse — Konnex/bittensor subnet protocol (Launch tier).

Defines the synapse that miners and validators exchange on a Konnex fleet
subnet. Mirrors the pattern in konnex-world/knx-subnet-drone-navigation
(template/protocol.py::DroneNavSynapse) but for warehouse fleet missions.

STATUS: DEFINITION ONLY. Requires `bittensor` (konnex-chain-sdk) to be
installed; importing this module without bittensor yields a stub class so
the rest of the codebase (and tests) keep working.

Boundary contract (AGENTS.md §6.8): only protocol-safe types cross this
boundary. Zero imports from robotics/, simulation/, ml/, fleet/.
"""

from __future__ import annotations

try:  # bittensor is an optional, Launch-tier dependency
    import bittensor as bt

    _BT_AVAILABLE = True
except ImportError:  # pragma: no cover - environment-dependent
    bt = None
    _BT_AVAILABLE = False

# bittensor v11 removed the Synapse/axon/dendrite networking stack.
_BT_SYNAPSE = getattr(bt, "Synapse", None) if _BT_AVAILABLE else None

if _BT_AVAILABLE and _BT_SYNAPSE is not None:

    class FleetMissionSynapse(_BT_SYNAPSE):  # type: ignore[misc]
        """Subnet protocol for fleet-mission mining and validation.

        Validator -> miner:
          - mission_id: deterministic per-round id
          - scenario_seed: seed for the standardized warehouse scenario
          - robot_count, task_count: mission size
          - policy_hint: optional policy descriptor the miner should improve

        Miner -> validator:
          - policy_hash: SHA-256 of the submitted policy weights
          - trajectory_uri: URI of the recorded trajectory bundle (Parquet/S3)
          - claimed_score: miner's self-reported PoPW score (validator re-scores)
          - miner_error: non-empty when the miner failed
        """

        version: str = "fleet-mission-v1"
        mission_id: str
        scenario_seed: int
        robot_count: int = 5
        task_count: int = 20
        policy_hint: str = ""

        policy_hash: str = ""
        trajectory_uri: str = ""
        claimed_score: float = 0.0
        miner_error: str = ""

        def deserialize(self) -> dict[str, object]:
            return {
                "policy_hash": self.policy_hash,
                "trajectory_uri": self.trajectory_uri,
                "claimed_score": self.claimed_score,
                "error": self.miner_error,
            }

else:  # pragma: no cover - environment-dependent

    class FleetMissionSynapse:  # type: ignore[no-redef]
        """Stub when bittensor is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:  # noqa: ARG002
            raise RuntimeError(
                "FleetMissionSynapse requires bittensor (konnex-chain-sdk). "
                "Install it for Launch-tier on-chain integration."
            )


def bittensor_available() -> bool:
    """Whether bittensor with the Synapse stack is usable in this environment."""
    return _BT_AVAILABLE and _BT_SYNAPSE is not None
