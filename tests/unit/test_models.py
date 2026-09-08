from datetime import datetime, timezone

import pytest

from reputation_experiment.domain.classifications import NormalizedClassification
from reputation_experiment.domain.models import NormalizedObservation, hmac_phone_token
from reputation_experiment.domain.normalization import build_observation


def test_hmac_phone_token_is_stable_and_keyed():
    secret = b"test-secret"
    token_a = hmac_phone_token("+15555550101", secret)
    token_b = hmac_phone_token("+15555550101", secret)
    assert token_a == token_b

    # Different secret -> different token, proving it's keyed (not a bare
    # hash an attacker could brute-force without the secret).
    other_secret = b"different-secret"
    token_c = hmac_phone_token("+15555550101", other_secret)
    assert token_a != token_c


def test_hmac_phone_token_differs_for_different_numbers():
    secret = b"test-secret"
    assert hmac_phone_token("+15555550101", secret) != hmac_phone_token("+15555550102", secret)


def test_normalized_confidence_out_of_range_rejected():
    with pytest.raises(ValueError):
        build_observation(
            case_id="X",
            phone_number_token="a" * 32,
            provider="TEST",
            normalized_classification=NormalizedClassification.LEGITIMATE,
            normalized_confidence=1.5,
        )


def test_normalized_confidence_none_is_allowed():
    obs = build_observation(
        case_id="X",
        phone_number_token="a" * 32,
        provider="TEST",
        normalized_classification=NormalizedClassification.UNKNOWN,
        normalized_confidence=None,
    )
    assert obs.normalized_confidence is None
