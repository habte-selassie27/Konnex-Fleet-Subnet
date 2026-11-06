"""PoPWScoringEngine — prototype PoPW-inspired evaluation mechanism.

Status: COMPLETE (Phase 7 prototype formula, implemented in Phase 6).
NOT Konnex's official scoring algorithm (BUILD.md §9) — adapt to the real
Konnex SDK scoring rules after Phase 8 research.

Weights are configurable via protocol/powp/weights.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from validator.scoring.components import coordination_score, robustness_score
from validator.scoring.konnex import KonnexWeights, KonnexWorkScore, work_score

_WEIGHTS_PATH = Path(__file__).resolve().parent.parent.parent / "protocol" / "powp" / "weights.yaml"


@dataclass(frozen=True)
class ScoringWeights:
    """Normalized component weights; must sum to 1.0."""

    mission_success: float = 0.40
    safety: float = 0.20
    efficiency: float = 0.15
    energy: float = 0.10
    coordination: float = 0.10
    robustness: float = 0.05

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> ScoringWeights:
        """Load weights from a YAML file. Falls back to defaults on error."""
        path = Path(path) if path else _WEIGHTS_PATH
        try:
            with path.open() as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return cls()
            return cls(
                mission_success=float(data.get("mission_success", 0.40)),
                safety=float(data.get("safety", 0.20)),
                efficiency=float(data.get("efficiency", 0.15)),
                energy=float(data.get("energy", 0.10)),
                coordination=float(data.get("coordination", 0.10)),
                robustness=float(data.get("robustness", 0.05)),
            )
        except (FileNotFoundError, yaml.YAMLError, ValueError):
            return cls()


@dataclass(frozen=True)
class PoPWScore:
    """The six component scores and the weighted final score."""

    mission_success: float
    safety: float
    efficiency: float
    energy: float
    coordination: float
    robustness: float
    final: float
    weights: ScoringWeights
    konnex: KonnexWorkScore | None = None


@dataclass(frozen=True)
class MissionResult:
    """Neutral mission outcome summary consumed by the scoring engine."""

    tasks_completed: int
    tasks_total: int
    elapsed_s: float
    time_limit_s: float
    collision_count: int
    energy_consumed: float
    energy_budget: float
    failure_count: int = 0


class PoPWScoringEngine:
    """Computes the prototype PoPW score from a MissionResult."""

    def __init__(self, weights: ScoringWeights | None = None, use_konnex: bool = False) -> None:
        self._weights = weights or ScoringWeights.from_yaml()
        self._use_konnex = use_konnex

    @property
    def weights(self) -> ScoringWeights:
        """Active scoring weights."""
        return self._weights

    def score(self, result: MissionResult) -> PoPWScore:
        """Score a mission result; every component is clamped to [0, 1]."""
        mission_success = self._ratio(result.tasks_completed, result.tasks_total)
        safety = max(0.0, 1.0 - min(1.0, result.collision_count / 10.0))
        efficiency = (
            max(0.0, 1.0 - (result.elapsed_s / result.time_limit_s))
            if result.time_limit_s > 0
            else 0.0
        )
        energy = (
            max(0.0, 1.0 - (result.energy_consumed / result.energy_budget))
            if result.energy_budget > 0
            else 0.0
        )
        coordination = coordination_score(result.collision_count, result.tasks_total)
        robustness = robustness_score(mission_success, result.failure_count)

        weights = self._weights
        final = 100.0 * (
            weights.mission_success * mission_success
            + weights.safety * safety
            + weights.efficiency * efficiency
            + weights.energy * energy
            + weights.coordination * coordination
            + weights.robustness * robustness
        )
        safety_violations = 1 if result.collision_count > 0 else 0
        konnex = work_score(
            task_match=mission_success,
            efficiency=efficiency,
            evidence_quality=1.0,
            safety_violations=safety_violations,
            weights=KonnexWeights.from_yaml(),
        )
        final_value = round(final, 2)
        if self._use_konnex and konnex is not None:
            final_value = round(konnex.final * 100.0, 2)
        return PoPWScore(
            mission_success=mission_success,
            safety=safety,
            efficiency=efficiency,
            energy=energy,
            coordination=coordination,
            robustness=robustness,
            final=final_value,
            weights=weights,
            konnex=konnex,
        )

    @staticmethod
    def _ratio(part: int, whole: int) -> float:
        if whole <= 0:
            return 0.0
        return min(1.0, max(0.0, part / whole))
