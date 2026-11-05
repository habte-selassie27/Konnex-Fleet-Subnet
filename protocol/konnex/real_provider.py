"""RealKonnexProvider — HTTP-based implementation against the documented Konnex API.

STATUS: PARTIAL — implements the three documented HTTP endpoints
(docs.konnex.world/sdk/http). The Python client source (sdk/python-client)
is still not installable (repo returns 404), so constructor auth and bundle
packaging remain unverified. `query_rewards` and `get_submission_status` have
no documented endpoint and remain STUBs.

Documented surface (verified 2026-11-01):
    POST /api/v1/tasks          body: {subnet, prompt, rewardStable, stakeStable, deadline}
    POST /api/v1/miners/models  body: {subnet, modelUri, kpi, stakeStable}
    POST /api/v1/validators/verify  body: {jobId, bundleUri}

Boundary contract (AGENTS.md §6.8): only protocol-safe types cross this
boundary. Zero imports from robotics/, simulation/, ml/, fleet/.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from protocol.konnex.models import MissionMetadata, SubmissionReceipt
from validator.reproducibility.artifact import EvaluationArtifact

logger = structlog.get_logger(__name__)

_DEFAULT_SUBNET = "sn.fleet.warehouse"


class RealKonnexProvider:
    """HTTP-based Konnex provider (documented endpoints only).

    ``endpoint`` is the API base URL (e.g. ``https://api.konnex.world``).
    ``api_key`` is sent as ``X-API-Key`` when non-empty (auth scheme is
    documented as deployment-specific; this is the most common convention).
    ``subnet`` defaults to ``sn.fleet.warehouse`` and can be overridden.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        *,
        subnet: str = _DEFAULT_SUBNET,
        timeout_s: float = 30.0,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._subnet = subnet
        self._client = httpx.Client(
            base_url=self._endpoint,
            timeout=timeout_s,
            headers={"X-API-Key": api_key} if api_key else {},
        )
        logger.info(
            "real_konnex_provider_initialized",
            endpoint=self._endpoint,
            subnet=self._subnet,
            sdk_verified=False,
            http_surface_verified=True,
        )

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(path, json=body)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f"Unexpected response shape from {path}: {data!r}")
        return data

    def submit_mission(self, metadata: MissionMetadata) -> SubmissionReceipt:
        """Register a mission as a Konnex task (POST /api/v1/tasks)."""
        body = {
            "subnet": self._subnet,
            "prompt": (
                f"warehouse fleet mission {metadata.mission_id} "
                f"({metadata.robot_count} robots, {metadata.task_count} tasks)"
            ),
            "rewardStable": 0.0,
            "stakeStable": 0.0,
            "deadline": 600,
        }
        try:
            data = self._post("/api/v1/tasks", body)
        except httpx.HTTPError as exc:
            logger.error("submit_mission_failed", error=str(exc))
            raise
        submission_id = str(data.get("jobId") or data.get("id") or data.get("taskId") or "")
        return SubmissionReceipt(
            submission_id=submission_id,
            status=str(data.get("status", "submitted")),
            tx_hash=str(data.get("txHash", "")),
        )

    def submit_evaluation(
        self,
        policy_id: str,  # noqa: ARG002
        eval_id: str,
        score: float,  # noqa: ARG002
        artifact_hash: str,
    ) -> SubmissionReceipt:
        """Submit an evaluation as a PoPW verification (POST /api/v1/validators/verify)."""
        body = {"jobId": eval_id, "bundleUri": artifact_hash}
        try:
            data = self._post("/api/v1/validators/verify", body)
        except httpx.HTTPError as exc:
            logger.error("submit_evaluation_failed", error=str(exc))
            raise
        submission_id = str(data.get("jobId") or data.get("id") or eval_id)
        return SubmissionReceipt(
            submission_id=submission_id,
            status=str(data.get("status", "verified")),
            tx_hash=str(data.get("txHash", "")),
        )

    def publish_proof(self, artifact: EvaluationArtifact) -> SubmissionReceipt:
        """Anchor an evaluation proof (submitted as a PoPW bundle URI)."""
        return self.submit_evaluation(
            policy_id=artifact.policy_id,
            eval_id=artifact.policy_id,
            score=artifact.final_score,
            artifact_hash=artifact.artifact_hash,
        )

    def query_rewards(self, policy_id: str) -> float:
        """Query pending KNX rewards.

        No reward-query endpoint is documented as of 2026-11-02, so this
        remains a STUB.
        """
        raise NotImplementedError(
            "RealKonnexProvider.query_rewards() is NOT IMPLEMENTED.\n"
            "No reward-query endpoint is documented (docs.konnex.world/sdk/http).\n"
            "Blocked on SDK / additional docs."
        )

    def get_submission_status(self, submission_id: str) -> dict[str, object]:
        """Query submission status.

        No submission-status endpoint is documented as of 2026-11-02, so this
        remains a STUB.
        """
        raise NotImplementedError(
            "RealKonnexProvider.get_submission_status() is NOT IMPLEMENTED.\n"
            "No submission-status endpoint is documented (docs.konnex.world/sdk/http).\n"
            "Blocked on SDK / additional docs."
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RealKonnexProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
