"""Artifact storage service.

Supports two backends, selected by configuration:

- Local filesystem (default when MINIO_ENDPOINT is empty) — deterministic path
  convention {policy_hash}/{evaluation_id}.json (AGENTS.md §5.8).
- S3-compatible (MinIO / AWS S3) when MINIO_ENDPOINT is set, via boto3.

The public save()/load() interface is identical for both backends so callers
(EvaluationService, workers) are backend-agnostic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError


class ArtifactStore:
    """Artifact store with local-filesystem + S3-compatible backends."""

    def __init__(
        self,
        root: Path,
        minio_endpoint: str = "",
        minio_access_key: str = "minioadmin",
        minio_secret_key: str = "minioadmin",
        minio_bucket: str = "fleet-artifacts",
        minio_secure: bool = False,
    ) -> None:
        self._root = Path(root)
        self._endpoint = (minio_endpoint or "").strip()
        self._access_key = minio_access_key
        self._secret_key = minio_secret_key
        self._bucket = minio_bucket
        self._secure = minio_secure
        self._s3 = None
        if self._endpoint:
            self._s3 = boto3.client(
                "s3",
                endpoint_url=("https://" if self._secure else "http://") + self._endpoint,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                config=BotoConfig(signature_version="s3v4"),
                region_name="us-east-1",
            )
            self._ensure_bucket()

    def save(self, policy_hash: str, evaluation_id: str, payload: str) -> Any:
        key = f"{policy_hash}/{evaluation_id}.json"
        if self._s3 is not None:
            self._s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=payload.encode("utf-8"),
                ContentType="application/json",
            )
            return f"s3://{self._bucket}/{key}"
        directory = self._root / policy_hash
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{evaluation_id}.json"
        path.write_text(payload, encoding="utf-8")
        return path

    def load(self, policy_hash: str, evaluation_id: str) -> str | None:
        key = f"{policy_hash}/{evaluation_id}.json"
        if self._s3 is not None:
            try:
                resp = self._s3.get_object(Bucket=self._bucket, Key=key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                    return None
                raise
            body = resp["Body"].read()
            return body.decode("utf-8")
        path = self._root / policy_hash / f"{evaluation_id}.json"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def _ensure_bucket(self) -> None:
        try:
            self._s3.head_bucket(Bucket=self._bucket)
        except ClientError:
            try:
                self._s3.create_bucket(Bucket=self._bucket)
            except ClientError:
                pass

    @property
    def backend(self) -> str:
        return "s3" if self._s3 is not None else "local"
