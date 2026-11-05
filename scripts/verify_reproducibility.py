#!/usr/bin/env python3
"""Verify two-validator reproducibility (±0.5 PoPW) for the Spark grant gate.

Runs the same policy/seed through two independent in-process validator
instances (separate executor objects, separate RNG state) and asserts their
scores agree within the configured tolerance (0.5 by default).

Usage:
    python scripts/verify_reproducibility.py
    python scripts/verify_reproducibility.py --policy nearest --seeds 42 1000 1001
    python scripts/verify_reproducibility.py \\
        --output experiments/results/reproducibility_report.json

Exit code: 0 on pass, 1 on any failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fleet.task_allocator.cost_optimizer import CostOptimizerAllocator
from fleet.task_allocator.hungarian import HungarianAllocator
from fleet.task_allocator.nearest import NearestTaskAllocator
from validator.consensus import CONSENSUS_TOLERANCE
from validator.reproducibility.verifier import ReproducibilityVerifier
from validator.runner import ValidationRequest, ValidatorRunner
from validator.sandbox.executor import InProcessPolicyExecutor, PolicyEntry
from validator.sandbox.resource_limits import ResourceLimits

POLICY_FACTORIES = {
    "nearest": NearestTaskAllocator,
    "hungarian": HungarianAllocator,
    "cost_optimizer": CostOptimizerAllocator,
}


def _hash(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run(policy: str, seeds: list[int], output: Path | None) -> int:
    factory = POLICY_FACTORIES[policy]
    registry = {
        policy: PolicyEntry(weights=policy.encode(), factory=factory)  # type: ignore[arg-type]
    }

    failures = 0
    seeds_report: list[dict[str, object]] = []
    report: dict[str, object] = {"policy": policy, "tolerance": CONSENSUS_TOLERANCE}

    for seed in seeds:
        runner_a = ValidatorRunner(InProcessPolicyExecutor(registry))
        runner_b = ValidatorRunner(InProcessPolicyExecutor(registry))
        request = ValidationRequest(
            policy_id=policy,
            policy_hash=_hash(policy.encode()),
            scenario_id="warehouse_v1_20tasks",
            seed=seed,
            env_version="v1.0.0",
            sim_version="gazebo_harmonic",
            resource_limits=ResourceLimits.default(),
        )
        result = ReproducibilityVerifier([runner_a, runner_b]).verify(request)
        status = "PASS" if result.agreed else "FAIL"
        if not result.agreed:
            failures += 1
        print(
            f"[{status}] policy={policy} seed={seed} "
            f"scores={result.scores} spread={result.spread:.4f} "
            f"tolerance={result.tolerance}"
        )
        seeds_report.append(
            {
                "seed": seed,
                "scores": result.scores,
                "spread": result.spread,
                "agreed": result.agreed,
                "status": result.status,
            }
        )

    report["seeds"] = seeds_report
    report["passed"] = len(seeds) - failures
    report["failed"] = failures
    report["overall"] = "PASS" if failures == 0 else "FAIL"

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2))
        print(f"\nReport saved to {output}")

    print(f"\nOverall: {report['overall']} ({report['passed']}/{len(seeds)} seeds)")
    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Two-validator reproducibility check")
    parser.add_argument("--policy", default="nearest", choices=sorted(POLICY_FACTORIES))
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 1000, 1001, 1002])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/results/reproducibility_report.json"),
    )
    args = parser.parse_args()
    return run(args.policy, args.seeds, args.output)


if __name__ == "__main__":
    sys.exit(main())
