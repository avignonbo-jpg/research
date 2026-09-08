from reputation_experiment.analysis.combinations import (
    CombinationVerdict,
    combine_intersection,
    combine_majority,
    combine_union,
    index_observations_by_provider_case,
)
from reputation_experiment.domain.classifications import NormalizedClassification
from reputation_experiment.domain.normalization import build_observation


def _obs(case_id: str, provider: str, classification: NormalizedClassification):
    return build_observation(
        case_id=case_id,
        phone_number_token="t" * 32,
        provider=provider,
        normalized_classification=classification,
    )


def test_union_malicious_if_any_provider_says_malicious():
    observations = [
        _obs("C1", "A", NormalizedClassification.LEGITIMATE),
        _obs("C1", "B", NormalizedClassification.SPAM),
    ]
    index = index_observations_by_provider_case(observations)
    result = combine_union("C1", ["A", "B"], index)
    assert result.verdict == CombinationVerdict.MALICIOUS


def test_union_legitimate_if_none_say_malicious():
    observations = [
        _obs("C1", "A", NormalizedClassification.LEGITIMATE),
        _obs("C1", "B", NormalizedClassification.LEGITIMATE),
    ]
    index = index_observations_by_provider_case(observations)
    result = combine_union("C1", ["A", "B"], index)
    assert result.verdict == CombinationVerdict.LEGITIMATE


def test_union_indeterminate_if_no_provider_responded():
    observations = [
        _obs("C1", "A", NormalizedClassification.UNAVAILABLE),
        _obs("C1", "B", NormalizedClassification.UNKNOWN),
    ]
    index = index_observations_by_provider_case(observations)
    result = combine_union("C1", ["A", "B"], index)
    assert result.verdict == CombinationVerdict.INDETERMINATE
    assert result.responding_providers == ()


def test_intersection_requires_all_required_providers_to_agree():
    observations = [
        _obs("C1", "A", NormalizedClassification.SPAM),
        _obs("C1", "B", NormalizedClassification.SPAM),
    ]
    index = index_observations_by_provider_case(observations)
    result = combine_intersection("C1", ["A", "B"], index)
    assert result.verdict == CombinationVerdict.MALICIOUS


def test_intersection_indeterminate_not_legitimate_when_required_provider_missing():
    """This is the critical anti-loophole test: a missing required provider
    must not make the intersection look artificially clean.
    """
    observations = [
        _obs("C1", "A", NormalizedClassification.SPAM),
        # B never responded at all.
    ]
    index = index_observations_by_provider_case(observations)
    result = combine_intersection("C1", ["A", "B"], index)
    assert result.verdict == CombinationVerdict.INDETERMINATE


def test_intersection_indeterminate_when_required_provider_failed():
    observations = [
        _obs("C1", "A", NormalizedClassification.SPAM),
        _obs("C1", "B", NormalizedClassification.UNAVAILABLE),
    ]
    index = index_observations_by_provider_case(observations)
    result = combine_intersection("C1", ["A", "B"], index)
    assert result.verdict == CombinationVerdict.INDETERMINATE


def test_intersection_legitimate_when_all_required_respond_and_disagree():
    observations = [
        _obs("C1", "A", NormalizedClassification.SPAM),
        _obs("C1", "B", NormalizedClassification.LEGITIMATE),
    ]
    index = index_observations_by_provider_case(observations)
    result = combine_intersection("C1", ["A", "B"], index)
    assert result.verdict == CombinationVerdict.LEGITIMATE


def test_majority_requires_minimum_responders():
    observations = [_obs("C1", "A", NormalizedClassification.SPAM)]
    index = index_observations_by_provider_case(observations)
    result = combine_majority("C1", ["A", "B", "C"], index, min_responding=2)
    assert result.verdict == CombinationVerdict.INDETERMINATE


def test_majority_ties_are_indeterminate_not_legitimate():
    observations = [
        _obs("C1", "A", NormalizedClassification.SPAM),
        _obs("C1", "B", NormalizedClassification.LEGITIMATE),
    ]
    index = index_observations_by_provider_case(observations)
    result = combine_majority("C1", ["A", "B"], index, min_responding=2)
    assert result.verdict == CombinationVerdict.INDETERMINATE


def test_majority_correctly_outvotes():
    observations = [
        _obs("C1", "A", NormalizedClassification.SPAM),
        _obs("C1", "B", NormalizedClassification.SCAM),
        _obs("C1", "C", NormalizedClassification.LEGITIMATE),
    ]
    index = index_observations_by_provider_case(observations)
    result = combine_majority("C1", ["A", "B", "C"], index, min_responding=2)
    assert result.verdict == CombinationVerdict.MALICIOUS
    assert result.malicious_votes == 2
    assert result.legitimate_votes == 1
