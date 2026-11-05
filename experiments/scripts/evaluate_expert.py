#!/usr/bin/env python3
"""Evaluate the FleetEnv heuristic expert as an apples-to-apples baseline.

The MAPPO actor is scored in FleetEnv, while the classical allocators are
scored by the orchestrator benchmark. Those are different simulators, so this
script measures the heuristic expert (greedy nearest task + task-seeking
controller) in the *same* FleetEnv used to evaluate MAPPO.

Usage:
    python experiments/scripts/evaluate_expert.py \
        --seeds 1000-1029 \
        --output experiments/results/fleet_env_expert
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ml.env.fleet_env import FleetEnv, FleetEnvConfig  # noqa: E402
from ml.evaluation.rollout import MAPPORolloutResult, summarize  # noqa: E402
from ml.training.bc_pretrain import expert_action  # noqa: E402
from validator.scoring.engine import MissionResult, PoPWScoringEngine  # noqa: E402


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
    parser = argparse.ArgumentParser(description="Evaluate the FleetEnv expert baseline")
    parser.add_argument("--seeds", default="1000-1029", help="e.g. 1000-1029")
    parser.add_argument("--robot-count", type=int, default=5)
    parser.add_argument("--task-count", type=int, default=20)
    parser.add_argument("--time-limit", type=float, default=600.0)
    parser.add_argument(
        "--output",
        default="experiments/results/fleet_env_expert",
        help="Directory for result.json",
    )
    args = parser.parse_args()

    config = FleetEnvConfig(
        robot_count=args.robot_count,
        task_count=args.task_count,
        time_limit_s=args.time_limit,
    )
    env = FleetEnv(config)
    scorer = PoPWScoringEngine()
    seeds = parse_seeds(args.seeds)
    results: list[MAPPORolloutResult] = []

    for seed in seeds:
        observations, _ = env.reset(seed=seed)
        done = False
        info: dict[str, Any] = {}
        while not done:
            actions = {agent_id: expert_action(obs) for agent_id, obs in observations.items()}
            observations, _, terminateds, truncateds, info = env.step(actions)
            done = bool(terminateds.get("__all__", False) or truncateds.get("__all__", False))

        metrics = info.get("__all__", {})
        tasks_completed = int(metrics.get("tasks_completed", 0))
        tasks_total = int(metrics.get("tasks_total", env.tasks_total()))
        energy_consumed = float(metrics.get("energy_consumed", env.energy_consumed()))
        score = scorer.score(
            MissionResult(
                tasks_completed=tasks_completed,
                tasks_total=tasks_total,
                elapsed_s=float(metrics.get("elapsed_s", 0.0)),
                time_limit_s=config.time_limit_s,
                collision_count=int(metrics.get("collision_count", 0)),
                energy_consumed=energy_consumed,
                energy_budget=config.robot_count * 100.0,
            )
        )
        results.append(
            MAPPORolloutResult(
                seed=seed,
                tasks_completed=tasks_completed,
                tasks_total=tasks_total,
                success_rate=tasks_completed / tasks_total if tasks_total else 0.0,
                elapsed_s=float(metrics.get("elapsed_s", 0.0)),
                collision_count=int(metrics.get("collision_count", 0)),
                energy_consumed=energy_consumed,
                popw_score=score.final,
                mission_complete=bool(metrics.get("mission_complete", False)),
                episode_steps=int(metrics.get("episode_steps", 0)),
            )
        )

    summary = summarize(results)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "policy": "expert",
        "checkpoint": None,
        "scenario_id": f"warehouse_v1_{args.task_count}tasks",
        "seed_range": [seeds[0], seeds[-1]],
        "n_runs": len(results),
        "deterministic": True,
        "summary": summary,
        "runs": [asdict(r) for r in results],
        "git_commit": git_commit(),
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (output_dir / "result.json").write_text(json.dumps(payload, indent=2))

    print(f"FleetEnv expert evaluation: {len(results)} seeds")
    print(f"  Success: {summary['mean_success_rate']:.1%} ± {summary['std_success_rate']:.1%}")
    print(f"  PoPW:    {summary['mean_popw_score']:.1f} ± {summary['std_popw_score']:.1f}")
    print(f"  Saved:   {output_dir / 'result.json'}")


if __name__ == "__main__":
    main()
