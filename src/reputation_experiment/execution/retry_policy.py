"""Shared retry policy.

Per EXPERIMENT_PLAN.md §15 (Provider Fairness Rules): all providers MUST
receive the same retry policy and timeout policy. This module is the single
place that policy is defined so the runner can't accidentally apply a
looser retry budget to one provider than another.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from reputation_experiment.domain.errors import (
    ProviderAdapterError,
    ProviderAuthError,
    ProviderInvalidResponseError,
)

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    jitter_seconds: float = 0.25

    def delay_for_attempt(self, attempt: int) -> float:
        """Exponential backoff with jitter. attempt is 1-indexed."""
        exponential = min(self.max_delay_seconds, self.base_delay_seconds * (2 ** (attempt - 1)))
        return exponential + random.uniform(0, self.jitter_seconds)


# Non-retryable: retrying an auth failure or a response that already failed
# schema validation just wastes budget and adds noise to latency metrics
# without any chance of succeeding.
NON_RETRYABLE_ERRORS = (ProviderAuthError, ProviderInvalidResponseError)

DEFAULT_RETRY_POLICY = RetryPolicy()


def call_with_retry(fn: Callable[[], T], *, policy: RetryPolicy = DEFAULT_RETRY_POLICY) -> T:
    """Invoke fn(), retrying on ProviderAdapterError subclasses (except the
    non-retryable ones above) up to policy.max_attempts times.
    """
    last_error: ProviderAdapterError | None = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except NON_RETRYABLE_ERRORS:
            raise
        except ProviderAdapterError as exc:
            last_error = exc
            if attempt < policy.max_attempts:
                time.sleep(policy.delay_for_attempt(attempt))

    assert last_error is not None
    raise last_error
