"""FTC Do Not Call (DNC) Reported Calls adapter.

Public, unauthenticated API. Per EXPERIMENT_PLAN.md and the FTC's own
documentation, this data is consumer-reported and explicitly NOT verified —
treat FTC as an unverified baseline signal, never as ground truth (see
docs/GROUND_TRUTH_PROTOCOL.md; a case must not be labeled MALICIOUS solely
because it appears in FTC data).

IMPORTANT — not verified against a live endpoint in this environment (no
network access at authoring time). The endpoint URL and response field names
below are based on the FTC developer API documentation referenced in
EXPERIMENT_PLAN.md's citation [1] and MUST be confirmed against the live
schema before this adapter is used in a real comparison run — add that
confirmation as a contract test in tests/contract/ using a recorded,
redacted fixture response before flipping this on in a Manual Experiment Run.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from reputation_experiment.adapters.base import ProviderAdapter
from reputation_experiment.domain.classifications import NormalizedClassification
from reputation_experiment.domain.errors import (
    ProviderInvalidResponseError,
    ProviderNetworkError,
    ProviderRateLimitedError,
    ProviderServerError,
    ProviderTimeoutError,
)
from reputation_experiment.domain.models import NormalizedObservation
from reputation_experiment.domain.normalization import ConfidenceInterpretation, build_observation

FTC_DNC_REPORTED_CALLS_ENDPOINT = "https://api.ftc.gov/v0/dnc-complaints"  # TODO: confirm exact path before live use


class FtcAdapter(ProviderAdapter):
    PROVIDER_ID = "FTC"
    CONFIDENCE_INTERPRETATION = ConfidenceInterpretation.UNAVAILABLE  # FTC exposes complaint counts, not a confidence field
    ADAPTER_VERSION = "0.1.0"

    def __init__(self, *, session: Optional[Any] = None, api_base_url: str = FTC_DNC_REPORTED_CALLS_ENDPOINT):
        # `session` accepts anything requests.Session-shaped so tests can
        # inject a fake without a real network dependency at import time.
        self._session = session
        self._api_base_url = api_base_url

    def query(
        self,
        *,
        case_id: str,
        phone_number_token: str,
        phone_number_e164: str,
        timeout_seconds: float,
    ) -> NormalizedObservation:
        session = self._session or self._lazy_requests_session()

        try:
            response = session.get(
                self._api_base_url,
                params={"phone": phone_number_e164},
                timeout=timeout_seconds,
            )
        except Exception as exc:  # requests.Timeout / ConnectionError / etc.
            if "timed out" in str(exc).lower() or "timeout" in type(exc).__name__.lower():
                raise ProviderTimeoutError(str(exc)) from exc
            raise ProviderNetworkError(str(exc)) from exc

        if response.status_code == 429:
            raise ProviderRateLimitedError(f"FTC API rate limited (HTTP {response.status_code})")
        if response.status_code >= 500:
            raise ProviderServerError(f"FTC API server error (HTTP {response.status_code})")
        if response.status_code >= 400:
            raise ProviderInvalidResponseError(f"FTC API rejected request (HTTP {response.status_code})")

        try:
            payload = response.json()
        except Exception as exc:
            raise ProviderInvalidResponseError(f"FTC API returned non-JSON response: {exc}") from exc

        return self._normalize(case_id=case_id, phone_number_token=phone_number_token, payload=payload)

    def _normalize(self, *, case_id: str, phone_number_token: str, payload: dict) -> "NormalizedObservation":
        complaint_count = payload.get("complaint_count") or payload.get("count") or 0
        native_classification = "reported" if complaint_count and complaint_count > 0 else "not_reported"

        normalized = (
            NormalizedClassification.SUSPICIOUS if complaint_count and complaint_count > 0
            else NormalizedClassification.UNKNOWN
        )
        # Deliberately SUSPICIOUS rather than SPAM/SCAM/FRAUD: FTC data is
        # unverified consumer complaint volume, not a confirmed disposition.
        # See docs/GROUND_TRUTH_PROTOCOL.md — this is a policy decision, not
        # an incidental default, and must not be "upgraded" to a malicious
        # class without a pre-registered, justified mapping.

        last_reported_raw = payload.get("last_reported_date")
        provider_timestamp = None
        if last_reported_raw:
            try:
                provider_timestamp = datetime.fromisoformat(last_reported_raw).replace(tzinfo=timezone.utc)
            except ValueError:
                provider_timestamp = None

        return build_observation(
            case_id=case_id,
            phone_number_token=phone_number_token,
            provider=self.PROVIDER_ID,
            provider_request_id=payload.get("request_id"),
            provider_classification=native_classification,
            normalized_classification=normalized,
            category=payload.get("subject") or payload.get("category"),
            provider_confidence_raw=complaint_count,
            normalized_confidence=None,  # complaint count is not a confidence scale — see CONFIDENCE_INTERPRETATION
            provider_timestamp=provider_timestamp,
            expires_at=None,
            source_version=self.ADAPTER_VERSION,
        )

    @staticmethod
    def _lazy_requests_session():
        import requests

        return requests.Session()
