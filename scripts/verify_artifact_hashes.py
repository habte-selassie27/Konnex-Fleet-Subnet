#!/usr/bin/env python3
"""Validate artifact hashes across all saved experiment results.

Scans ``experiments/results/`` recursively for JSON files and verifies that
every embedded or standalone ``EvaluationArtifact`` has a valid, intact hash
(``EvaluationArtifact.verify()``). This is the tamper-detection complement to
``scripts/verify_benchmark_logs.py`` (which validates log structure, not hash
integrity).

Exit code 0 = all artifacts valid, 1 = any artifact invalid/tampered,
2 = no artifacts found to check.

Usage:
    python scripts/verify_artifact_hashes.py
    python scripts/verify_artifact_hashes.py --results-dir experiments/results
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from validator.reproducibility.artifact import EvaluationArtifact

DEFAULT_RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"_error": str(exc), "_path": str(path)}


def _is_artifact_shape(data: dict[str, Any]) -> bool:
    """Heuristic: an EvaluationArtifact has policy_id, policy_hash, scenario_id,
    seed, final_score, and optionally artifact_hash."""
    required = {"policy_id", "policy_hash", "scenario_id", "seed", "final_score"}
    return required.issubset(set(data.keys()))


def _validate_file(path: Path) -> list[str]:
    """Return a list of human-readable problems for one JSON file (empty when clean)."""
    problems: list[str] = []
    label = str(path.relative_to(DEFAULT_RESULTS_DIR.parent))

    raw = _load_json(path)
    if not isinstance(raw, dict):
        problems.append(f"{label}: not a JSON object")
        return problems

    if "_error" in raw:
        problems.append(f"{label}: unparseable JSON ({raw['_error']})")
        return problems

    # Case 1: the file IS a sealed EvaluationArtifact.
    if _is_artifact_shape(raw):
        try:
            artifact = EvaluationArtifact.from_json(json.dumps(raw))
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"{label}: cannot deserialize as EvaluationArtifact ({exc})")
            return problems

        if not artifact.artifact_hash:
            problems.append(f"{label}: artifact_hash is empty (artifact not sealed)")
        elif not artifact.verify():
            problems.append(
                f"{label}: artifact_hash mismatch — artifact has been tampered with "
                f"(stored={artifact.artifact_hash}, computed={artifact.compute_hash()})"
            )
        else:
            problems.append(f"{label}: artifact hash OK")
        return problems

    # Case 2: the file embeds a list of artifacts (e.g. reproducibility reports
    # with per-seed artifact entries, or rollout results with embedded runs).
    embedded = raw.get("artifacts") or raw.get("runs") or raw.get("seeds")
    if isinstance(embedded, list):
        for i, entry in enumerate(embedded):
            if not isinstance(entry, dict):
                continue
            # Reproducibility reports store per-seed scores, not full artifacts.
            if "scores" in entry and "artifact_hash" not in entry:
                continue
            if _is_artifact_shape(entry):
                try:
                    artifact = EvaluationArtifact.from_json(json.dumps(entry))
                except (KeyError, TypeError, ValueError):
                    continue
                if not artifact.artifact_hash:
                    problems.append(f"{label}[{i}]: artifact_hash is empty (artifact not sealed)")
                elif not artifact.verify():
                    problems.append(f"{label}[{i}]: artifact_hash mismatch — tampered")
        return problems

    # Case 3: file has no artifact shape — nothing to validate here.
    return problems


def audit(results_dir: Path) -> tuple[list[str], int]:
    """Return (problems, artifacts_checked)."""
    problems: list[str] = []
    artifacts_checked = 0

    for path in sorted(results_dir.rglob("*.json")):
        file_problems = _validate_file(path)
        if file_problems:
            # Only count as "checked" if we actually looked at artifact shape(s).
            raw = _load_json(path)
            if isinstance(raw, dict) and (
                _is_artifact_shape(raw)
                or isinstance(raw.get("artifacts"), list)
                or isinstance(raw.get("runs"), list)
                or isinstance(raw.get("seeds"), list)
            ):
                artifacts_checked += 1
            problems.extend(file_problems)

    return problems, artifacts_checked


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate saved artifact hashes")
    parser.add_argument(
        "--results-dir",
        default=str(DEFAULT_RESULTS_DIR),
        help="Directory to scan for experiment result JSON files",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"NOT RUN — results dir {results_dir} does not exist.")
        sys.exit(2)

    problems, artifacts_checked = audit(results_dir)

    if artifacts_checked == 0:
        print("NOT RUN — no EvaluationArtifact-shaped files found.")
        sys.exit(2)

    if problems:
        print(f"FAIL — {len(problems)} problem(s) across {artifacts_checked} artifact(s):")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)

    print(f"PASS — {artifacts_checked} artifact hash(es) verified intact.")


if __name__ == "__main__":
    main()
