"""TNS (Transaction Network Services) Call Guardian adapter — STUB.

Call Guardian is primarily a carrier/operator-integrated reputation-scoring
platform (deployed inside carrier networks, consumed via SIP/AIN/ENUM
signaling integration or an operator-level API), rather than a simple
per-lookup developer REST API. Publicly described scoring is a signed
scale (worst to best) produced by TNS's own model, which is a different
shape again from IPQS's risk score or Call Control's ordinal confidence
indicator — do not assume comparability without an explicit, documented
mapping. As with first_orion.py, confirm the actual integration shape
(carrier-level vs. queryable API) before treating this as a drop-in REST
adapter.

Not implemented in this pass: no credentials, partner agreement, or live
response schema were available. See hiya.py's docstring for the pattern to
follow when wiring this up for real.
"""
from __future__ import annotations

from reputation_experiment.adapters.base import NotImplementedAdapter
from reputation_experiment.domain.normalization import ConfidenceInterpretation


class TnsAdapter(NotImplementedAdapter):
    PROVIDER_ID = "TNS"
    # TNS documents a signed numeric reputation scale (worst..best) rather
    # than an ordinal tier or a 0-1 risk probability — its own distinct
    # shape, not directly comparable to IPQS's risk_score without a
    # pre-registered mapping.
    CONFIDENCE_INTERPRETATION = ConfidenceInterpretation.RISK_SCORE
    ADAPTER_VERSION = "0.0.0-stub"
