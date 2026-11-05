#!/usr/bin/env python3
"""Unified cross-harness benchmark: every policy scored inside FleetEnv.

Runs nearest / hungarian / cost_optimizer / expert / MAPPO through one
simulator, one controller and one PoPW engine over an identical seed set, so
the classical-vs-MAPPO comparison no longer mixes harnesses.

Usage:
    python experiments/scripts/benchmark_fleet_env.py --seeds 1000-1029
    python experiments/scripts/benchmark_fleet_env.py --seeds 1000-1009 \
        --policies nearest,hungarian,mappo --checkpoint ml/checkpoints/step_bc_v3.pt

Outputs (real runs only — AGENTS.md Law 1):
    experiments/results/fleet_env_unified/result.json
    experiments/results/fleet_env_unified/benchmark_table.md
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fleet.task_allocator.base import TaskAllocator  # noqa: E402
from fleet.task_allocator.cost_optimizer import CostOptimizerAllocator  # noqa: E402
from fleet.task_allocator.hungarian import HungarianAllocator  # noqa: E402
from fleet.task_allocator.nearest import NearestTaskAllocator  # noqa: E402
from ml.env.fleet_env import FleetEnv, FleetEnvConfig  # noqa: E402
from ml.evaluation.allocator_policy import (  # noqa: E402
    AllocatorPolicy,
    allocator_action_fn,
    expert_action_fn,
    mappo_action_fn,
)
from validator.scoring.engine import MissionResult, PoPWScoringEngine  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "experiments" / "results" / "fleet_env_unified"
DEFAULT_CHECKPOINT = PROJECT_ROOT / "ml" / "checkpoints" / "step_bc_v3.pt"

ALLOCATORS: dict[str, type[TaskAllocator]] = {
    "nearest": NearestTaskAllocator,
    "hungarian": HungarianAllocator,
    "cost_optimizer": CostOptimizerAllocator,
}


@dataclass
class PolicyRuns:
    """Per-policy rollout results scored by the shared harness."""

    policy: str
    harness: str
    seeds: list[int]
    n_runs: int
    mean_success_rate: float
    std_success_rate: float
    mean_completion_time_s: float
    std_completion_time_s: float
    mean_collision_count: float
    std_collision_count: float
    mean_popw_score: float
    std_popw_score: float
    status: str
    runs: list[dict[str, Any]]
    note: str = ""


def parse_seeds(value: str) -> list[int]:
    if "-" in value:
        start, end = value.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(part) for part in value.split(",")]


def git_metadata() -> tuple[str, bool]:
    """Return (commit hash, dirty flag); ('NO_GIT_REPO', False) when absent."""
    try:
        commit = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL
            ).strip()
        )
        return commit, dirty
    except Exception:
        return "NO_GIT_REPO", False


def _summarize(
    policy: str, seeds: list[int], rows: list[dict[str, Any]], note: str = ""
) -> PolicyRuns:
    import statistics

    scores = [float(r["popw_score"]) for r in rows]
    rates = [float(r["success_rate"]) for r in rows]
    times = [float(r["elapsed_s"]) for r in rows]
    collisions = [float(r["collision_count"]) for r in rows]

    def std(values: list[float]) -> float:
        return statistics.stdev(values) if len(values) > 1 else 0.0

    return PolicyRuns(
        policy=policy,
        harness="FleetEnv",
        seeds=seeds,
        n_runs=len(rows),
        mean_success_rate=statistics.mean(rates),
        std_success_rate=std(rates),
        mean_completion_time_s=statistics.mean(times),
        std_completion_time_s=std(times),
        mean_collision_count=statistics.mean(collisions),
        std_collision_count=std(collisions),
        mean_popw_score=statistics.mean(scores),
        std_popw_score=std(scores),
        status="COMPLETE",
        runs=rows,
        note=note,
    )


def run_policy(
    policy: str,
    seeds: list[int],
    config: FleetEnvConfig,
    checkpoint: Path | None,
) -> PolicyRuns:
    """Run one policy over all seeds inside a fresh FleetEnv."""
    env = FleetEnv(config)
    scorer = PoPWScoringEngine()

    action_fn: Any
    note = ""
    if policy in ALLOCATORS:
        adapter = AllocatorPolicy(ALLOCATORS[policy]())
        env.set_assignment_provider(adapter.provider)
        action_fn = allocator_action_fn()
        note = "allocator chooses assignment; env controller drives (FleetEnv)"
    elif policy == "expert":
        action_fn = expert_action_fn()
        note = "heuristic task-seeker (same controller as MAPPO)"
    elif policy == "mappo":
        if checkpoint is None or not Path(checkpoint).exists():
            raise SystemExit(f"MAPPO checkpoint not found: {checkpoint}")
        from ml.policies.mappo.agent import MAPPOAgent

        agent = MAPPOAgent.from_checkpoint(str(checkpoint))
        action_fn = mappo_action_fn(agent)
        note = f"checkpoint={Path(checkpoint).name}"
    else:
        known = sorted({*ALLOCATORS, "expert", "mappo"})
        raise SystemExit(f"Unknown policy {policy!r}. Choose from {known}")

    rows: list[dict[str, Any]] = []
    for seed in seeds:
        observations, _ = env.reset(seed=seed)
        done = False
        info: dict[str, Any] = {}
        while not done:
            actions = action_fn(env, observations)
            observations, _, terminateds, truncateds, info = env.step(actions)
            done = bool(terminateds.get("__all__", False) or truncateds.get("__all__", False))

        metrics = info.get("__all__", {})
        tasks_completed = int(metrics.get("tasks_completed", 0))
        tasks_total = int(metrics.get("tasks_total", env.tasks_total()))
        elapsed_s = float(metrics.get("elapsed_s", 0.0))
        score = scorer.score(
            MissionResult(
                tasks_completed=tasks_completed,
                tasks_total=tasks_total,
                elapsed_s=elapsed_s,
                time_limit_s=config.time_limit_s,
                collision_count=int(metrics.get("collision_count", 0)),
                energy_consumed=float(metrics.get("energy_consumed", env.energy_consumed())),
                energy_budget=config.robot_count * 100.0,
            )
        )
        rows.append(
            {
                "seed": seed,
                "tasks_completed": tasks_completed,
                "tasks_total": tasks_total,
                "success_rate": tasks_completed / tasks_total if tasks_total else 0.0,
                "elapsed_s": elapsed_s,
                "collision_count": int(metrics.get("collision_count", 0)),
                "energy_consumed": float(metrics.get("energy_consumed", 0.0)),
                "popw_score": score.final,
                "mission_complete": bool(metrics.get("mission_complete", False)),
            }
        )

    env.set_assignment_provider(None)
    return _summarize(policy, seeds, rows, note=note)


def markdown_table(results: list[PolicyRuns]) -> str:
    lines = [
        "| Policy | Success | Time (s) | Collisions | PoPW | Runs |",
        "|--------|---------|----------|------------|------|------|",
    ]
    for r in results:
        lines.append(
            f"| {r.policy} | {r.mean_success_rate:.1%} ± {r.std_success_rate:.1%} "
            f"| {r.mean_completion_time_s:.1f} ± {r.std_completion_time_s:.1f} "
            f"| {r.mean_collision_count:.1f} ± {r.std_collision_count:.1f} "
            f"| {r.mean_popw_score:.1f} ± {r.std_popw_score:.1f} | {r.n_runs} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified FleetEnv benchmark")
    parser.add_argument("--seeds", default="1000-1009")
    parser.add_argument(
        "--policies",
        default="nearest,hungarian,cost_optimizer,expert,mappo",
        help="comma-separated subset",
    )
    parser.add_argument("--robot-count", type=int, default=5)
    parser.add_argument("--task-count", type=int, default=20)
    parser.add_argument("--time-limit", type=float, default=600.0)
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--output", default=str(RESULTS_DIR))
    args = parser.parse_args()

    seeds = parse_seeds(args.seeds)
    policies = [p.strip() for p in args.policies.split(",") if p.strip()]
    checkpoint = Path(args.checkpoint) if "mappo" in policies else None
    config = FleetEnvConfig(
        robot_count=args.robot_count,
        task_count=args.task_count,
        time_limit_s=args.time_limit,
    )

    results: list[PolicyRuns] = []
    for policy in policies:
        started = time.monotonic()
        result = run_policy(policy, seeds, config, checkpoint)
        results.append(result)
        print(
            f"  {policy:<16} PoPW {result.mean_popw_score:6.1f} ± {result.std_popw_score:4.1f}  "
            f"success {result.mean_success_rate:6.1%}  "
            f"({time.monotonic() - started:.1f}s)"
        )

    commit, dirty = git_metadata()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "harness": "FleetEnv",
        "scenario": f"warehouse_v1_{args.task_count}tasks",
        "robot_count": args.robot_count,
        "task_count": args.task_count,
        "seed_range": [seeds[0], seeds[-1]],
        "methodology": (
            "All policies scored in the same FleetEnv with identical seeds. "
            "Allocator policies choose assignments via FleetEnv's assignment "
            "provider and follow the task waypoint; expert and MAPPO emit "
            "waypoints directly."
        ),
        "git_commit": commit,
        "git_dirty": dirty,
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "policies": [asdict(r) for r in results],
    }
    (output_dir / "result.json").write_text(json.dumps(payload, indent=2))
    table = markdown_table(results)
    (output_dir / "benchmark_table.md").write_text(table + "\n")

    print(f"\nUnified harness: {len(results)} policies × {len(seeds)} seeds")
    print(table)
    print(f"\nSaved: {output_dir / 'result.json'}")
    print(f"Git:   {commit}{' (dirty)' if dirty else ''}")


if __name__ == "__main__":
    main()
