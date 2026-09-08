from datetime import datetime, timezone

from reputation_experiment.analysis.metrics import (
    bootstrap_confidence_interval,
    build_confusion_matrix,
    score_provider,
)
from reputation_experiment.domain.classifications import (
    AdjudicationStatus,
    CorpusClass,
    GroundTruthConfidence,
    GroundTruthLabel,
    NormalizedClassification,
)
from reputation_experiment.domain.models import CorpusCase
from reputation_experiment.domain.normalization import build_observation


def _case(case_id: str, label: GroundTruthLabel) -> CorpusCase:
    return CorpusCase(
        case_id=case_id,
        phone_number_token="t" * 32,
        corpus_class=CorpusClass.KNOWN_MALICIOUS if label == GroundTruthLabel.MALICIOUS else CorpusClass.LEGITIMATE_BUSINESS,
        ground_truth_label=label,
        ground_truth_confidence=GroundTruthConfidence.HIGH,
        ground_truth_source="test_fixture",
        ground_truth_observed_at=datetime.now(timezone.utc),
        adjudication_status=AdjudicationStatus.VERIFIED,
    )


def _obs(case_id: str, classification: NormalizedClassification, provider: str = "TESTPROV"):
    return build_observation(
        case_id=case_id,
        phone_number_token="t" * 32,
        provider=provider,
        normalized_classification=classification,
    )


def test_confusion_matrix_basic_counts():
    cases = {
        "TP1": _case("TP1", GroundTruthLabel.MALICIOUS),
        "FN1": _case("FN1", GroundTruthLabel.MALICIOUS),
        "FP1": _case("FP1", GroundTruthLabel.LEGITIMATE),
        "TN1": _case("TN1", GroundTruthLabel.LEGITIMATE),
    }
    observations = [
        _obs("TP1", NormalizedClassification.SPAM),        # correctly caught
        _obs("FN1", NormalizedClassification.LEGITIMATE),   # missed
        _obs("FP1", NormalizedClassification.SCAM),         # false alarm
        _obs("TN1", NormalizedClassification.LEGITIMATE),   # correctly clean
    ]

    matrix = build_confusion_matrix(observations=observations, ground_truth_by_case=cases)
    assert matrix.true_positive == 1
    assert matrix.false_negative == 1
    assert matrix.false_positive == 1
    assert matrix.true_negative == 1


def test_confusion_matrix_excludes_unknown_and_suspicious():
    """UNKNOWN/SUSPICIOUS must not be silently coerced into TN or FN — they
    should be excluded from the binary matrix entirely (reported via
    coverage_rate/indeterminate_rate instead, not folded into accuracy).
    """
    cases = {"C1": _case("C1", GroundTruthLabel.MALICIOUS)}
    observations = [_obs("C1", NormalizedClassification.UNKNOWN)]

    matrix = build_confusion_matrix(observations=observations, ground_truth_by_case=cases)
    assert matrix.total == 0


def test_confusion_matrix_excludes_failures():
    cases = {"C1": _case("C1", GroundTruthLabel.MALICIOUS)}
    observations = [_obs("C1", NormalizedClassification.UNAVAILABLE)]

    matrix = build_confusion_matrix(observations=observations, ground_truth_by_case=cases)
    assert matrix.total == 0


def test_score_provider_three_denominators():
    """A provider that answers everything with UNKNOWN should show 0%
    coverage/decidable rate, not silently vanish from the report by having
    an empty denominator excluded.
    """
    cases = {
        "C1": _case("C1", GroundTruthLabel.MALICIOUS),
        "C2": _case("C2", GroundTruthLabel.LEGITIMATE),
    }
    observations = [
        _obs("C1", NormalizedClassification.UNKNOWN),
        _obs("C2", NormalizedClassification.UNAVAILABLE),
    ]

    scorecard = score_provider(provider="TESTPROV", observations=observations, ground_truth_by_case=cases)
    assert scorecard.all_eligible_count == 2
    assert scorecard.answered_count == 1  # UNKNOWN counts as answered (provider ran), UNAVAILABLE does not
    assert scorecard.decidable_count == 0
    assert scorecard.failure_rate == 0.5
    assert scorecard.indeterminate_rate == 0.5


def test_score_provider_coverage_does_not_hide_low_answer_rate():
    cases = {f"C{i}": _case(f"C{i}", GroundTruthLabel.MALICIOUS) for i in range(10)}
    # Only 2 of 10 answered with a real classification.
    observations = [_obs(f"C{i}", NormalizedClassification.UNAVAILABLE) for i in range(8)]
    observations += [_obs("C8", NormalizedClassification.SPAM), _obs("C9", NormalizedClassification.SPAM)]

    scorecard = score_provider(provider="TESTPROV", observations=observations, ground_truth_by_case=cases)
    assert scorecard.coverage_rate == 0.2
    assert scorecard.failure_rate == 0.8


def test_bootstrap_confidence_interval_bounds_are_sane():
    values = [1.0] * 80 + [0.0] * 20  # 80% accuracy
    lower, upper = bootstrap_confidence_interval(values, num_resamples=500, seed=42)
    assert 0.0 <= lower <= 0.8 <= upper <= 1.0


def test_bootstrap_confidence_interval_empty_input():
    import math

    lower, upper = bootstrap_confidence_interval([])
    assert math.isnan(lower) and math.isnan(upper)
