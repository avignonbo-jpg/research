from reputation_experiment.analysis.agreement import agreement_matrix, pairwise_agreement
from reputation_experiment.domain.classifications import NormalizedClassification
from reputation_experiment.domain.normalization import build_observation


def _obs(case_id: str, provider: str, classification: NormalizedClassification):
    return build_observation(
        case_id=case_id,
        phone_number_token="t" * 32,
        provider=provider,
        normalized_classification=classification,
    )


def test_full_agreement_between_identical_providers():
    observations = [
        _obs("C1", "A", NormalizedClassification.SPAM),
        _obs("C1", "B", NormalizedClassification.SPAM),
        _obs("C2", "A", NormalizedClassification.LEGITIMATE),
        _obs("C2", "B", NormalizedClassification.LEGITIMATE),
    ]
    result = pairwise_agreement("A", "B", observations)
    assert result.comparable_cases == 2
    assert result.agreement_rate == 1.0
    assert result.malicious_only_overlap == 1
    assert result.legitimate_only_overlap == 1


def test_full_disagreement_between_providers():
    observations = [
        _obs("C1", "A", NormalizedClassification.SPAM),
        _obs("C1", "B", NormalizedClassification.LEGITIMATE),
    ]
    result = pairwise_agreement("A", "B", observations)
    assert result.agreement_rate == 0.0
    assert result.detected_by_a_missed_by_b == 1
    assert result.detected_by_b_missed_by_a == 0


def test_failures_excluded_from_comparable_cases():
    """A failed observation must not be treated as an implicit LEGITIMATE
    vote when computing agreement — it should simply not count as a
    comparable case for that pair.
    """
    observations = [
        _obs("C1", "A", NormalizedClassification.SPAM),
        _obs("C1", "B", NormalizedClassification.UNAVAILABLE),
    ]
    result = pairwise_agreement("A", "B", observations)
    assert result.comparable_cases == 0


def test_agreement_matrix_covers_all_pairs():
    observations = [
        _obs("C1", "A", NormalizedClassification.SPAM),
        _obs("C1", "B", NormalizedClassification.SPAM),
        _obs("C1", "C", NormalizedClassification.LEGITIMATE),
    ]
    matrix = agreement_matrix(["A", "B", "C"], observations)
    pairs = {(m.provider_a, m.provider_b) for m in matrix}
    assert pairs == {("A", "B"), ("A", "C"), ("B", "C")}
