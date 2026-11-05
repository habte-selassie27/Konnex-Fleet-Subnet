#!/usr/bin/env python3
"""scripts/konnex_demo.py — Full Konnex lifecycle demo.

Demonstrates the complete PoPW lifecycle using the mock provider:
    1. Submit a mission to the (mock) Konnex network
    2. Run a fleet mission and produce an evaluation artifact
    3. Submit the evaluation result (score + artifact hash)
    4. Publish the sealed proof on-chain (mock tx)
    5. Query accumulated KNX rewards

Run with: make konnex-demo
    or:    python scripts/konnex_demo.py

Status: COMPLETE (mock provider).
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

# CLI script: bootstrap the project root so `python scripts/konnex_demo.py`
# works from anywhere (same pattern as experiments/scripts/run_experiment.py).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from protocol.konnex.factory import create_provider
from protocol.konnex.mock_provider import MockKonnexProvider
from protocol.konnex.models import MissionMetadata
from validator.reproducibility.artifact import EvaluationArtifact


def main() -> None:
    print("=" * 60)
    print("  Konnex Fleet Intelligence — PoPW Lifecycle Demo")
    print("=" * 60)
    print()

    # ─── 1. Create provider ──────────────────────────────────────────────
    print("[1/5] Creating mock Konnex provider ...")
    provider = create_provider(mode="mock")
    assert isinstance(provider, MockKonnexProvider)
    print(f"  Provider: {type(provider).__name__}")
    print()

    # ─── 2. Submit a mission ─────────────────────────────────────────────
    mission_id = str(uuid.uuid4())[:8]
    print(f"[2/5] Submitting mission {mission_id} ...")
    metadata = MissionMetadata(
        mission_id=mission_id,
        policy_id="policy_nearest",
        scenario_id="warehouse_v1",
        seed=42,
        robot_count=5,
        task_count=20,
        env_version="v1.0.0",
        sim_version="gazebo_harmonic",
    )
    mission_receipt = provider.submit_mission(metadata)
    print(f"  submission_id: {mission_receipt.submission_id}")
    print(f"  status:        {mission_receipt.status}")
    print(f"  tx_hash:       {mission_receipt.tx_hash}")
    print()

    # ─── 3. Simulate an evaluation ───────────────────────────────────────
    print("[3/5] Running simulated evaluation ...")
    time.sleep(0.1)  # simulate some work

    # Create a realistic evaluation artifact
    artifact = EvaluationArtifact(
        policy_id="policy_nearest",
        policy_hash="a1b2c3d4" * 8,  # 64-char hex
        scenario_id="warehouse_v1",
        seed=42,
        env_version="v1.0.0",
        sim_version="gazebo_harmonic",
        score_components={
            "mission_success": 0.90,
            "safety": 1.00,
            "efficiency": 0.85,
            "energy": 0.88,
            "coordination": 0.92,
            "robustness": 1.00,
        },
        final_score=91.4,
        completion_time_s=245.7,
        collision_count=0,
        tasks_completed=18,
        tasks_total=20,
        energy_consumed=42.3,
        timestamp=time.time(),
    )
    artifact.seal()
    print(f"  Artifact hash: {artifact.artifact_hash[:16]}...")
    print(f"  Final score:   {artifact.final_score}")
    print(f"  Verified:      {artifact.verify()}")
    print()

    # ─── 4. Submit evaluation + publish proof ────────────────────────────
    print("[4/5] Submitting evaluation and publishing proof ...")
    eval_id = str(uuid.uuid4())[:8]
    eval_receipt = provider.submit_evaluation(
        policy_id="policy_nearest",
        eval_id=eval_id,
        score=artifact.final_score,
        artifact_hash=artifact.artifact_hash,
    )
    print(f"  Eval receipt:  {eval_receipt.submission_id} ({eval_receipt.status})")

    proof_receipt = provider.publish_proof(artifact)
    print(f"  Proof receipt: {proof_receipt.submission_id} ({proof_receipt.status})")
    print(f"  On-chain tx:   {proof_receipt.tx_hash}")
    print()

    # ─── 5. Query rewards ────────────────────────────────────────────────
    print("[5/5] Querying KNX rewards ...")
    rewards = provider.query_rewards("policy_nearest")
    print("  Policy:        policy_nearest")
    print(f"  Accumulated:   {rewards:.4f} KNX")
    print()

    # ─── Summary ─────────────────────────────────────────────────────────
    print("=" * 60)
    print("  Demo Summary")
    print("=" * 60)
    print(f"  Missions submitted:  {provider.get_mission_count()}")
    print(f"  Evaluations submitted: {provider.get_eval_count()}")
    print(f"  Proofs published:    {provider.get_proof_count()}")
    print(f"  Total KNX rewards:   {rewards:.4f}")
    print()
    print("  All operations used the mock provider (no network calls).")
    print("  To use real Konnex network: set KONNEX_PROVIDER=real")
    print("  (requires SDK verification — see docs/konnex.md)")
    print("=" * 60)


if __name__ == "__main__":
    main()
