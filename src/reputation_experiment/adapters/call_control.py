"""Call Control adapter — STUB.

Call Control's Identify API returns spam status, a confidence indicator,
call type, complaint timing, and tags, derived from its own proprietary
complaint database — a materially different evidence source from FTC's
consumer-reported DNC data or IPQS's fraud/risk model. Not implemented in
this pass: no credentials or live response schema were available. See
hiya.py's docstring for the pattern to follow when wiring this up for real.
"""
from __future__ import annotations

from reputation_experiment.adapters.base import NotImplementedAdapter
from reputation_experiment.domain.normalization import ConfidenceInterpretation


class CallControlAdapter(NotImplementedAdapter):
    PROVIDER_ID = "CALL_CONTROL"
    # Call Control describes its own field as a "confidence indicator" —
    # treat as ordinal/opaque, not a calibrated probability, until a
    # pre-registered calibration procedure says otherwise (§8 / reviewer
    # notes on Confidence policy).
    CONFIDENCE_INTERPRETATION = ConfidenceInterpretation.ORDINAL
    ADAPTER_VERSION = "0.0.0-stub"
