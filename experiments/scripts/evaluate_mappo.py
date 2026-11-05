#!/usr/bin/env python3
"""Evaluate a trained MAPPO checkpoint in FleetEnv.

Usage:
    python experiments/scripts/evaluate_mappo.py \
        --checkpoint ml/checkpoints/step_204800.pt \
        --seeds 1000-1009 \
        --output experiments/results/mappo_eval

This is the only valid MAPPO benchmark path. It reports real rollout metrics
and never falls back to another policy.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ml.env.fleet_env import FleetEnvConfig
from ml.evaluation.rollout import evaluate_checkpoint, summarize


def parse_seeds(value: str) -> list[int]:
    if "-" in value:
        start, end = value.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(part) for part in value.split(",")]


def git_commit() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=PROJECT_ROOT,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "UNKNOWN"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate MAPPO in FleetEnv")
    parser.add_argument("--checkpoint", required=True, help="Path to a MAPPO .pt checkpoint")
    parser.add_argument("--seeds", default="1000-1009", help="e.g. 1000-1009 or 1000,1002")
    parser.add_argument("--robot-count", type=int, default=5)
    parser.add_argument("--task-count", type=int, default=20)
    parser.add_argument("--time-limit", type=float, default=600.0)
    parser.add_argument(
        "--output",
        default="experiments/results/mappo_eval",
        help="Directory for result.json",
    )
    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="Sample actions instead of using the deterministic mean",
    )
    args = parser.parse_args()

    config = FleetEnvConfig(
        robot_count=args.robot_count,
        task_count=args.task_count,
        time_limit_s=args.time_limit,
    )
    results = evaluate_checkpoint(
        checkpoint_path=args.checkpoint,
        seeds=parse_seeds(args.seeds),
        config=config,
        deterministic=not args.stochastic,
    )
    summary = summarize(results)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "policy": "mappo",
        "checkpoint": str(Path(args.checkpoint).resolve()),
        "scenario_id": f"warehouse_v1_{args.task_count}tasks",
        "seed_range": [parse_seeds(args.seeds)[0], parse_seeds(args.seeds)[-1]],
        "n_runs": len(results),
        "deterministic": not args.stochastic,
        "summary": summary,
        "runs": [asdict(r) for r in results],
        "git_commit": git_commit(),
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (output_dir / "result.json").write_text(json.dumps(payload, indent=2))

    print(f"MAPPO evaluation: {len(results)} seeds")
    print(f"  Success: {summary['mean_success_rate']:.1%} ± {summary['std_success_rate']:.1%}")
    print(f"  PoPW:    {summary['mean_popw_score']:.1f} ± {summary['std_popw_score']:.1f}")
    print(f"  Saved:   {output_dir / 'result.json'}")


if __name__ == "__main__":
    main()
