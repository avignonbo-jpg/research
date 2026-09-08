"""Core immutable data contracts.

Design notes (see EXPERIMENT_PLAN.md §6, §10, §29 and the reviewer notes at
the end of the source doc):

- NormalizedObservation is frozen: raw provider data and derived analysis
  must never be mutated in place once recorded, so a run's results stay
  traceable to exactly what a provider returned.
- phone_number_token, not phone_number: reports must be joinable without
  retaining a plain-reversible identifier. A bare hash of a phone number has
  a small enough search space (a handful of billion E.164 numbers) to be
  trivially enumerable; use hmac_phone_token() with a locally-held secret
  instead. The raw number is intentionally NOT a field on this model —
  callers needing the raw number (e.g. an adapter about to make a live
  query) must supply it out of band, sourced from the restricted-access
  live corpus, never from something serialized into results/.
- provider_confidence_raw is preserved exactly as the provider returned it
  (str | int | float) alongside a *separately derived* normalized_confidence
  that may legitimately be None — see domain/normalization.py.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Union

from reputation_experiment.domain.classifications import (
    CorpusClass,
    GroundTruthLabel,
    GroundTruthConfidence,
    AdjudicationStatus,
    NormalizedClassification,
)


def hmac_phone_token(phone_number_e164: str, secret: bytes) -> str:
    """Derive a stable, non-reversible token for a phone number.

    Deliberately HMAC (keyed) rather than a bare hash: E.164 numbers are a
    small enough space that an unkeyed hash (even SHA-256) is enumerable by
    brute force in seconds on commodity hardware. The secret must be held
    locally (e.g. an environment variable injected only in the manual
    experiment-run workflow) and MUST NOT be committed — see
    scripts/scan_sensitive_data.py.
    """
    return hmac.new(secret, phone_number_e164.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class NormalizedObservation:
    """One provider's answer for one corpus case, normalized for
    cross-provider analysis while preserving the original provider output.
    Matches EXPERIMENT_PLAN.md §6 field-for-field, plus case_id (added per
    reviewer note, so analysis can join without re-deriving a token).
    """

    case_id: str
    phone_number_token: str
    provider: str
    provider_request_id: Optional[str]
    provider_classification: Optional[str]
    normalized_classification: NormalizedClassification
    category: Optional[str]
    provider_confidence_raw: Optional[Union[str, int, float]]
    normalized_confidence: Optional[float]
    observed_at: datetime
    provider_timestamp: Optional[datetime]
    expires_at: Optional[datetime]
    latency_ms: Optional[int]
    http_status: Optional[int]
    error_type: Optional[str]
    cache_hit: bool
    source_version: Optional[str]

    def __post_init__(self) -> None:
        if self.normalized_confidence is not None and not (0.0 <= self.normalized_confidence <= 1.0):
            raise ValueError(
                f"normalized_confidence must be in [0.0, 1.0] or None, "
                f"got {self.normalized_confidence!r}"
            )


@dataclass(frozen=True)
class CorpusCase:
    """One labeled test-corpus record. Matches EXPERIMENT_PLAN.md §10, plus
    the three-label split (groundTruthLabel / groundTruthCategory /
    adjudicationStatus) recommended over a single overloaded field, and
    corpus_class for the §9 A-G bucket this case belongs to.

    phone_number_token, not phone_number: public/committed corpus fixtures
    must never contain a raw private individual's number (see
    docs/DATA_HANDLING.md). A live corpus with real numbers, if used, stays
    outside the repository entirely and is joined to this record by token
    at run time, never persisted alongside it.
    """

    case_id: str
    phone_number_token: str
    corpus_class: CorpusClass
    ground_truth_label: GroundTruthLabel
    ground_truth_confidence: GroundTruthConfidence
    ground_truth_source: str
    ground_truth_observed_at: datetime
    adjudication_status: AdjudicationStatus
    ground_truth_expires_at: Optional[datetime] = None
    ground_truth_category: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class RunMetadata:
    """Reproducibility record for one experiment run — EXPERIMENT_PLAN.md
    §29. Every results/<run>/run.json is expected to serialize this.
    """

    experiment_run_id: str
    corpus_version: str
    provider_adapter_version: str
    provider_api_version: str
    git_commit: str
    run_started_at: datetime
    configuration_hash: str
    provider_set: tuple[str, ...]
    cache_mode: str
    timeout_seconds: int
    repetitions: int
    run_completed_at: Optional[datetime] = None
