"""Deterministic heuristic belief and EVPI calculations for SAGE questions."""

from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Optional


EPSILON = 1e-4


def parameter_specificity(*, specified: bool, domain_size: Optional[int]) -> float:
    """Return the specified SAGE-style heuristic score for one parameter."""
    if specified:
        return 1.0
    if domain_size is not None and domain_size > 0:
        return 1.0 / domain_size
    return EPSILON


def normalized_beliefs(weights: Mapping[str, float]) -> dict[str, float]:
    """Normalize nonnegative candidate weights; zero-mass input stays empty."""
    safe = {key: max(0.0, float(value)) for key, value in weights.items()}
    total = sum(safe.values())
    if total <= 0:
        return {}
    return {key: value / total for key, value in safe.items()}


def evpi(candidate_beliefs: Mapping[str, float],
         outcomes_by_candidate: Mapping[str, Optional[str]]) -> float:
    """Expected best-candidate confidence gain for a deterministic answer partition.

    Candidate beliefs form a normalized categorical posterior approximation. A
    response partitions candidates by answer outcome, and Bayes conditioning is
    exact for that partition. The result is a heuristic, not user-intent
    calibration.
    """
    beliefs = normalized_beliefs(candidate_beliefs)
    if not beliefs:
        return 0.0
    current_best = max(beliefs.values())
    partitions: dict[str, float] = defaultdict(float)
    for candidate, probability in beliefs.items():
        outcome = outcomes_by_candidate.get(candidate)
        partitions[str(outcome)] += probability
    expected_best = 0.0
    for outcome, probability in partitions.items():
        if probability <= 0:
            continue
        best_after = max(
            (mass / probability for candidate, mass in beliefs.items()
             if str(outcomes_by_candidate.get(candidate)) == outcome),
            default=0.0,
        )
        expected_best += probability * best_after
    return max(0.0, expected_best - current_best)


def question_score(candidate_beliefs: Mapping[str, float],
                   outcomes_by_candidate: Mapping[str, Optional[str]],
                   *, redundancy_count: int, redundancy_lambda: float) -> tuple[float, float]:
    """Return (EVPI, EVPI minus configurable repeated-aspect cost)."""
    value = evpi(candidate_beliefs, outcomes_by_candidate)
    return value, value - max(0, redundancy_count) * max(0.0, redundancy_lambda)
