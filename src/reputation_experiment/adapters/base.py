"""ProviderAdapter base interface.

EXPERIMENT_PLAN.md §6: this interface is research-only and MUST NOT be
placed in, or imported by, the production Android architecture. See
tests/isolation/test_isolation_guard.py and scripts/verify_isolation.py,
which fail the build if any file under src/reputation_experiment imports
android.*, com.signalgate.*, or any of the forbidden production symbols.  # isolation-guard: allow

Each adapter must raise a typed ProviderAdapterError subclass (see
domain/errors.py) rather than letting an arbitrary exception escape, and
must never invent a NormalizedObservation with classification=LEGITIMATE to
paper over a failure.
"""
from __future__ import annotations

import abc
import time
from typing import Optional

from reputation_experiment.domain.errors import ProviderAdapterError
from reputation_experiment.domain.models import NormalizedObservation
from reputation_experiment.domain.normalization import ConfidenceInterpretation


class ProviderAdapter(abc.ABC):
    """Base class for all provider adapters (FtcAdapter, HiyaAdapter,
    NomoroboAdapter, CallControlAdapter, IpqsAdapter, ...).
    """

    #: Short provider identifier used as NormalizedObservation.provider and
    #: in report tables (e.g. "FTC", "HIYA").
    PROVIDER_ID: str = "UNSET"

    #: How this provider's confidence-like field should be read. See
    #: domain/normalization.ConfidenceInterpretation. Declared at class
    #: level so analysis code can check it before attempting to compare
    #: confidence values across providers.
    CONFIDENCE_INTERPRETATION: ConfidenceInterpretation = ConfidenceInterpretation.NOT_DOCUMENTED

    #: Adapter code version, recorded on every observation's
    #: source_version so results are traceable to the exact normalization
    #: logic that produced them (EXPERIMENT_PLAN.md §29).
    ADAPTER_VERSION: str = "0.1.0"

    @abc.abstractmethod
    def query(
        self,
        *,
        case_id: str,
        phone_number_token: str,
        phone_number_e164: str,
        timeout_seconds: float,
    ) -> NormalizedObservation:
        """Query the provider for one phone number and return a
        NormalizedObservation.

        phone_number_e164 is supplied out of band by the runner at query
        time (from the restricted-access live corpus) and MUST NOT be
        logged, cached to disk in plaintext, or embedded in any raised
        exception message — see execution/redaction.py.

        Implementations must catch provider-specific exceptions (HTTP
        errors, timeouts, malformed JSON, etc.) and re-raise them as one of
        the typed subclasses in domain.errors, never let a raw exception
        with an embedded phone number propagate to the runner's logs.
        """
        raise NotImplementedError

    def timed_query(
        self,
        *,
        case_id: str,
        phone_number_token: str,
        phone_number_e164: str,
        timeout_seconds: float,
    ) -> NormalizedObservation:
        """Wraps query() to guarantee latency_ms is always populated (even
        on the exception path, latency belongs to execution/runner.py's own
        try/except around this call — this method just standardizes timing
        for the success path so adapters don't each reimplement it).
        """
        start = time.monotonic()
        observation = self.query(
            case_id=case_id,
            phone_number_token=phone_number_token,
            phone_number_e164=phone_number_e164,
            timeout_seconds=timeout_seconds,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if observation.latency_ms is None:
            # Backfill only if the adapter didn't already measure a more
            # precise provider-side latency (e.g. from a response header).
            observation = _with_latency(observation, elapsed_ms)
        return observation


def _with_latency(observation: NormalizedObservation, latency_ms: int) -> NormalizedObservation:
    from dataclasses import replace

    return replace(observation, latency_ms=latency_ms)


class NotImplementedAdapter(ProviderAdapter):
    """Placeholder used by commercial adapters (Hiya, Nomorobo, Call
    Control, IPQS, First Orion, TNS) until this branch is wired up with
    real credentials in
    a protected GitHub Environment (see .github/workflows and
    EXPERIMENT_PLAN.md §27's Manual Experiment Run).

    Raising here is deliberate: a stub that silently returned UNAVAILABLE
    would be indistinguishable in reports from a real provider that was
    genuinely down during a run. Raising NotImplementedError makes "this
    adapter isn't wired up yet" fail loudly in the runner instead of
    quietly polluting a scorecard's reliability metrics.
    """

    def query(
        self,
        *,
        case_id: str,
        phone_number_token: str,
        phone_number_e164: str,
        timeout_seconds: float,
    ) -> NormalizedObservation:
        raise NotImplementedError(
            f"{self.PROVIDER_ID} adapter has no live implementation yet — "
            "requires provider credentials and API contract validation "
            "before this branch can run a live comparison against it. "
            "See docs/PROVIDER_SEMANTICS.md."
        )
