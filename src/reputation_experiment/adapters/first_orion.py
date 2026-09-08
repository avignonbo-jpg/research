"""First Orion PROTECT+ adapter — STUB.

First Orion's PROTECT+ risk-detection product is carrier-integrated
(inbound risk analysis delivered inside the carrier network / via SIP
configuration), not a simple self-serve REST lookup like IPQS — see
First Orion's own developer materials. A partner/carrier-level agreement
and onboarding is likely required before any programmatic per-number query
is possible at all, which changes the integration shape from "call an
endpoint with an API key" to something closer to a carrier integration.
That distinction should be confirmed (and documented in
docs/PROVIDER_SEMANTICS.md) before this adapter is implemented for real,
since it affects whether this provider can be included in an ad hoc
experiment harness the same way as the other candidates.

Not implemented in this pass: no credentials, partner agreement, or live
response schema were available. See hiya.py's docstring for the pattern to
follow when wiring this up for real.
"""
from __future__ import annotations

from reputation_experiment.adapters.base import NotImplementedAdapter
from reputation_experiment.domain.normalization import ConfidenceInterpretation


class FirstOrionAdapter(NotImplementedAdapter):
    PROVIDER_ID = "FIRST_ORION"
    # Public materials describe risk detection in qualitative/alert terms
    # rather than a documented numeric scale — treat as undocumented until
    # a real integration contract says otherwise.
    CONFIDENCE_INTERPRETATION = ConfidenceInterpretation.NOT_DOCUMENTED
    ADAPTER_VERSION = "0.0.0-stub"
