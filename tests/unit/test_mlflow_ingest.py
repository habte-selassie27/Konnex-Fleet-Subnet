"""Tests for file-backed MLflow evidence logging (ml/tracking/ingest.py)."""

from __future__ import annotations

import json
from pathlib import Path

from ml.tracking.ingest import ingest, verify


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _result_dir(tmp_path: Path) -> Path:
    results = tmp_path / "results"

    _write(
        results / "exp_001" / "result.json",
        {
            "experiment_id": "exp_001",
            "policy": "nearest",
            "scenario_id": "warehouse_v1",
            "seed_range": [1000, 1009],
            "n_runs": 10,
            "robot_count": 5,
            "mean_success_rate": 0.82,
            "std_success_rate": 0.04,
            "mean_completion_time_s": 400.0,
            "std_completion_time_s": 20.0,
            "mean_collision_count": 3.0,
            "std_collision_count": 1.0,
            "mean_popw_score": 82.5,
            "std_popw_score": 3.2,
            "status": "COMPLETE",
            "git_commit": "abc123",
        },
    )

    _write(
        results / "mappo_eval" / "result.json",
        {
            "policy": "mappo",
            "scenario_id": "warehouse_v1_20tasks",
            "seed_range": [1000, 1029],
            "n_runs": 30,
            "summary": {
                "mean_success_rate": 1.0,
                "std_success_rate": 0.0,
                "mean_completion_time_s": 135.6,
                "std_completion_time_s": 14.2,
                "mean_collision_count": 1.1,
                "mean_popw_score": 92.9,
                "std_popw_score": 2.1,
            },
            "git_commit": "abc123",
        },
    )

    _write(
        results / "fleet_env_unified" / "result.json",
        {
            "harness": "FleetEnv",
            "git_commit": "abc123",
            "policies": [
                {
                    "policy": "hungarian",
                    "harness": "FleetEnv",
                    "n_runs": 5,
                    "mean_success_rate": 1.0,
                    "mean_popw_score": 93.2,
                }
            ],
        },
    )

    _write(
        results / "exp_e2e_001" / "result.json",
        {"policy": "nearest", "status": "COMPLETE", "mean_popw_score": 1.0},
    )
    return results


def test_ingest_logs_every_benchmark_artifact(tmp_path: Path) -> None:
    results = _result_dir(tmp_path)
    uri = f"file:{tmp_path}/mlruns"

    # 3 artifacts, one of which carries 1 nested policy -> 3 runs
    # (the exp_e2e smoke run is intentionally excluded).
    assert ingest(results, uri) == 3
    assert verify(uri) == 3


def test_ingest_is_idempotent(tmp_path: Path) -> None:
    results = _result_dir(tmp_path)
    uri = f"file:{tmp_path}/mlruns"

    ingest(results, uri)
    assert ingest(results, uri) == 0


def test_nested_summary_metrics_are_flattened(tmp_path: Path) -> None:
    import mlflow
    from mlflow.tracking import MlflowClient

    results = _result_dir(tmp_path)
    uri = f"file:{tmp_path}/mlruns"
    ingest(results, uri)

    mlflow.set_tracking_uri(uri)
    client = MlflowClient()
    experiment = client.get_experiment_by_name("konnex-fleet-benchmarks")
    assert experiment is not None
    runs = {
        run.data.tags.get("mlflow.runName"): run
        for run in client.search_runs([experiment.experiment_id])
    }

    mappo_run = runs["mappo@mappo_eval"]
    assert mappo_run.data.metrics["mean_popw_score"] == 92.9
    assert mappo_run.data.params["git_commit"] == "abc123"
