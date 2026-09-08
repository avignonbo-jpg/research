"""IPQS (IPQualityScore) adapter — STUB.

IPQS's Phone Number Validation API returns risk-oriented intelligence — a
fraud/risk score, validity, carrier, line type, recent-abuse signals — which
IPQS itself documents as a risk estimate, not a calibrated probability of
maliciousness. Not implemented in this pass: no credentials or live response
schema were available. See hiya.py's docstring for the pattern to follow
when wiring this up for real.
"""
from __future__ import annotations

from reputation_experiment.adapters.base import NotImplementedAdapter
from reputation_experiment.domain.normalization import ConfidenceInterpretation


class IpqsAdapter(NotImplementedAdapter):
    PROVIDER_ID = "IPQS"
    # IPQS's "fraud score" is explicitly a risk estimate per their own docs,
    # not the same scale as another provider's "confidence" — treat as its
    # own risk_score interpretation, never silently cast to a probability.
    CONFIDENCE_INTERPRETATION = ConfidenceInterpretation.RISK_SCORE
    ADAPTER_VERSION = "0.0.0-stub"
