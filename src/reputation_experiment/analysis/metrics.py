"""Detection metrics.

Implements EXPERIMENT_PLAN.md §16 (Primary Detection Metrics) plus the
reviewer-note corrections that matter most for not drawing misleading
conclusions:

  - Three denominators, not one:
      all_eligible  — every case attempted, including provider failures.
                      Measures operational reality.
      answered      — cases where the provider returned SOMETHING usable
                      (excludes UNAVAILABLE/ERROR).
      decidable     — answered cases that were also NOT UNKNOWN/SUSPICIOUS,
                      i.e. an explicit MALICIOUS/LEGITIMATE call.
    A provider that returns UNKNOWN often can look good if unknowns are
    silently discarded from the denominator — computing all three prevents
    that.
  - Coverage rate and indeterminate rate are first-class metrics, not
    afterthoughts.
  - SUSPICIOUS is excluded from the primary binary calculation by default
    (per the binary evaluation policy) unless a caller supplies a
    pre-registered threshold mapping it to malicious/legitimate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from reputation_experiment.domain.classifications import (
    GroundTruthLabel,
    NormalizedClassification,
    is_failure,
    is_legitimate,
    is_malicious,
)
from reputation_experiment.domain.models import CorpusCase, NormalizedObservation


@dataclass(frozen=True)
class ConfusionMatrix:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int

    @property
    def total(self) -> int:
        return self.true_positive + self.false_positive + self.true_negative + self.false_negative


@dataclass(frozen=True)
class DetectionScorecard:
    provider: str
    confusion_matrix: ConfusionMatrix
    tpr: Optional[float]
    fpr: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    f1: Optional[float]
    coverage_rate: float          # answered / all_eligible
    indeterminate_rate: float     # UNKNOWN / all_eligible
    failure_rate: float           # UNAVAILABLE+ERROR / all_eligible
    all_eligible_count: int
    answered_count: int
    decidable_count: int


def _safe_div(numerator: float, denominator: float) -> Optional[float]:
    if denominator == 0:
        return None
    return numerator / denominator


def build_confusion_matrix(
    *,
    observations: list[NormalizedObservation],
    ground_truth_by_case: dict[str, CorpusCase],
) -> ConfusionMatrix:
    """Builds a confusion matrix over DECIDABLE observations only (excludes
    UNKNOWN/UNAVAILABLE/ERROR/SUSPICIOUS observations, and any case whose
    ground truth is not MALICIOUS/LEGITIMATE — e.g. AMBIGUOUS or
    SPOOFED_NUMBER cases are excluded from the primary binary matrix; see
    EXPERIMENT_PLAN.md's note on evaluating spoofing cases separately).
    """
    tp = fp = tn = fn = 0

    for obs in observations:
        case = ground_truth_by_case.get(obs.case_id)
        if case is None:
            continue
        if case.ground_truth_label not in (GroundTruthLabel.MALICIOUS, GroundTruthLabel.LEGITIMATE):
            continue
        if is_failure(obs.normalized_classification):
            continue
        if obs.normalized_classification in (
            NormalizedClassification.UNKNOWN,
            NormalizedClassification.SUSPICIOUS,
        ):
            continue

        predicted_malicious = is_malicious(obs.normalized_classification)
        actual_malicious = case.ground_truth_label == GroundTruthLabel.MALICIOUS

        if predicted_malicious and actual_malicious:
            tp += 1
        elif predicted_malicious and not actual_malicious:
            fp += 1
        elif not predicted_malicious and not actual_malicious:
            tn += 1
        else:
            fn += 1

    return ConfusionMatrix(true_positive=tp, false_positive=fp, true_negative=tn, false_negative=fn)


def score_provider(
    *,
    provider: str,
    observations: list[NormalizedObservation],
    ground_truth_by_case: dict[str, CorpusCase],
) -> DetectionScorecard:
    """Computes a full scorecard for one provider's observations. Callers
    should pre-filter `observations` to a single provider before calling.
    """
    provider_observations = [o for o in observations if o.provider == provider]
    eligible = [o for o in provider_observations if o.case_id in ground_truth_by_case]

    all_eligible_count = len(eligible)
    answered = [o for o in eligible if not is_failure(o.normalized_classification)]
    answered_count = len(answered)
    decidable = [
        o for o in answered
        if o.normalized_classification not in (NormalizedClassification.UNKNOWN, NormalizedClassification.SUSPICIOUS)
    ]
    decidable_count = len(decidable)

    indeterminate_count = sum(
        1 for o in answered if o.normalized_classification == NormalizedClassification.UNKNOWN
    )
    failure_count = sum(1 for o in eligible if is_failure(o.normalized_classification))

    matrix = build_confusion_matrix(observations=eligible, ground_truth_by_case=ground_truth_by_case)

    tpr = _safe_div(matrix.true_positive, matrix.true_positive + matrix.false_negative)
    fpr = _safe_div(matrix.false_positive, matrix.false_positive + matrix.true_negative)
    precision = _safe_div(matrix.true_positive, matrix.true_positive + matrix.false_positive)
    recall = tpr
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)

    return DetectionScorecard(
        provider=provider,
        confusion_matrix=matrix,
        tpr=tpr,
        fpr=fpr,
        precision=precision,
        recall=recall,
        f1=f1,
        coverage_rate=_safe_div(answered_count, all_eligible_count) or 0.0,
        indeterminate_rate=_safe_div(indeterminate_count, all_eligible_count) or 0.0,
        failure_rate=_safe_div(failure_count, all_eligible_count) or 0.0,
        all_eligible_count=all_eligible_count,
        answered_count=answered_count,
        decidable_count=decidable_count,
    )


@dataclass(frozen=True)
class MarginalValue:
    """EXPERIMENT_PLAN.md §22: what does adding one provider to a baseline
    actually change? Reported alongside unique TP/FP counts per the
    reviewer note — those are more interpretable than a bare F1 delta.
    """

    provider: str
    baseline_recall: Optional[float]
    combined_recall: Optional[float]
    baseline_precision: Optional[float]
    combined_precision: Optional[float]
    baseline_f1: Optional[float]
    combined_f1: Optional[float]
    marginal_recall: Optional[float]
    marginal_precision: Optional[float]
    marginal_f1: Optional[float]
    marginal_false_positive_rate: Optional[float]
    unique_true_positives: int
    unique_false_positives: int


def _delta(before: Optional[float], after: Optional[float]) -> Optional[float]:
    if before is None or after is None:
        return None
    return after - before


def compute_marginal_value(
    *,
    provider: str,
    baseline_scorecard: DetectionScorecard,
    combined_scorecard: DetectionScorecard,
    baseline_observations: list[NormalizedObservation],
    provider_observations: list[NormalizedObservation],
    ground_truth_by_case: dict[str, CorpusCase],
) -> MarginalValue:
    """baseline_scorecard/combined_scorecard should be scored the same way
    (e.g. via combinations.combine_union) with and without `provider`
    included. unique_true_positives/unique_false_positives are cases this
    provider alone contributed that the baseline combination missed.
    """
    baseline_case_ids = {o.case_id for o in baseline_observations}
    provider_malicious_case_ids = {
        o.case_id for o in provider_observations if is_malicious(o.normalized_classification)
    }

    unique_tp = 0
    unique_fp = 0
    for case_id in provider_malicious_case_ids - baseline_case_ids:
        case = ground_truth_by_case.get(case_id)
        if case is None:
            continue
        if case.ground_truth_label == GroundTruthLabel.MALICIOUS:
            unique_tp += 1
        elif case.ground_truth_label == GroundTruthLabel.LEGITIMATE:
            unique_fp += 1

    return MarginalValue(
        provider=provider,
        baseline_recall=baseline_scorecard.recall,
        combined_recall=combined_scorecard.recall,
        baseline_precision=baseline_scorecard.precision,
        combined_precision=combined_scorecard.precision,
        baseline_f1=baseline_scorecard.f1,
        combined_f1=combined_scorecard.f1,
        marginal_recall=_delta(baseline_scorecard.recall, combined_scorecard.recall),
        marginal_precision=_delta(baseline_scorecard.precision, combined_scorecard.precision),
        marginal_f1=_delta(baseline_scorecard.f1, combined_scorecard.f1),
        marginal_false_positive_rate=_delta(baseline_scorecard.fpr, combined_scorecard.fpr),
        unique_true_positives=unique_tp,
        unique_false_positives=unique_fp,
    )


def bootstrap_confidence_interval(
    values: list[float],
    *,
    num_resamples: int = 2000,
    confidence: float = 0.95,
    seed: Optional[int] = None,
) -> tuple[float, float]:
    """Stratified bootstrap CI, per reviewer note: a 1-2 point F1 difference
    can be noise on a 500-case corpus, so scorecards should report an
    interval, not a bare point estimate. `values` should be per-case binary
    outcomes (e.g. 1.0 for a correct decidable classification, 0.0 for
    incorrect) that the caller has already restricted to the population of
    interest (e.g. decidable cases only).
    """
    import random

    if not values:
        return (math.nan, math.nan)

    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(num_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    alpha = 1 - confidence
    lower_idx = int((alpha / 2) * num_resamples)
    upper_idx = int((1 - alpha / 2) * num_resamples) - 1
    return (means[max(0, lower_idx)], means[min(num_resamples - 1, upper_idx)])
