"""BittensorKonnexProvider — on-chain integration via the Konnex (bittensor) chain.

STATUS: LAUNCH TIER — skeleton only. Live chain operations require:
    - konnex-chain-sdk (bittensor fork) installed
    - a funded wallet (faucet: https://subnets.testnet.konnex.world/faucet)
    - a registered hotkey on a fleet subnet (netuid)
    - a running subtensor connection

The provider maps KonnexProvider methods to bittensor primitives:
    - submit_mission      -> query the metagraph for the current round; the
                            mission is broadcast to miners via a FleetMissionSynapse
    - submit_evaluation   -> validator scores a miner's response; weight setting
                            via subtensor.set_weights
    - publish_proof       -> commit the PoPW artifact hash as an extrinsic
                            (or store it in the subnet's commit-reveal)
    - query_rewards       -> read the metagraph incentive for a hotkey
    - get_submission_status -> query a block/extrinsic by hash

Boundary contract (AGENTS.md §6.8): only protocol-safe types cross this
boundary. Zero imports from robotics/, simulation/, ml/, fleet/.
"""

from __future__ import annotations

from typing import Any

import structlog

from protocol.konnex.models import MissionMetadata, SubmissionReceipt
from protocol.konnex.synapse import bittensor_available
from validator.reproducibility.artifact import EvaluationArtifact

logger = structlog.get_logger(__name__)


class BittensorKonnexProvider:
    """On-chain Konnex provider (Launch tier, skeleton).

    Live operations raise NotImplementedError with setup instructions until
    a funded wallet + registered hotkey + subnet netuid are configured.
    """

    def __init__(
        self,
        network: str = "testnet",
        wallet_name: str = "fleet",
        hotkey_name: str = "default",
        netuid: int | None = None,
    ) -> None:
        self._network = network
        self._wallet_name = wallet_name
        self._hotkey_name = hotkey_name
        self._netuid = netuid
        self._subtensor: Any = None
        self._wallet: Any = None
        self._metagraph: Any = None
        logger.warning(
            "bittensor_konnex_provider_initialized",
            network=network,
            netuid=netuid,
            bittensor_available=bittensor_available(),
            message="Live chain operations require testnet funds + registered hotkey.",
        )

    def _require_chain(self) -> None:
        if not bittensor_available():
            raise NotImplementedError(
                "BittensorKonnexProvider requires bittensor (konnex-chain-sdk). "
                "Install it: see docs/konnex.md §5."
            )
        if self._netuid is None:
            raise NotImplementedError(
                "BittensorKonnexProvider.netuid is not set. Register a fleet "
                "subnet first (bittensor CLI) and pass netuid=... ."
            )
        if self._subtensor is None:
            import bittensor as bt  # noqa: PLC0415

            self._subtensor = bt.subtensor(network=self._network)
            self._wallet = bt.wallet(name=self._wallet_name, hotkey=self._hotkey_name)
            self._metagraph = self._subtensor.metagraph(netuid=self._netuid)

    def submit_mission(self, metadata: MissionMetadata) -> SubmissionReceipt:  # noqa: ARG002
        """Broadcast a mission to miners via the metagraph (Launch tier)."""
        self._require_chain()
        # In a full implementation, the validator would iterate the metagraph
        # neurons and send a FleetMissionSynapse to each miner via dendrite.
        raise NotImplementedError(
            "BittensorKonnexProvider.submit_mission() is LAUNCH TIER.\n"
            "Requires a funded wallet + registered hotkey + fleet subnet netuid.\n"
            "See docs/konnex.md §5 and the konnex-chain-sdk."
        )

    def submit_evaluation(
        self,
        policy_id: str,  # noqa: ARG002
        eval_id: str,  # noqa: ARG002
        score: float,  # noqa: ARG002
        artifact_hash: str,  # noqa: ARG002
    ) -> SubmissionReceipt:
        """Record a validator evaluation (Launch tier)."""
        self._require_chain()
        raise NotImplementedError(
            "BittensorKonnexProvider.submit_evaluation() is LAUNCH TIER.\n"
            "Requires weight-setting permissions on the fleet subnet."
        )

    def publish_proof(self, artifact: EvaluationArtifact) -> SubmissionReceipt:  # noqa: ARG002
        """Anchor a PoPW proof on-chain (Launch tier)."""
        self._require_chain()
        raise NotImplementedError(
            "BittensorKonnexProvider.publish_proof() is LAUNCH TIER.\n"
            "Requires a registered hotkey and commit-reveal support."
        )

    def query_rewards(self, policy_id: str) -> float:  # noqa: ARG002
        """Read pending rewards from the metagraph incentive (Launch tier)."""
        self._require_chain()
        # In a full implementation: return self._metagraph.I[hotkey_uid]
        raise NotImplementedError(
            "BittensorKonnexProvider.query_rewards() is LAUNCH TIER.\n"
            "Metagraph incentive read requires a registered hotkey UID."
        )

    def get_submission_status(self, submission_id: str) -> dict[str, object]:  # noqa: ARG002
        """Query submission status from the chain (Launch tier)."""
        self._require_chain()
        raise NotImplementedError(
            "BittensorKonnexProvider.get_submission_status() is LAUNCH TIER.\n"
            "Requires querying extrinsics by hash on the subnet."
        )

    def close(self) -> None:
        self._subtensor = None
        self._wallet = None
        self._metagraph = None

    def __enter__(self) -> BittensorKonnexProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
