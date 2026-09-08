"""Experiment runner.

Per EXPERIMENT_PLAN.md §14 (Experimental Run) and §15 (Provider Fairness
Rules): iterates every corpus case against every enabled provider, using the
same corpus version, normalization, timeout policy, and retry policy for
every provider in a run — no provider may receive a specially filtered
corpus or a looser policy than another.

A failed query is NEVER converted into a LEGITIMATE observation here — see
domain/errors.py and domain/classifications.is_failure(). The runner records
the typed error and moves on to the next case/provider pair.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from reputation_experiment.adapters.base import ProviderAdapter
from reputation_experiment.domain.classifications import NormalizedClassification
from reputation_experiment.domain.errors import ProviderAdapterError
from reputation_experiment.domain.models import CorpusCase, NormalizedObservation
from reputation_experiment.domain.normalization import build_observation
from reputation_experiment.execution.cache import CacheMode, ObservationCache
from reputation_experiment.execution.redaction import redact
from reputation_experiment.execution.retry_policy import DEFAULT_RETRY_POLICY, RetryPolicy, call_with_retry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunConfig:
    timeout_seconds: float = 10.0
    cache_mode: CacheMode = CacheMode.LIVE_ONLY
    retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY
    repetitions: int = 1


def _failure_observation(
    *, case_id: str, phone_number_token: str, provider: str, error: ProviderAdapterError
) -> NormalizedObservation:
    """Builds the typed-failure observation. classification is UNAVAILABLE
    (provider could not be reached / did not respond usefully) rather than
    ERROR, unless the caller already distinguishes further — both are in
    FAILURE_CLASSIFICATIONS and excluded identically from the malicious/
    legitimate binary split (see domain/classifications.py).
    """
    classification = (
        NormalizedClassification.UNAVAILABLE
        if error.error_type.value in ("TIMEOUT", "UNAVAILABLE", "NETWORK_ERROR", "RATE_LIMITED")
        else NormalizedClassification.ERROR
    )
    return build_observation(
        case_id=case_id,
        phone_number_token=phone_number_token,
        provider=provider,
        normalized_classification=classification,
        error_type=error.error_type.value,
        cache_hit=False,
    )


def run_one(
    *,
    adapter: ProviderAdapter,
    case: CorpusCase,
    phone_number_e164: str,
    config: RunConfig,
    cache: ObservationCache | None = None,
) -> NormalizedObservation:
    """Run a single (provider, case) query, applying retry policy and
    (optionally) cache policy. phone_number_e164 must come from the
    restricted-access live corpus, never from a committed fixture file —
    see adapters/base.py's query() docstring.
    """

    def _fetch() -> NormalizedObservation:
        try:
            return call_with_retry(
                lambda: adapter.timed_query(
                    case_id=case.case_id,
                    phone_number_token=case.phone_number_token,
                    phone_number_e164=phone_number_e164,
                    timeout_seconds=config.timeout_seconds,
                ),
                policy=config.retry_policy,
            )
        except ProviderAdapterError as exc:
            logger.warning(
                redact(f"{adapter.PROVIDER_ID} failed for case={case.case_id}: {exc}")
            )
            return _failure_observation(
                case_id=case.case_id,
                phone_number_token=case.phone_number_token,
                provider=adapter.PROVIDER_ID,
                error=exc,
            )

    if cache is None or config.cache_mode == CacheMode.LIVE_ONLY:
        return _fetch()

    result, cache_hit = cache.get_or_fetch(
        provider=adapter.PROVIDER_ID,
        phone_number_token=case.phone_number_token,
        mode=config.cache_mode,
        fetch=_fetch,
    )
    if isinstance(result, NormalizedObservation):
        return result

    # Cache hit returned a raw dict (see ObservationCache.get_or_fetch) —
    # reconstruct the classification/error_type fields callers need for
    # analysis without silently reinterpreting anything else.
    return build_observation(
        case_id=result["case_id"],
        phone_number_token=result["phone_number_token"],
        provider=result["provider"],
        normalized_classification=NormalizedClassification(result["normalized_classification"]),
        provider_classification=result.get("provider_classification"),
        provider_request_id=result.get("provider_request_id"),
        category=result.get("category"),
        provider_confidence_raw=result.get("provider_confidence_raw"),
        normalized_confidence=result.get("normalized_confidence"),
        latency_ms=result.get("latency_ms"),
        http_status=result.get("http_status"),
        error_type=result.get("error_type"),
        cache_hit=True,
        source_version=result.get("source_version"),
    )


def run_batch(
    *,
    adapters: Iterable[ProviderAdapter],
    cases: Iterable[CorpusCase],
    phone_lookup: dict[str, str],
    config: RunConfig,
    cache: ObservationCache | None = None,
) -> list[NormalizedObservation]:
    """Run every (case, adapter) pair. phone_lookup maps
    case.phone_number_token -> phone_number_e164, sourced from the
    restricted-access live corpus (never a committed fixture).

    Per §14: the same corpus is used for every provider in the run — this
    function's structure (outer loop over cases, inner loop over adapters)
    guarantees that by construction rather than by convention.
    """
    observations: list[NormalizedObservation] = []
    adapters = list(adapters)

    for case in cases:
        phone_number_e164 = phone_lookup.get(case.phone_number_token)
        if phone_number_e164 is None:
            logger.warning(
                f"No live phone number available for case={case.case_id} "
                f"token={case.phone_number_token} — skipping all providers for this case"
            )
            continue

        for adapter in adapters:
            for _ in range(config.repetitions):
                observations.append(
                    run_one(
                        adapter=adapter,
                        case=case,
                        phone_number_e164=phone_number_e164,
                        config=config,
                        cache=cache,
                    )
                )

    return observations
