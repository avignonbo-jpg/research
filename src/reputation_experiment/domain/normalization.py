"""Normalization helpers shared by all adapters.

Per EXPERIMENT_PLAN.md §8 and the reviewer notes: provider confidence must
never be treated as equivalent merely because a field is named "confidence".
An IPQS fraud/risk score and a Call Control confidence indicator are
different scales; converting both into a single float without a defensible,
pre-registered mapping manufactures precision that doesn't exist. Adapters
should prefer leaving normalized_confidence as None over guessing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Union

from reputation_experiment.domain.classifications import NormalizedClassification
from reputation_experiment.domain.models import NormalizedObservation


class ConfidenceInterpretation(str, Enum):
    """How a given provider's confidence-like field should be read. Recorded
    per-adapter (see adapters/base.py CONFIDENCE_INTERPRETATION) rather than
    assumed identical across providers.
    """

    ORDINAL = "ordinal"          # e.g. LOW/MEDIUM/HIGH tiers
    RISK_SCORE = "risk_score"    # e.g. IPQS fraud score — a risk estimate, not a probability
    BINARY_FLAG = "binary_flag"  # e.g. a simple spam/not-spam boolean
    UNAVAILABLE = "unavailable"  # provider does not return anything confidence-like
    NOT_DOCUMENTED = "not_documented"  # provider returns something but its scale isn't published


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_observation(
    *,
    case_id: str,
    phone_number_token: str,
    provider: str,
    normalized_classification: NormalizedClassification,
    provider_request_id: Optional[str] = None,
    provider_classification: Optional[str] = None,
    category: Optional[str] = None,
    provider_confidence_raw: Optional[Union[str, int, float]] = None,
    normalized_confidence: Optional[float] = None,
    provider_timestamp: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    latency_ms: Optional[int] = None,
    http_status: Optional[int] = None,
    error_type: Optional[str] = None,
    cache_hit: bool = False,
    source_version: Optional[str] = None,
    observed_at: Optional[datetime] = None,
) -> NormalizedObservation:
    """Convenience constructor used by every adapter so the field defaults
    (observed_at=now, cache_hit=False, etc.) live in one place instead of
    being re-decided per adapter.
    """
    return NormalizedObservation(
        case_id=case_id,
        phone_number_token=phone_number_token,
        provider=provider,
        provider_request_id=provider_request_id,
        provider_classification=provider_classification,
        normalized_classification=normalized_classification,
        category=category,
        provider_confidence_raw=provider_confidence_raw,
        normalized_confidence=normalized_confidence,
        observed_at=observed_at or utcnow(),
        provider_timestamp=provider_timestamp,
        expires_at=expires_at,
        latency_ms=latency_ms,
        http_status=http_status,
        error_type=error_type,
        cache_hit=cache_hit,
        source_version=source_version,
    )
