"""ARQ worker job tests — evaluation execution + persistence.

Status: COMPLETE. Uses a throwaway SQLite DB; no Redis or Docker required.
"""

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from backend.db.database import Database
from backend.services.evaluation_service import EvaluationService
from backend.services.storage_service import ArtifactStore
from backend.workers.arq_worker import run_evaluation_job


@pytest.fixture
def ctx(tmp_path: Path) -> Iterator[dict[str, Any]]:
    """Worker context with a real DB + artifact store in tmp_path."""
    database = Database(f"sqlite+aiosqlite:///{tmp_path}/worker.db")
    asyncio.run(database.create_all())
    yield {
        "db": database,
        "evaluations": EvaluationService(database, ArtifactStore(tmp_path / "artifacts")),
    }
    asyncio.run(database.dispose())


def test_evaluation_job_persists_scored_evaluations(ctx: dict[str, Any]) -> None:
    summary = asyncio.run(run_evaluation_job(ctx, "hungarian", [42]))

    assert summary["policy"] == "hungarian"
    assert summary["seeds"] == [42]
    assert summary["mean_final_score"] == summary["evaluations"][0]["final_score"]
    run = summary["evaluations"][0]
    assert run["status"] == "COMPLETE"
    assert run["final_score"] > 0.0

    stored = asyncio.run(ctx["evaluations"].list())
    assert len(stored) == 1
    assert stored[0].id == run["evaluation_id"]
    assert stored[0].policy_id == "hungarian"
    assert stored[0].final_score == run["final_score"]

    artifact_text = asyncio.run(ctx["evaluations"].artifact_text(run["evaluation_id"]))
    assert artifact_text is not None
    artifact = json.loads(artifact_text)
    assert artifact["policy_id"] == "hungarian"
    assert artifact["seed"] == 42
    assert artifact["final_score"] == run["final_score"]
    assert artifact["artifact_hash"] == stored[0].artifact_hash


def test_evaluation_job_rejects_unknown_policy(ctx: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="unknown policy"):
        asyncio.run(run_evaluation_job(ctx, "not-a-policy", [42]))


def test_evaluation_job_rejects_empty_seeds(ctx: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="seeds"):
        asyncio.run(run_evaluation_job(ctx, "nearest", []))
