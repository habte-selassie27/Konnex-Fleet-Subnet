"""Ingest recorded experiment results into a file-backed MLflow tracker.

MLflow was configured in docker-compose but never produced evidence. This
module writes the *existing, real* benchmark artifacts into a local
`mlruns/` store so the tracking registry reflects actual runs — no server, no
new dependency, no fabricated metrics.

Usage:
    python -m ml.tracking.ingest                 # write mlruns/ + verify read-back
    python -m ml.tracking.ingest --verify-only   # read-back check only
    mlflow ui --backend-store-uri ./mlruns       # inspect runs

Each ingested run records the source artifact path and git commit, so a run in
the UI can be traced back to exactly one result.json.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"
MLRUNS_DIR = PROJECT_ROOT / "mlruns"
EXPERIMENT_NAME = "konnex-fleet-benchmarks"

# Metric keys shared by every result format (flat or nested "summary").
_METRIC_KEYS = (
    "mean_success_rate",
    "std_success_rate",
    "mean_completion_time_s",
    "std_completion_time_s",
    "mean_collision_count",
    "std_collision_count",
    "mean_popw_score",
    "std_popw_score",
)


def git_commit() -> str:
    """Current commit, or NO_GIT_REPO when the checkout has no history."""
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
    except Exception:
        return "NO_GIT_REPO"


def _flatten(result: dict[str, Any]) -> dict[str, Any]:
    """Flatten a nested ``summary`` block into the top level."""
    summary = result.get("summary")
    if isinstance(summary, dict):
        return {**summary, **{k: v for k, v in result.items() if k != "summary"}}
    return dict(result)


def collect_runs(results_dir: Path) -> list[tuple[str, dict[str, Any], Path]]:
    """Return (run_name, flattened result, source path) for every artifact."""
    runs: list[tuple[str, dict[str, Any], Path]] = []
    for path in sorted(results_dir.rglob("result.json")):
        if path.parent.name.startswith("exp_e2e"):
            continue  # end-to-end smoke evidence, not a benchmark
        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue

        policies = raw.get("policies")
        if isinstance(policies, list):  # unified FleetEnv harness
            for entry in policies:
                if not isinstance(entry, dict):
                    continue
                name = f"{entry.get('policy', 'unknown')}@{path.parent.name}"
                runs.append(
                    (
                        name,
                        {
                            **_flatten(entry),
                            **{
                                k: raw[k] for k in raw if k in ("harness", "scenario", "git_commit")
                            },
                        },
                        path,
                    )
                )
            continue

        name = f"{raw.get('policy', 'unknown')}@{path.parent.name}"
        runs.append((name, _flatten(raw), path))
    return runs


def _params(result: dict[str, Any], path: Path) -> dict[str, str]:
    try:
        source = str(path.relative_to(PROJECT_ROOT))
    except ValueError:  # results outside the repo (tests, external runs)
        source = str(path)
    seed_range = result.get("seed_range")
    return {
        "policy": str(result.get("policy", "unknown")),
        "harness": str(result.get("harness", "orchestrator")),
        "scenario": str(result.get("scenario_id") or result.get("scenario") or "unknown"),
        "robot_count": str(result.get("robot_count", "unknown")),
        "n_runs": str(result.get("n_runs", "unknown")),
        "seed_range": str(seed_range) if seed_range else "unknown",
        "status": str(result.get("status", "COMPLETE")),
        "git_commit": str(result.get("git_commit", "NO_GIT_REPO")),
        "source_artifact": source,
    }


def _metrics(result: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key in _METRIC_KEYS:
        value = result.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = float(value)
    return out


def ingest(results_dir: Path = RESULTS_DIR, tracking_uri: str | None = None) -> int:
    """Log every recorded result as an MLflow run. Returns the run count."""
    import mlflow
    from mlflow.tracking import MlflowClient

    uri = tracking_uri or f"file:{MLRUNS_DIR}"
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(EXPERIMENT_NAME)
    client = MlflowClient()
    experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
    existing = (
        {
            run.data.tags.get("mlflow.runName")
            for run in client.search_runs([experiment.experiment_id])
        }
        if experiment
        else set()
    )

    logged = 0
    for name, result, path in collect_runs(results_dir):
        if name in existing:
            print(f"  skip (already logged): {name}")
            continue
        with mlflow.start_run(run_name=name):
            mlflow.log_params(_params(result, path))
            metrics = _metrics(result)
            if metrics:
                mlflow.log_metrics(metrics)
            mlflow.set_tag("source", "experiments/results")
            mlflow.set_tag("git_commit", str(result.get("git_commit", "NO_GIT_REPO")))
            mlflow.log_artifact(str(path))
        logged += 1
        print(f"  logged: {name} ({len(metrics)} metrics)")
    return logged


def verify(tracking_uri: str | None = None) -> int:
    """Read the runs back out of the store; returns the run count."""
    import mlflow
    from mlflow.tracking import MlflowClient

    uri = tracking_uri or f"file:{MLRUNS_DIR}"
    mlflow.set_tracking_uri(uri)
    client = MlflowClient()
    experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
    if experiment is None:
        print("No MLflow experiment found — run the ingest first.")
        return 0
    runs = client.search_runs([experiment.experiment_id])
    print(f"MLflow store: {uri}")
    print(f"Experiment:   {EXPERIMENT_NAME} ({len(runs)} runs)")
    for run in runs:
        popw = run.data.metrics.get("mean_popw_score")
        success = run.data.metrics.get("mean_success_rate")
        score = f"{popw:.1f}" if popw is not None else "—"
        rate = f"{success:.1%}" if success is not None else "—"
        print(
            f"  {run.data.tags.get('mlflow.runName', '?'):<40} PoPW {score:>6}  success {rate:>7}"
        )
    return len(runs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest benchmark results into MLflow")
    parser.add_argument("--results-dir", default=str(RESULTS_DIR))
    parser.add_argument("--tracking-uri", default=None)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if not args.verify_only:
        count = ingest(Path(args.results_dir), args.tracking_uri)
        print(f"Ingested {count} run(s) into {args.tracking_uri or f'file:{MLRUNS_DIR}'}")
    total = verify(args.tracking_uri)
    if total == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
