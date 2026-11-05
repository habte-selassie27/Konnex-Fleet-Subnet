"""Artifact storage service.

Status: COMPLETE (local filesystem, Phase 6).
MinIO/S3 storage is STUB (boto3 wiring deferred); the local store follows the
deterministic path convention {policy_hash}/{evaluation_id}.json (AGENTS.md §5.8)
so artifact deduplication works regardless of backend.
"""

from pathlib import Path


class ArtifactStore:
    """Local-filesystem artifact store."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def save(self, policy_hash: str, evaluation_id: str, payload: str) -> Path:
        """Persist an artifact and return its path."""
        directory = self._root / policy_hash
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{evaluation_id}.json"
        path.write_text(payload, encoding="utf-8")
        return path

    def load(self, policy_hash: str, evaluation_id: str) -> str | None:
        """Load an artifact's text, or None when missing."""
        path = self._root / policy_hash / f"{evaluation_id}.json"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")
