"""Adapter contract tests.

Two things every adapter must satisfy, checked here rather than left to
convention:

  1. Registry consistency — every adapter's PROVIDER_ID appears in
     corpus.validation.CANDIDATE_PROVIDER_IDS (so the ground-truth-protocol
     circular-validation check actually covers it) and PROVIDER_IDs are
     unique across adapters.
  2. Failure honesty — a stub adapter (no live implementation) must raise
     NotImplementedError, never fabricate a NormalizedObservation. A real
     adapter (FTC) must map every provider-side failure mode to the correct
     typed error from domain.errors, never let a bare exception escape and
     never silently produce classification=LEGITIMATE on a failure path.

The FTC cases use a fake requests.Session-shaped object (see FakeSession
below) so this suite has no live network dependency, matching
EXPERIMENT_PLAN.md's decoupling requirement for this repository.
"""
from __future__ import annotations

import pytest

from reputation_experiment.adapters.base import ProviderAdapter
from reputation_experiment.adapters.call_control import CallControlAdapter
from reputation_experiment.adapters.first_orion import FirstOrionAdapter
from reputation_experiment.adapters.ftc import FtcAdapter
from reputation_experiment.adapters.hiya import HiyaAdapter
from reputation_experiment.adapters.ipqs import IpqsAdapter
from reputation_experiment.adapters.nomorobo import NomoroboAdapter
from reputation_experiment.adapters.tns import TnsAdapter
from reputation_experiment.corpus.validation import CANDIDATE_PROVIDER_IDS
from reputation_experiment.domain.classifications import NormalizedClassification
from reputation_experiment.domain.errors import (
    ProviderInvalidResponseError,
    ProviderNetworkError,
    ProviderRateLimitedError,
    ProviderServerError,
    ProviderTimeoutError,
)

ALL_ADAPTER_CLASSES = (
    FtcAdapter,
    HiyaAdapter,
    NomoroboAdapter,
    CallControlAdapter,
    IpqsAdapter,
    FirstOrionAdapter,
    TnsAdapter,
)

STUB_ADAPTER_CLASSES = (
    HiyaAdapter,
    NomoroboAdapter,
    CallControlAdapter,
    IpqsAdapter,
    FirstOrionAdapter,
    TnsAdapter,
)

# Used as a placeholder subject number in tests below: area code 555,
# exchange 555, line 0100 — squarely inside the NXX-555-0100..0199
# NANPA-reserved fictional range, so it can never be a real subscriber
# number and is explicitly exempted by scripts/scan_sensitive_data.py.
_TEST_E164_NUMBER = "+15555550100"


# --- Registry consistency -------------------------------------------------


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTER_CLASSES)
def test_adapter_is_provider_adapter_subclass(adapter_cls):
    assert issubclass(adapter_cls, ProviderAdapter)


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTER_CLASSES)
def test_provider_id_registered_in_candidate_set(adapter_cls):
    assert adapter_cls.PROVIDER_ID in CANDIDATE_PROVIDER_IDS, (
        f"{adapter_cls.__name__}.PROVIDER_ID={adapter_cls.PROVIDER_ID!r} is missing from "
        "corpus.validation.CANDIDATE_PROVIDER_IDS — the circular-validation guard "
        "would silently fail to cover this provider."
    )


def test_all_provider_ids_are_unique():
    ids = [cls.PROVIDER_ID for cls in ALL_ADAPTER_CLASSES]
    assert len(ids) == len(set(ids)), f"duplicate PROVIDER_ID across adapters: {ids}"


def test_candidate_set_has_no_untracked_adapters():
    """Every id in CANDIDATE_PROVIDER_IDS should correspond to a real
    adapter class in this suite — otherwise the set is stale and the
    ground-truth-protocol check is enforcing a provider list that no
    longer matches what actually runs.
    """
    ids = {cls.PROVIDER_ID for cls in ALL_ADAPTER_CLASSES}
    assert ids == CANDIDATE_PROVIDER_IDS


# --- Stub adapters must fail loudly, never fabricate ----------------------


@pytest.mark.parametrize("adapter_cls", STUB_ADAPTER_CLASSES)
def test_stub_adapter_raises_not_implemented(adapter_cls):
    adapter = adapter_cls()
    with pytest.raises(NotImplementedError):
        adapter.query(
            case_id="case-1",
            phone_number_token="token-1",
            phone_number_e164=_TEST_E164_NUMBER,
            timeout_seconds=1.0,
        )


# --- FTC adapter: real error-mapping contract ------------------------------


class _FakeResponse:
    def __init__(self, status_code, json_data=None, raise_on_json=False):
        self.status_code = status_code
        self._json_data = json_data
        self._raise_on_json = raise_on_json

    def json(self):
        if self._raise_on_json:
            raise ValueError("response body is not valid JSON")
        return self._json_data


class _FakeSession:
    """requests.Session-shaped fake — no real network call is made."""

    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    def get(self, url, params=None, timeout=None):
        if self._exc is not None:
            raise self._exc
        return self._response


class _FakeTimeout(Exception):
    """Stands in for requests.exceptions.Timeout without importing requests
    at test-collection time."""


def test_ftc_adapter_reported_number_maps_to_suspicious_not_malicious():
    """A complaint count > 0 must map to SUSPICIOUS, not SPAM/SCAM/FRAUD —
    FTC data is unverified consumer complaint volume, not a confirmed
    disposition (see adapters/ftc.py and docs/GROUND_TRUTH_PROTOCOL.md).
    """
    adapter = FtcAdapter(session=_FakeSession(_FakeResponse(200, {"complaint_count": 3})))
    obs = adapter.query(case_id="c1", phone_number_token="tok", phone_number_e164=_TEST_E164_NUMBER, timeout_seconds=5)
    assert obs.normalized_classification == NormalizedClassification.SUSPICIOUS
    assert obs.normalized_confidence is None  # complaint count is not a confidence scale


def test_ftc_adapter_unreported_number_maps_to_unknown():
    adapter = FtcAdapter(session=_FakeSession(_FakeResponse(200, {"complaint_count": 0})))
    obs = adapter.query(case_id="c2", phone_number_token="tok", phone_number_e164=_TEST_E164_NUMBER, timeout_seconds=5)
    assert obs.normalized_classification == NormalizedClassification.UNKNOWN


@pytest.mark.parametrize(
    "status_code,expected_error",
    [
        (429, ProviderRateLimitedError),
        (500, ProviderServerError),
        (503, ProviderServerError),
        (400, ProviderInvalidResponseError),
        (404, ProviderInvalidResponseError),
    ],
)
def test_ftc_adapter_http_status_error_mapping(status_code, expected_error):
    adapter = FtcAdapter(session=_FakeSession(_FakeResponse(status_code)))
    with pytest.raises(expected_error):
        adapter.query(case_id="c3", phone_number_token="tok", phone_number_e164=_TEST_E164_NUMBER, timeout_seconds=5)


def test_ftc_adapter_non_json_body_raises_invalid_response():
    adapter = FtcAdapter(session=_FakeSession(_FakeResponse(200, raise_on_json=True)))
    with pytest.raises(ProviderInvalidResponseError):
        adapter.query(case_id="c4", phone_number_token="tok", phone_number_e164=_TEST_E164_NUMBER, timeout_seconds=5)


def test_ftc_adapter_timeout_exception_mapped_to_provider_timeout_error():
    adapter = FtcAdapter(session=_FakeSession(exc=_FakeTimeout("request timed out")))
    with pytest.raises(ProviderTimeoutError):
        adapter.query(case_id="c5", phone_number_token="tok", phone_number_e164=_TEST_E164_NUMBER, timeout_seconds=5)


def test_ftc_adapter_generic_exception_mapped_to_provider_network_error():
    adapter = FtcAdapter(session=_FakeSession(exc=ConnectionError("boom")))
    with pytest.raises(ProviderNetworkError):
        adapter.query(case_id="c6", phone_number_token="tok", phone_number_e164=_TEST_E164_NUMBER, timeout_seconds=5)


def test_ftc_adapter_never_returns_malicious_or_legitimate():
    """FTC's own data can only ever justify SUSPICIOUS/UNKNOWN — asserting
    this here means any future edit that "upgrades" a reported number to
    SPAM/SCAM/FRAUD, or a failure path to LEGITIMATE, fails a test instead
    of silently changing the ground-truth-protocol guarantee.
    """
    for complaint_count in (0, 1, 50):
        adapter = FtcAdapter(session=_FakeSession(_FakeResponse(200, {"complaint_count": complaint_count})))
        obs = adapter.query(case_id="c7", phone_number_token="tok", phone_number_e164=_TEST_E164_NUMBER, timeout_seconds=5)
        assert obs.normalized_classification not in (
            NormalizedClassification.SPAM,
            NormalizedClassification.SCAM,
            NormalizedClassification.FRAUD,
            NormalizedClassification.ROBOCALL,
            NormalizedClassification.TELEMARKETING,
            NormalizedClassification.LEGITIMATE,
        )
