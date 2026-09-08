"""Provider agreement analysis — EXPERIMENT_PLAN.md §19.

Determines whether providers give independent information or largely
duplicate one another, via pairwise agreement/disagreement rates and
detected-by-A/missed-by-B breakdowns.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from reputation_experiment.domain.classifications import is_failure, is_malicious
from reputation_experiment.domain.models import NormalizedObservation


@dataclass(frozen=True)
class PairwiseAgreement:
    provider_a: str
    provider_b: str
    comparable_cases: int          # both providers answered (non-failure)
    agreement_rate: float
    disagreement_rate: float
    malicious_only_overlap: int    # both said malicious
    legitimate_only_overlap: int   # both said legitimate
    detected_by_a_missed_by_b: int
    detected_by_b_missed_by_a: int


def _malicious_calls_by_provider(
    observations: list[NormalizedObservation],
) -> dict[str, dict[str, bool]]:
    """provider -> {case_id -> is_malicious_call}, excluding failures."""
    result: dict[str, dict[str, bool]] = {}
    for obs in observations:
        if is_failure(obs.normalized_classification):
            continue
        result.setdefault(obs.provider, {})[obs.case_id] = is_malicious(obs.normalized_classification)
    return result


def pairwise_agreement(
    provider_a: str, provider_b: str, observations: list[NormalizedObservation]
) -> PairwiseAgreement:
    by_provider = _malicious_calls_by_provider(observations)
    calls_a = by_provider.get(provider_a, {})
    calls_b = by_provider.get(provider_b, {})

    shared_case_ids = set(calls_a) & set(calls_b)
    comparable = len(shared_case_ids)

    agree = 0
    malicious_overlap = 0
    legitimate_overlap = 0
    a_only = 0
    b_only = 0

    for case_id in shared_case_ids:
        a_malicious = calls_a[case_id]
        b_malicious = calls_b[case_id]
        if a_malicious == b_malicious:
            agree += 1
            if a_malicious:
                malicious_overlap += 1
            else:
                legitimate_overlap += 1
        elif a_malicious and not b_malicious:
            a_only += 1
        elif b_malicious and not a_malicious:
            b_only += 1

    agreement_rate = agree / comparable if comparable else float("nan")
    disagreement_rate = 1 - agreement_rate if comparable else float("nan")

    return PairwiseAgreement(
        provider_a=provider_a,
        provider_b=provider_b,
        comparable_cases=comparable,
        agreement_rate=agreement_rate,
        disagreement_rate=disagreement_rate,
        malicious_only_overlap=malicious_overlap,
        legitimate_only_overlap=legitimate_overlap,
        detected_by_a_missed_by_b=a_only,
        detected_by_b_missed_by_a=b_only,
    )


def agreement_matrix(
    providers: list[str], observations: list[NormalizedObservation]
) -> list[PairwiseAgreement]:
    """All pairwise combinations, per §19's example matrix."""
    return [
        pairwise_agreement(a, b, observations)
        for a, b in combinations(sorted(set(providers)), 2)
    ]
