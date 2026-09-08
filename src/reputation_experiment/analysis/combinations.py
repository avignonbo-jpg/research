"""Offline combination experiments — EXPERIMENT_PLAN.md §20-22.

Deliberately starts with deterministic offline rules (UNION/INTERSECTION/
MAJORITY) rather than a learned fusion model. Per the reviewer notes on
Combination policy:

  - Failures (UNAVAILABLE/ERROR) and UNKNOWN contribute NO vote — a missing
    provider must never make an intersection look artificially clean, and
    must never be silently treated as a "not malicious" vote in a majority.
  - If too few providers actually responded for a combination rule to be
    meaningful, the result is INDETERMINATE, not "legitimate by default".
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from reputation_experiment.domain.classifications import is_failure, is_malicious
from reputation_experiment.domain.classifications import NormalizedClassification
from reputation_experiment.domain.models import NormalizedObservation


class CombinationVerdict(str, Enum):
    MALICIOUS = "MALICIOUS"
    LEGITIMATE = "LEGITIMATE"
    INDETERMINATE = "INDETERMINATE"


class CombinationRule(str, Enum):
    UNION = "UNION"
    INTERSECTION = "INTERSECTION"
    MAJORITY = "MAJORITY"


@dataclass(frozen=True)
class CombinationResult:
    case_id: str
    rule: CombinationRule
    verdict: CombinationVerdict
    responding_providers: tuple[str, ...]
    malicious_votes: int
    legitimate_votes: int


def _votes_for_case(
    case_id: str, providers: list[str], observations_by_provider_case: dict[tuple[str, str], NormalizedObservation]
) -> tuple[dict[str, bool], tuple[str, ...]]:
    """Returns (provider -> is_malicious_vote, responding_providers).
    Providers whose observation is a failure or UNKNOWN are excluded
    entirely — they contribute no vote in either direction.
    """
    votes: dict[str, bool] = {}
    responding: list[str] = []

    for provider in providers:
        obs = observations_by_provider_case.get((provider, case_id))
        if obs is None:
            continue
        if is_failure(obs.normalized_classification):
            continue
        if obs.normalized_classification == NormalizedClassification.UNKNOWN:
            continue
        votes[provider] = is_malicious(obs.normalized_classification)
        responding.append(provider)

    return votes, tuple(responding)


def combine_union(
    case_id: str, providers: list[str], observations_by_provider_case: dict[tuple[str, str], NormalizedObservation]
) -> CombinationResult:
    votes, responding = _votes_for_case(case_id, providers, observations_by_provider_case)
    if not responding:
        return CombinationResult(case_id, CombinationRule.UNION, CombinationVerdict.INDETERMINATE, responding, 0, 0)

    malicious_votes = sum(1 for v in votes.values() if v)
    verdict = CombinationVerdict.MALICIOUS if malicious_votes > 0 else CombinationVerdict.LEGITIMATE
    return CombinationResult(case_id, CombinationRule.UNION, verdict, responding, malicious_votes, len(votes) - malicious_votes)


def combine_intersection(
    case_id: str,
    providers: list[str],
    observations_by_provider_case: dict[tuple[str, str], NormalizedObservation],
    *,
    required_providers: Optional[list[str]] = None,
) -> CombinationResult:
    """MALICIOUS only if every required provider (default: every provider
    passed in) that actually responded voted malicious AND at least the
    minimum required set of providers responded. Per the reviewer note: a
    provider that failed to respond must not make the intersection appear
    cleaner by being silently excluded from the requirement — if a required
    provider didn't respond at all, the case is INDETERMINATE rather than
    evaluated on a shrunken provider set.
    """
    required = required_providers or providers
    votes, responding = _votes_for_case(case_id, providers, observations_by_provider_case)

    missing_required = [p for p in required if p not in votes]
    if missing_required:
        return CombinationResult(
            case_id, CombinationRule.INTERSECTION, CombinationVerdict.INDETERMINATE, responding, 0, 0
        )

    malicious_votes = sum(1 for p in required if votes[p])
    verdict = (
        CombinationVerdict.MALICIOUS if malicious_votes == len(required) else CombinationVerdict.LEGITIMATE
    )
    return CombinationResult(
        case_id, CombinationRule.INTERSECTION, verdict, responding, malicious_votes, len(required) - malicious_votes
    )


def combine_majority(
    case_id: str,
    providers: list[str],
    observations_by_provider_case: dict[tuple[str, str], NormalizedObservation],
    *,
    min_responding: int = 2,
) -> CombinationResult:
    """MALICIOUS if malicious_votes > legitimate_votes among responding
    providers, but only if at least min_responding providers actually
    responded — a "majority" of one responding provider isn't a majority.
    """
    votes, responding = _votes_for_case(case_id, providers, observations_by_provider_case)

    if len(responding) < min_responding:
        return CombinationResult(
            case_id, CombinationRule.MAJORITY, CombinationVerdict.INDETERMINATE, responding, 0, 0
        )

    malicious_votes = sum(1 for v in votes.values() if v)
    legitimate_votes = len(votes) - malicious_votes

    if malicious_votes > legitimate_votes:
        verdict = CombinationVerdict.MALICIOUS
    elif legitimate_votes > malicious_votes:
        verdict = CombinationVerdict.LEGITIMATE
    else:
        verdict = CombinationVerdict.INDETERMINATE  # tie

    return CombinationResult(case_id, CombinationRule.MAJORITY, verdict, responding, malicious_votes, legitimate_votes)


def index_observations_by_provider_case(
    observations: list[NormalizedObservation],
) -> dict[tuple[str, str], NormalizedObservation]:
    """Builds the (provider, case_id) -> observation index the combine_*
    functions expect. Centralized here so callers don't each re-derive it
    slightly differently.
    """
    return {(obs.provider, obs.case_id): obs for obs in observations}
