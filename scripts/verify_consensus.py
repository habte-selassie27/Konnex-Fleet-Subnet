#!/usr/bin/env python3
"""Multi-validator consensus over a real containerized policy.

Runs the committed echo policy (`validator/examples/echo_policy`) inside the
Docker sandbox, through two **independent** validator instances, and records the
score spread. This is the live-container counterpart of
`scripts/verify_reproducibility.py` (which uses the in-process executor).

Gated on `KONNEX_POLICY_IMAGE`: with no image configured the script exits 2
("NOT RUN") rather than silently scoring an in-process fallback — a fake pass
would be worse than an honest skip.

Usage:
    docker build -t konnex-echo-policy validator/examples/echo_policy
    KONNEX_POLICY_IMAGE=konnex-echo-policy python scripts/verify_consensus.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from validator.consensus import (  # noqa: E402
    CONSENSUS_TOLERANCE,
    ConsensusRequest,
    ConsensusValidator,
)
from validator.examples.echo_policy.weights import echo_policy_hash  # noqa: E402
from validator.runner import ValidatorRunner  # noqa: E402
from validator.sandbox.docker_executor import DockerPolicyExecutor  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "experiments" / "results" / "validator_consensus"


def git_commit() -> str:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-validator consensus (real container)")
    parser.add_argument("--seeds", default="42,1000,1001")
    parser.add_argument("--tolerance", type=float, default=CONSENSUS_TOLERANCE)
    parser.add_argument("--output", default=str(OUTPUT_DIR))
    args = parser.parse_args()

    image = os.environ.get("KONNEX_POLICY_IMAGE", "").strip()
    if not image:
        print("NOT RUN — KONNEX_POLICY_IMAGE is unset.")
        print(
            "  Build the fixture: docker build -t konnex-echo-policy validator/examples/echo_policy"
        )
        print("  Then:              KONNEX_POLICY_IMAGE=konnex-echo-policy make verify-consensus")
        sys.exit(2)

    if not DockerPolicyExecutor.is_available():
        print(f"NOT RUN — Docker is unavailable, cannot run image {image!r}.")
        sys.exit(2)

    policy_hash = echo_policy_hash()
    print(f"Policy image: {image}")
    print(f"Policy hash:  {policy_hash}")

    # Two separate executors + runners: no shared state, so any divergence is a
    # harness/code issue rather than a cached result.
    runners = [
        ValidatorRunner(
            DockerPolicyExecutor(image),
            env_version="v1.0.0",
            sim_version="gazebo_harmonic",
        )
        for _ in range(2)
    ]
    consensus = ConsensusValidator(runners, tolerance=args.tolerance)

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    results: list[dict[str, Any]] = []
    for seed in seeds:
        request = ConsensusRequest(
            policy_id="echo-policy",
            policy_hash=policy_hash,
            scenario_id="warehouse_v1_20tasks",
            seed=seed,
            env_version="v1.0.0",
            sim_version="gazebo_harmonic",
        )
        result = consensus.validate(request)
        scores = [round(v.result.score.final, 4) for v in result.votes]
        statuses = [v.result.status for v in result.votes]
        print(
            f"  seed={seed:<6} scores={scores} statuses={statuses} "
            f"spread={result.score_spread:.4f} {result.status}"
        )
        results.append(
            {
                "seed": seed,
                "scores": scores,
                "statuses": statuses,
                "spread": result.score_spread,
                "agreed": result.agreed,
                "status": result.status,
                "rejection_reason": result.rejection_reason,
                "final_score": result.final_score,
            }
        )

    agreed = sum(1 for r in results if r["agreed"])
    max_spread = max((r["spread"] for r in results), default=0.0)
    passed = agreed == len(results)
    payload = {
        "policy_id": "echo-policy",
        "policy_hash": policy_hash,
        "policy_image": image,
        "validators": len(runners),
        "tolerance": args.tolerance,
        "seeds": results,
        "passed": passed,
        "agreed": agreed,
        "total": len(results),
        "max_spread": max_spread,
        "overall": "PASS" if passed else "DISPUTE",
        "git_commit": git_commit(),
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "consensus.json").write_text(json.dumps(payload, indent=2))

    print(
        f"\nConsensus: {agreed}/{len(results)} agreed, max spread {max_spread:.4f} "
        f"(tolerance {args.tolerance})"
    )
    print(f"Saved: {output_dir / 'consensus.json'}")
    if not passed:
        print("FAIL — validators disagree; no score may be published.")
        sys.exit(1)


if __name__ == "__main__":
    main()
