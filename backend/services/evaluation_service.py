"""EvaluationService — persistence for evaluation results and artifacts.

Status: COMPLETE (Phase 6).
"""

import json
import uuid

from backend.db.database import Database
from backend.db.models import EvaluationRecord
from backend.schemas import EvaluationResponse, EvaluationSubmitRequest
from backend.services.storage_service import ArtifactStore


class EvaluationService:
    """Stores evaluation records in the DB and artifacts in the store."""

    def __init__(self, db: Database, store: ArtifactStore) -> None:
        self._db = db
        self._store = store

    async def submit(self, request: EvaluationSubmitRequest) -> EvaluationResponse:
        """Persist an evaluation + artifact and return the API response."""
        record_id = str(uuid.uuid4())
        artifact_text = json.dumps(request.artifact, sort_keys=True, indent=2)
        artifact_path = self._store.save(request.policy_hash, record_id, artifact_text)

        record = EvaluationRecord(
            id=record_id,
            policy_id=request.policy_id,
            policy_hash=request.policy_hash,
            scenario_id=request.scenario_id,
            seed=request.seed,
            env_version=request.env_version,
            sim_version=request.sim_version,
            status=request.status,
            final_score=request.final_score,
            artifact_hash=request.artifact_hash,
            artifact_path=str(artifact_path),
        )
        async with self._db.session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return self._to_response(record)

    async def get(self, evaluation_id: str) -> EvaluationResponse | None:
        """Fetch an evaluation, or None when it does not exist."""
        async with self._db.session() as session:
            record = await session.get(EvaluationRecord, evaluation_id)
        if record is None:
            return None
        return self._to_response(record)

    async def artifact_text(self, evaluation_id: str) -> str | None:
        """Return the stored artifact text for an evaluation, or None."""
        async with self._db.session() as session:
            record = await session.get(EvaluationRecord, evaluation_id)
        if record is None:
            return None
        return self._store.load(record.policy_hash, record.id)

    @staticmethod
    def _to_response(record: EvaluationRecord) -> EvaluationResponse:
        return EvaluationResponse(
            id=record.id,
            policy_id=record.policy_id,
            status=record.status,
            final_score=record.final_score,
            artifact_hash=record.artifact_hash,
            artifact_url=f"/api/v1/evaluations/{record.id}/artifact",
        )
