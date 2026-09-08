"""Explicit failure types.

Per EXPERIMENT_PLAN.md §24 (Failure Semantics): provider failure MUST NEVER
be interpreted as LEGITIMATE. Each failure mode below maps 1:1 to an
ErrorType so a failure is always distinguishable from a successful clean
result, and different failure causes are never collapsed into one bucket
before analysis (a RATE_LIMITED provider and an AUTH_FAILURE provider fail
for operationally different reasons and should be reported separately).
"""
from __future__ import annotations

from enum import Enum


class ErrorType(str, Enum):
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    AUTH_FAILURE = "AUTH_FAILURE"
    RATE_LIMITED = "RATE_LIMITED"
    SERVER_ERROR = "SERVER_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    NETWORK_ERROR = "NETWORK_ERROR"


class ProviderAdapterError(Exception):
    """Base class for adapter-raised errors. Carries an ErrorType so the
    runner (execution/runner.py) can record a distinct, typed failure rather
    than a bare exception message, and never mint a NormalizedObservation
    with classification=LEGITIMATE on the strength of catching this.
    """

    def __init__(self, error_type: ErrorType, message: str):
        super().__init__(message)
        self.error_type = error_type


class ProviderTimeoutError(ProviderAdapterError):
    def __init__(self, message: str = "provider request timed out"):
        super().__init__(ErrorType.TIMEOUT, message)


class ProviderUnavailableError(ProviderAdapterError):
    def __init__(self, message: str = "provider unavailable"):
        super().__init__(ErrorType.UNAVAILABLE, message)


class ProviderAuthError(ProviderAdapterError):
    def __init__(self, message: str = "provider authentication failed"):
        super().__init__(ErrorType.AUTH_FAILURE, message)


class ProviderRateLimitedError(ProviderAdapterError):
    def __init__(self, message: str = "provider rate limit exceeded"):
        super().__init__(ErrorType.RATE_LIMITED, message)


class ProviderServerError(ProviderAdapterError):
    def __init__(self, message: str = "provider returned a server error"):
        super().__init__(ErrorType.SERVER_ERROR, message)


class ProviderInvalidResponseError(ProviderAdapterError):
    def __init__(self, message: str = "provider response failed schema/parse validation"):
        super().__init__(ErrorType.INVALID_RESPONSE, message)


class ProviderNetworkError(ProviderAdapterError):
    def __init__(self, message: str = "network error contacting provider"):
        super().__init__(ErrorType.NETWORK_ERROR, message)


class CorpusValidationError(Exception):
    """Raised when a corpus case fails schema or ground-truth-protocol
    validation (e.g. a case labeled MALICIOUS solely because it appeared in
    unverified FTC data — see corpus/validation.py).
    """


class IsolationViolationError(Exception):
    """Raised by scripts/verify_isolation.py when experiment code imports a
    forbidden production symbol. The full list lives in FORBIDDEN in that
    script (android.*, com.signalgate.*, CallScreeningEngine, SourceEntity,  # isolation-guard: allow
    UnifiedEntryEntity, Room, ...) and is intentionally not duplicated here  # isolation-guard: allow
    beyond this one documentation reference.
    """
