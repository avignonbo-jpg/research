"""Hiya Number Reputation adapter — STUB.

Hiya's Number Reputation API requires a commercial service agreement and may
involve per-use fees; API keys must be treated as confidential and never
stored in source control or shipped on client devices (see
docs/PROVIDER_SEMANTICS.md and EXPERIMENT_PLAN.md's Security Requirements).

Not implemented in this pass: no credentials or live response schema were
available to build and contract-test a real client against. When this is
wired up, follow the FTC adapter's shape (query() -> typed errors ->
build_observation()), record HIYA_API_KEY only via GitHub Actions Secrets
injected in the protected `reputation-experiment-live` environment, and add
a tests/contract/ fixture from a redacted recorded response before enabling
this in a Manual Experiment Run.
"""
from __future__ import annotations

from reputation_experiment.adapters.base import NotImplementedAdapter
from reputation_experiment.domain.normalization import ConfidenceInterpretation


class HiyaAdapter(NotImplementedAdapter):
    PROVIDER_ID = "HIYA"
    # Hiya exposes reputation status + classification; documented as a
    # discrete/ordinal signal rather than a numeric score as far as public
    # docs describe it — confirm exact shape once credentials exist.
    CONFIDENCE_INTERPRETATION = ConfidenceInterpretation.NOT_DOCUMENTED
    ADAPTER_VERSION = "0.0.0-stub"
