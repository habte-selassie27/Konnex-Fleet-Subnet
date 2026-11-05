"""Konnex-aligned work measurement (estimate) — PoPW-style scoring.

Konnex docs (https://docs.konnex.world) describe the score as a safety gate
multiplied by weighted task-match, efficiency and evidence quality:

    gate(safety) = 0 if any hard violation (collision, torque limit), else 1
    Score        = gate(safety) × (w1·task_match + w2·efficiency + w3·evidence_quality)
    efficiency   = 0.5·(t_ref / t_actual) + 0.5·(E_ref / E_actual)   # capped at 1

Konnex does not publish the per-subnet weight vector or the payout curve, so
the defaults here are *our estimate* (w1=0.50, w2=0.30, w3=0.20), configurable
via the `konnex:` block in protocol/powp/weights.yaml. Rewards are split
competitively (Score_i / Σ Score_j) or winner-takes-most.

Status: COMPLETE (estimate; not Konnex's official formula).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

_WEIGHTS_PATH = Path(__file__).resolve().parent.parent.parent / "protocol" / "powp" / "weights.yaml"

# Konnex does not publish its payout curve; this is the share the top policy
# receives under the winner-takes-most variant described in the docs.
DEFAULT_TOP_SHARE = 0.75


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True)
class KonnexWeights:
    """Per-subnet weight vector for the Konnex work score (must sum to 1)."""

    task_match: float = 0.50
    efficiency: float = 0.30
    evidence_quality: float = 0.20

    def normalized(self) -> KonnexWeights:
        """Return a copy whose weights sum to 1.0 (defaults if all zero)."""
        total = self.task_match + self.efficiency + self.evidence_quality
        if total <= 0:
            return KonnexWeights()
        return KonnexWeights(
            task_match=self.task_match / total,
            efficiency=self.efficiency / total,
            evidence_quality=self.evidence_quality / total,
        )

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> KonnexWeights:
        """Load the `konnex:` block from weights.yaml; defaults on any error."""
        path = Path(path) if path else _WEIGHTS_PATH
        try:
            with path.open() as handle:
                data = yaml.safe_load(handle)
            block = data.get("konnex") if isinstance(data, dict) else None
            if not isinstance(block, dict):
                return cls()
            return cls(
                task_match=float(block.get("task_match", 0.50)),
                efficiency=float(block.get("efficiency", 0.30)),
                evidence_quality=float(block.get("evidence_quality", 0.20)),
            ).normalized()
        except (FileNotFoundError, yaml.YAMLError, ValueError, TypeError):
            return cls()


@dataclass(frozen=True)
class KonnexWorkScore:
    """The gated Konnex work score and the components behind it."""

    safety_gate: int
    safety_violations: int
    task_match: float
    efficiency: float
    evidence_quality: float
    final: float
    weights: KonnexWeights


def reference_efficiency(
    t_ref: float,
    t_actual: float,
    e_ref: float,
    e_actual: float,
) -> float:
    """Konnex efficiency: mean of time and energy reference ratios, capped at 1.

    References are the best known/expected time and energy for the task. A
    non-positive measurement yields 0.0 for that half rather than inventing a
    ratio (Law 1).
    """
    time_ratio = _clamp01(t_ref / t_actual) if t_actual > 0 and t_ref > 0 else 0.0
    energy_ratio = _clamp01(e_ref / e_actual) if e_actual > 0 and e_ref > 0 else 0.0
    return 0.5 * time_ratio + 0.5 * energy_ratio


def work_score(
    *,
    task_match: float,
    efficiency: float,
    evidence_quality: float = 1.0,
    safety_violations: int = 0,
    weights: KonnexWeights | None = None,
) -> KonnexWorkScore:
    """Score one robot-work result with the Konnex gate × weighted-sum model.

    `safety_violations` is a hard gate: any hard violation (collision, torque
    limit) makes the whole score 0, because the docs treat unsafe work as
    disqualifying rather than merely penalized.
    """
    active = (weights or KonnexWeights.from_yaml()).normalized()
    task_match = _clamp01(task_match)
    efficiency = _clamp01(efficiency)
    evidence_quality = _clamp01(evidence_quality)
    gate = 0 if safety_violations > 0 else 1
    weighted = (
        active.task_match * task_match
        + active.efficiency * efficiency
        + active.evidence_quality * evidence_quality
    )
    return KonnexWorkScore(
        safety_gate=gate,
        safety_violations=max(0, safety_violations),
        task_match=task_match,
        efficiency=efficiency,
        evidence_quality=evidence_quality,
        final=_clamp01(gate * weighted),
        weights=active,
    )


def competitive_split(scores: Sequence[float], task_reward: float) -> list[float]:
    """Split a task reward proportionally to scores (Score_i / Σ Score_j).

    All-zero (or negative) scores earn nothing — no reward is fabricated when
    no verified work exists.
    """
    if task_reward < 0:
        raise ValueError("task_reward must be non-negative")
    cleaned = [max(0.0, float(score)) for score in scores]
    total = sum(cleaned)
    if total <= 0:
        return [0.0 for _ in cleaned]
    return [task_reward * score / total for score in cleaned]


def winner_takes_most(
    scores: Sequence[float],
    task_reward: float,
    top_share: float = DEFAULT_TOP_SHARE,
) -> list[float]:
    """Give the top score `top_share` of the reward; split the rest by score.

    The Konnex whitepaper says only the winning policy is deployed, so the
    payout curve is winner-biased. Any remainder that cannot be attributed
    (all other scores zero) stays unallocated rather than being invented.
    """
    if task_reward < 0:
        raise ValueError("task_reward must be non-negative")
    if not 0.0 < top_share <= 1.0:
        raise ValueError("top_share must be in (0, 1]")
    cleaned = [max(0.0, float(score)) for score in scores]
    if not cleaned or sum(cleaned) <= 0:
        return [0.0 for _ in cleaned]
    winner = max(range(len(cleaned)), key=cleaned.__getitem__)
    rewards = [0.0 for _ in cleaned]
    rewards[winner] = task_reward * top_share
    rest_total = sum(score for index, score in enumerate(cleaned) if index != winner)
    if rest_total > 0:
        remainder = task_reward * (1.0 - top_share)
        for index, score in enumerate(cleaned):
            if index != winner:
                rewards[index] = remainder * score / rest_total
    return rewards
