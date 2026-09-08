# GROUND_TRUTH_PROTOCOL.md

> **Reconstruction, not the original** — assembled from citations in
> `corpus/validation.py` and `adapters/ftc.py`. See `docs/EXPERIMENT_PLAN.md`'s
> reconstruction notice for the full caveat.

## No provider is its own ground truth

A corpus case's `ground_truth_label` and `ground_truth_source` must never
be derived from the output of a provider under evaluation, and must not
be circularly assembled from the set of providers being evaluated in this
experiment (`EXPERIMENT_PLAN.md §11`). `corpus/validation.validate_corpus(...,
strict=True)` enforces this against `CANDIDATE_PROVIDER_IDS`.

## FTC complaint data is evidence, not a verdict

A raw FTC consumer-complaint count, by itself, only ever justifies a
`SUSPICIOUS` normalized classification — never `SPAM`, `SCAM`, `FRAUD`, or
any other confirmed-disposition label. Complaint volume is unverified
self-reported data, not a confirmed disposition. See `adapters/ftc.py`
and `tests/contract/test_adapter_contract.py`'s
`test_ftc_adapter_never_returns_malicious_or_legitimate`.

## Corpus case categories

The synthetic corpus (`corpus/public_synthetic_cases.jsonl`) is organized
by `corpus_class`, observed in the file itself:

| `corpus_class`         | `ground_truth_label` |
|-------------------------|------------------------|
| `KNOWN_MALICIOUS`       | `MALICIOUS`           |
| `LEGITIMATE_BUSINESS`   | `LEGITIMATE`          |
| `ORDINARY_PERSONAL`     | `LEGITIMATE`          |
| `RECENTLY_REPORTED`     | `MALICIOUS`           |
| `HISTORICAL_RECOVERED`  | `LEGITIMATE`          |
| `SPOOFING_EXAMPLE`      | `SPOOFED_NUMBER`      |
| `GRAY_ZONE`             | `AMBIGUOUS`           |

`SPOOFED_NUMBER` and `AMBIGUOUS` are deliberately excluded from the binary
MALICIOUS/LEGITIMATE confusion matrix used for precision/recall/F1 (see
`analysis/metrics.py`) — forcing them into either bucket would misrepresent
what the provider actually got right or wrong.
