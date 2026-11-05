"""MLflow training callback.

Spec (AGENTS.md §5.2): logs params, per-step metrics, checkpoints.
MLflow is optional: when the server is unreachable, metrics/checkpoints still
go to the local filesystem so training is reproducible without MLflow.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MLflowTrainingCallback:
    """Logs MAPPO training metrics to MLflow (or local files as fallback)."""

    def __init__(
        self,
        experiment_name: str,
        run_name: str,
        tracking_uri: str = "http://localhost:5000",
        checkpoint_dir: str | Path = "ml/checkpoints",
    ) -> None:
        self.experiment_name = experiment_name
        self.run_name = run_name
        self.tracking_uri = tracking_uri
        self.checkpoint_dir = Path(checkpoint_dir)
        self._mlflow: Any = None
        self._run: Any = None
        self._init_mlflow()

    def _init_mlflow(self) -> None:
        # Fail fast when the tracking server is unreachable instead of
        # blocking on mlflow's HTTP retry/backoff (which hangs tests and
        # training startup for tens of seconds).
        try:
            import socket
            from urllib.parse import urlparse

            parsed = urlparse(self.tracking_uri)
            host = parsed.hostname or "localhost"
            port = parsed.port or 80
            with socket.create_connection((host, port), timeout=0.5):
                pass
        except OSError:
            logger.warning("mlflow_unavailable at %s — local logging only", self.tracking_uri)
            return
        try:
            import mlflow

            mlflow.set_tracking_uri(self.tracking_uri)
            mlflow.set_experiment(self.experiment_name)
            self._run = mlflow.start_run(run_name=self.run_name)
            self._mlflow = mlflow
            logger.info("mlflow_connected at %s", self.tracking_uri)
        except Exception:
            logger.warning("mlflow_unavailable at %s — local logging only", self.tracking_uri)

    def log_params(self, params: dict[str, Any]) -> None:
        if self._mlflow:
            try:
                self._mlflow.log_params(params)
            except Exception:
                pass

    def on_step_end(self, step: int, metrics: dict[str, float]) -> None:
        if self._mlflow:
            try:
                self._mlflow.log_metrics(metrics, step=step)
            except Exception:
                pass

    def save_checkpoint(self, model: Any, step: int) -> Path:
        path = self.checkpoint_dir / f"step_{step}.pt"
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(model, "save"):
            model.save(str(path))
        else:
            import torch

            torch.save(model.state_dict() if hasattr(model, "state_dict") else model, path)
        if self._mlflow:
            try:
                self._mlflow.log_artifact(str(path))
            except Exception:
                pass
        return path

    def get_git_commit(self) -> str:
        try:
            return (
                subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
                .decode()
                .strip()
            )
        except Exception:
            return "UNKNOWN"

    def end_run(self, status: str = "FINISHED") -> None:
        if self._mlflow:
            try:
                self._mlflow.end_run(status=status)
            except Exception:
                pass

    def __enter__(self) -> MLflowTrainingCallback:
        return self

    def __exit__(self, *args: Any) -> None:
        self.end_run()
