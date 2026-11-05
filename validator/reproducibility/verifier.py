"""Reproducibility verifier.

Verifies that independent validators produce scores within the configured
tolerance (±0.5 by default) for the same (policy_hash, scenario_id, seed,
env_version). Larger divergence flags the evaluation as UNSTABLE.

Status: COMPLETE (Phase 6).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from validator.consensus import CONSENSUS_TOLERANCE
from validator.runner import ValidationRequest, ValidationResult, ValidatorRunner


@dataclass(frozen=True)
class ReproducibilityResult:
    """Outcome of a reproducibility check across independent validators."""

    request: ValidationRequest
    scores: list[float]
    spread: float
    agreed: bool
    tolerance: float
    validator_count: int

    @property
    def status(self) -> str:
        return "REPRODUCIBLE" if self.agreed else "UNSTABLE"


class ReproducibilityVerifier:
    """Runs a validation request through N independent validators and checks
    that their scores agree within ``tolerance``.

    Usage:
        verifier = ReproducibilityVerifier([runner_a, runner_b])
        result = verifier.verify(request)
        assert result.agreed
    """

    def __init__(
        self,
        runners: Sequence[ValidatorRunner],
        tolerance: float = CONSENSUS_TOLERANCE,
    ) -> None:
        if len(runners) < 2:
            raise ValueError("Reproducibility verification requires at least 2 validators")
        self._runners = list(runners)
        self._tolerance = tolerance

    def verify(self, request: ValidationRequest) -> ReproducibilityResult:
        """Execute the request on every validator and check score agreement."""
        results: list[ValidationResult] = [r.validate(request) for r in self._runners]
        scores = [res.score.final for res in results if res.status == "COMPLETE"]

        if len(scores) < 2:
            # Not enough successful runs to claim reproducibility.
            spread = 0.0
            agreed = False
        else:
            spread = max(scores) - min(scores)
            agreed = spread <= self._tolerance

        return ReproducibilityResult(
            request=request,
            scores=scores,
            spread=spread,
            agreed=agreed,
            tolerance=self._tolerance,
            validator_count=len(self._runners),
        )
