from reputation_experiment.domain.classifications import (
    NormalizedClassification,
    is_failure,
    is_legitimate,
    is_malicious,
)


def test_unknown_unavailable_error_are_distinct():
    assert NormalizedClassification.UNKNOWN != NormalizedClassification.UNAVAILABLE
    assert NormalizedClassification.UNAVAILABLE != NormalizedClassification.ERROR
    assert NormalizedClassification.UNKNOWN != NormalizedClassification.ERROR


def test_failure_is_never_malicious_or_legitimate():
    """Required invariant, mirrored from Pulse's own CallTier.SECURITY_FAILURE:
    a provider failure must never be indistinguishable from a successful
    clean (LEGITIMATE) result or a successful malicious detection.
    """
    for classification in (NormalizedClassification.UNAVAILABLE, NormalizedClassification.ERROR):
        assert is_failure(classification) is True
        assert is_malicious(classification) is False
        assert is_legitimate(classification) is False


def test_unknown_is_not_a_failure_and_not_legitimate():
    """UNKNOWN means the provider successfully ran and had no opinion — a
    different situation from a failure, and must not be silently treated
    as either malicious or legitimate.
    """
    assert is_failure(NormalizedClassification.UNKNOWN) is False
    assert is_malicious(NormalizedClassification.UNKNOWN) is False
    assert is_legitimate(NormalizedClassification.UNKNOWN) is False


def test_all_malicious_classes_are_malicious():
    for classification in (
        NormalizedClassification.SPAM,
        NormalizedClassification.SCAM,
        NormalizedClassification.FRAUD,
        NormalizedClassification.ROBOCALL,
        NormalizedClassification.TELEMARKETING,
    ):
        assert is_malicious(classification) is True
        assert is_legitimate(classification) is False


def test_suspicious_is_neither_malicious_nor_legitimate_by_default():
    """SUSPICIOUS is reported separately and excluded from the primary
    binary calculation unless a preregistered threshold maps it — it must
    not silently default into either bucket.
    """
    assert is_malicious(NormalizedClassification.SUSPICIOUS) is False
    assert is_legitimate(NormalizedClassification.SUSPICIOUS) is False
