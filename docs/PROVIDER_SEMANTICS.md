# PROVIDER_SEMANTICS.md

> **Reconstruction, not the original** — assembled from citations in
> `domain/normalization.py` and the adapter docstrings. See
> `docs/EXPERIMENT_PLAN.md`'s reconstruction notice for the full caveat.

## Confidence is only normalized where a documented mapping exists

`normalized_confidence` (0.0–1.0) is populated only when a provider
publishes a documented, stable confidence/risk scale that can be mapped
onto that range without guessing. Otherwise `normalized_confidence` stays
`null` and the provider's raw value is preserved verbatim in
`provider_confidence_raw` — see `domain/normalization.ConfidenceInterpretation`.

## Known confidence shapes (from adapter docstrings)

| Provider     | Shape (as documented in the adapter) |
|--------------|----------------------------------------|
| FTC          | Complaint count — not a confidence scale at all; never mapped |
| IPQS         | 0–100 numeric risk score (documented publicly) |
| Call Control | Ordinal confidence indicator |
| Hiya         | Not documented publicly as a stable numeric scale — treat as `NOT_DOCUMENTED` until confirmed |
| First Orion  | Qualitative risk/alert framing, not a documented numeric scale — treat as `NOT_DOCUMENTED` |
| TNS          | Signed numeric reputation scale (worst..best), per TNS's own published materials — its own distinct shape, not directly comparable to IPQS's risk score without an explicit, pre-registered mapping |

## Integration shape varies by provider

Not every provider is a simple per-lookup REST API. First Orion's
PROTECT+ and TNS's Call Guardian are both primarily carrier/operator-integrated
products (inbound risk analysis inside the carrier network, or via
SIP/AIN/ENUM signaling), which may require a partner-level agreement
before any programmatic per-number query is possible at all — a
different integration shape than "call an endpoint with an API key."
Confirm the real integration shape for each before treating a stub
adapter as a drop-in REST client. See `adapters/first_orion.py` and
`adapters/tns.py`.
