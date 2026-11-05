"""Multi-validator consensus — runs same request through N validators.

Phase 6 stretch goal: multiple independent validators agree on scores.
Two validators running the same (policy_hash, seed, env_version) must
produce scores within ±0.5 points (AGENTS.md §0.6 reproducibility requirement).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

import structlog

from validator.runner import ValidationResult, ValidatorRunner

logger = structlog.get_logger(__name__)

CONSENSUS_TOLERANCE = 0.5  # max allowed score divergence between validators


@dataclass(frozen=True)
class ConsensusRequest:
    """A validation request to be run by multiple validators."""

    policy_id: str
    policy_hash: str
    scenario_id: str
    seed: int
    env_version: str
    sim_version: str


@dataclass
class ValidatorVote:
    """One validator's result on a consensus request."""

    validator_id: str
    result: ValidationResult


@dataclass
class ConsensusResult:
    """Outcome of multi-validator consensus."""

    request: ConsensusRequest
    votes: list[ValidatorVote]
    agreed: bool
    final_score: float
    score_spread: float  # max - min across validators
    validator_count: int
    agreement_count: int  # how many validators agree within tolerance
    complete_count: int = 0  # how many validators produced a usable score

    @property
    def status(self) -> str:
        if self.agreed:
            return "CONSENSUS"
        return "DISPUTE"

    @property
    def rejection_reason(self) -> str | None:
        """Why the result was rejected, or None when validators agreed.

        Two distinct failure modes are reported separately: too few validators
        produced a usable score at all (crash/timeout/dispute), versus usable
        scores that diverge beyond the reproducibility tolerance.
        """
        if self.agreed:
            return None
        if self.complete_count < 2:
            return (
                f"only {self.complete_count} of {self.validator_count} validators "
                "produced a COMPLETE result (need at least 2)"
            )
        return f"score spread {self.score_spread:.3f} exceeds tolerance {CONSENSUS_TOLERANCE:.1f}"

    @property
    def accepted(self) -> bool:
        """True only when the score may be published as a consensus score."""
        return self.agreed


class ConsensusValidator:
    """Runs validation through multiple independent validators and checks agreement.

    Usage:
        cv = ConsensusValidator([runner1, runner2, runner3])
        result = cv.validate(request)
        if result.agreed:
            print(f"All validators agree: {result.final_score:.1f}")
        else:
            print(f"Dispute! Spread: {result.score_spread:.1f}")
    """

    def __init__(
        self,
        runners: list[ValidatorRunner],
        tolerance: float = CONSENSUS_TOLERANCE,
    ) -> None:
        if len(runners) < 2:
            raise ValueError("Consensus requires at least 2 validators")
        self._runners = runners
        self._tolerance = tolerance

    def validate(self, request: ConsensusRequest) -> ConsensusResult:
        """Run the request through all validators and check consensus."""
        from validator.runner import ValidationRequest

        votes: list[ValidatorVote] = []
        for i, runner in enumerate(self._runners):
            val_request = ValidationRequest(
                policy_id=request.policy_id,
                policy_hash=request.policy_hash,
                scenario_id=request.scenario_id,
                seed=request.seed,
                env_version=request.env_version,
                sim_version=request.sim_version,
            )
            result = runner.validate(val_request)
            votes.append(ValidatorVote(validator_id=f"validator_{i}", result=result))

        return self._check_consensus(request, votes)

    def resolve(self, request: ConsensusRequest) -> ValidationResult | None:
        """Run consensus and return the accepted result, or None on dispute.

        Callers must treat None as "do not publish a score": a disputed (or
        under-participating) validator set is a rejection, not a warning.
        """
        result = self.validate(request)
        if not result.accepted:
            logger.warning(
                "consensus_rejected",
                policy=request.policy_id,
                seed=request.seed,
                status=result.status,
                reason=result.rejection_reason,
                scores=[round(v.result.score.final, 2) for v in result.votes],
            )
            return None
        return result.votes[0].result

    def _check_consensus(
        self, request: ConsensusRequest, votes: list[ValidatorVote]
    ) -> ConsensusResult:
        """Determine if validators agree within tolerance."""
        scores = [v.result.score.final for v in votes if v.result.status == "COMPLETE"]

        if len(scores) < 2:
            # Not enough successful runs for consensus
            return ConsensusResult(
                request=request,
                votes=votes,
                agreed=False,
                final_score=scores[0] if scores else 0.0,
                score_spread=0.0,
                validator_count=len(votes),
                agreement_count=len(scores),
                complete_count=len(scores),
            )

        min_score = min(scores)
        max_score = max(scores)
        spread = max_score - min_score
        median_score = statistics.median(scores)

        # Count how many validators agree with the median within tolerance
        agreement_count = sum(1 for s in scores if abs(s - median_score) <= self._tolerance)

        agreed = spread <= self._tolerance

        logger.info(
            "consensus_check",
            policy=request.policy_id,
            seed=request.seed,
            scores=[round(s, 2) for s in scores],
            spread=round(spread, 3),
            median=round(median_score, 2),
            agreed=agreed,
        )

        return ConsensusResult(
            request=request,
            votes=votes,
            agreed=agreed,
            final_score=median_score,
            score_spread=spread,
            validator_count=len(votes),
            agreement_count=agreement_count,
            complete_count=len(scores),
        )


@dataclass
class ConsensusBatch:
    """Batch consensus result across multiple requests."""

    results: list[ConsensusResult]

    @property
    def total_requests(self) -> int:
        return len(self.results)

    @property
    def agreed_count(self) -> int:
        return sum(1 for r in self.results if r.agreed)

    @property
    def agreement_rate(self) -> float:
        return self.agreed_count / max(1, self.total_requests)

    @property
    def mean_spread(self) -> float:
        spreads = [r.score_spread for r in self.results]
        return statistics.mean(spreads) if spreads else 0.0

    def summary(self) -> str:
        lines = [
            f"Consensus Batch: {self.agreed_count}/{self.total_requests} agreed "
            f"({self.agreement_rate:.0%})",
            f"Mean spread: {self.mean_spread:.3f} (tolerance: {CONSENSUS_TOLERANCE})",
            "",
        ]
        for r in self.results:
            status = "✓" if r.agreed else "✗"
            scores = [f"{v.result.score.final:.1f}" for v in r.votes]
            lines.append(
                f"  {status} {r.request.policy_id} seed={r.request.seed} "
                f"scores=[{', '.join(scores)}] spread={r.score_spread:.3f}"
            )
        return "\n".join(lines)
