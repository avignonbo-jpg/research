"""Temporal stability analysis — EXPERIMENT_PLAN.md §13, §18.

Measures classification stability, freshness, and propagation delay across
repeated observations of the same (provider, case) pair over time (the
T0/T+1/T+3/T+7/T+14/T+30 sampling schedule). This module only computes
statistics from whatever observations are supplied — scheduling the
repeated runs themselves is an operational concern for the Manual
Experiment Run workflow, not this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from reputation_experiment.domain.models import NormalizedObservation


@dataclass(frozen=True)
class StabilityResult:
    provider: str
    case_id: str
    observation_count: int
    classification_changes: int
    stability_rate: float  # 1 - (changes / (observations - 1)), 1.0 if only one observation


def classification_stability(
    observations: list[NormalizedObservation],
) -> list[StabilityResult]:
    """Groups observations by (provider, case_id) and computes how often
    the normalized classification changed between consecutive observations,
    ordered by observed_at.
    """
    grouped: dict[tuple[str, str], list[NormalizedObservation]] = {}
    for obs in observations:
        grouped.setdefault((obs.provider, obs.case_id), []).append(obs)

    results: list[StabilityResult] = []
    for (provider, case_id), obs_list in grouped.items():
        ordered = sorted(obs_list, key=lambda o: o.observed_at)
        changes = sum(
            1
            for prev, curr in zip(ordered, ordered[1:])
            if prev.normalized_classification != curr.normalized_classification
        )
        denominator = len(ordered) - 1
        stability_rate = 1.0 if denominator <= 0 else 1 - (changes / denominator)
        results.append(
            StabilityResult(
                provider=provider,
                case_id=case_id,
                observation_count=len(ordered),
                classification_changes=changes,
                stability_rate=stability_rate,
            )
        )
    return results


def observation_age_seconds(observation: NormalizedObservation) -> Optional[float]:
    """age = observationTime - providerDataTimestamp, per §18 Freshness.
    Returns None when provider_timestamp is unavailable — this must be
    reported as a distinct "unknown-age percentage", never silently
    excluded or treated as age=0 (age=0 would make an untimestamped
    provider look artificially fresh).
    """
    if observation.provider_timestamp is None:
        return None
    delta = observation.observed_at - observation.provider_timestamp
    return delta.total_seconds()


def freshness_summary(observations: list[NormalizedObservation]) -> dict:
    ages = [a for a in (observation_age_seconds(o) for o in observations) if a is not None]
    unknown_count = sum(1 for o in observations if observation_age_seconds(o) is None)
    total = len(observations)

    ages_sorted = sorted(ages)

    def _percentile(p: float) -> Optional[float]:
        if not ages_sorted:
            return None
        idx = min(len(ages_sorted) - 1, int(p * len(ages_sorted)))
        return ages_sorted[idx]

    return {
        "median_age_seconds": _percentile(0.5),
        "p95_age_seconds": _percentile(0.95),
        "max_age_seconds": ages_sorted[-1] if ages_sorted else None,
        "unknown_age_percentage": (unknown_count / total) if total else None,
    }
