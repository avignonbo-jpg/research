# EXPERIMENT_PLAN.md

> **RECONSTRUCTION NOTICE — READ BEFORE RELYING ON THIS DOCUMENT.**
> This file did not exist in the archive this repository was built from,
> even though `src/`, `scripts/`, and `tests/` cite it by section number
> (`§1`–`§31`) throughout. Every section below was reverse-assembled
> **only** from what those citations actually say in context — no section
> content was invented beyond what the code already commits to doing.
> Sections with no supporting citation are marked `[NOT EVIDENCED]` rather
> than filled in with invented content. If an authoritative
> `EXPERIMENT_PLAN.md` exists elsewhere, replace this file with it and
> treat this reconstruction as void — the code's citations were checked
> against this reconstruction, not the other way around.
>
> Source citations for every section are listed at the bottom of this
> file for auditing.

## §1. Purpose and scope

`[NOT EVIDENCED — inferred from repository framing]` This document
governs the reputation-provider comparison research track: a standalone,
removable experiment measuring whether additional phone-reputation
providers (beyond the existing FTC-derived feed) would materially improve
SignalGate Pulse's detection outcomes, before any decision to change the
production decision model. See the source planning document's "Purpose"
section for the fuller framing this experiment operates under.

## §2–3. Decoupling from production

This experiment must never become a dependency of `consumer-v1` (Pulse)
or Multi-Port production behavior. `scripts/verify_isolation.py` enforces
this as a hard CI gate, not a review convention — a violation fails the
build.

## §4–5. `[NOT EVIDENCED]`

No citation in the codebase references these section numbers directly.
Given the surrounding structure (§2–3 scope, §6 interface), these likely
covered corpus sourcing or provider selection criteria, but nothing here
should be treated as more than a guess.

## §6. `ProviderAdapter` interface and core field definitions

Defines the adapter interface every provider integration must implement
(`adapters/base.py`) and the `NormalizedObservation` field set
(`domain/models.py`), matched field-for-field. This interface is
research-only and must not be placed in, or imported by, the production
Android architecture.

## §7. Classification vocabulary

The experiment must distinguish a provider's exact native classification
(`provider_classification` — never discarded, even after normalization)
from the project's own `normalized_classification` vocabulary
(`domain/classifications.py`). A separate, cited "Binary evaluation
policy" governs how the ten-value normalized vocabulary collapses to a
MALICIOUS/LEGITIMATE binary split for precision/recall/F1 purposes
(spoofing and gray-zone cases are evaluated separately rather than forced
into the binary split).

## §8. Confidence normalization

Provider confidence-like fields must only be mapped onto the project's
0.0–1.0 `normalized_confidence` scale when a pre-registered, defensible
mapping exists for that provider (`domain/normalization.py`,
`ConfidenceInterpretation`). Otherwise the raw value is preserved in
`provider_confidence_raw` and `normalized_confidence` stays `null` —
never force-fit an undocumented scale into a false appearance of
comparability. See also `docs/PROVIDER_SEMANTICS.md`.

## §9. `[NOT EVIDENCED]`

## §10. Labeled test-corpus record (`CorpusCase`)

Defines the corpus case schema — matched field-for-field by
`domain/models.CorpusCase`, plus `case_id`. See `docs/GROUND_TRUTH_PROTOCOL.md`
and `schemas/corpus-case.schema.json`.

## §11. Ground-Truth Rules

No provider under evaluation may serve as its own ground truth, and
ground truth must not be circularly derived from the set of providers
being evaluated (`corpus/validation.py`). Enforced as `validate_corpus(...,
strict=True)`, not left as a documentation-only rule. See
`docs/GROUND_TRUTH_PROTOCOL.md`.

## §12. `[NOT EVIDENCED]`

## §13. `[paired with §18 — see Temporal Stability below]`

## §14. Experimental Run

Iterate every corpus case against every enabled provider, using the same
corpus version, normalization, timeout policy, and retry policy for every
provider in a single run — no provider may receive a specially filtered
corpus or a looser policy than another. Implemented in
`execution/runner.run_batch` (outer loop over cases, inner loop over
adapters, by construction rather than convention).

## §15. Provider Fairness Rules

All providers must be subject to the same retry policy
(`execution/retry_policy.py`) and the same run configuration
(`RunConfig`) within one experimental run — see §14.

## §16. Primary Detection Metrics

Precision, recall, F1, TPR, FPR, coverage rate, indeterminate rate, and
failure rate per provider, computed only over the subset of cases where
ground truth resolves to a binary MALICIOUS/LEGITIMATE outcome (spoofing
and gray-zone cases evaluated separately — see §7's note). Implemented in
`analysis/metrics.py`.

## §17. `[NOT EVIDENCED]`

## §18. Temporal Stability

Paired with §13. Analyzes whether a provider's classification for the
same number is stable over repeated observations across time, versus
churning — see `analysis/temporal.py`.

## §19. Provider Agreement

Pairwise agreement analysis between providers' normalized classifications
for the same case — see `analysis/agreement.py`.

## §20–22. Offline Combination Experiments

Evaluates provider combinations (e.g. UNION, INTERSECTION, MAJORITY
voting) purely as an offline analysis over already-collected
observations — explicitly **not** a learned fusion model, per the cited
reviewer notes. §22 specifically addresses marginal-value analysis: what
detection improvement (if any) does adding one additional provider
contribute on top of an existing baseline combination? See
`analysis/combinations.py`. This offline analysis is separate from, and
must not be read as pre-approving, the production multi-provider fusion
architecture described in the source planning document's "Future
architectural direction — Phase 3 intent only" section — that remains
gated on this experiment producing measured evidence first.

## §23. Cache Modes

Four cache modes govern how a run interacts with previously-cached
observations: `LIVE_ONLY`, `CACHE_ONLY`, `CACHE_THEN_REFRESH`, and
`CACHE_WITH_BACKGROUND_REFRESH` — see `execution/cache.CacheMode` and
`schemas/run.schema.json`.

## §24. Failure Semantics

A provider failure (timeout, network error, rate limit, server error,
invalid response) must never be silently converted into a `LEGITIMATE`
observation. Failures get a typed error (`domain/errors.py`) and a
`normalized_classification` of `UNAVAILABLE` or `ERROR` — both excluded
from the malicious/legitimate binary split (§16) rather than treated as
"clean."

## §25. Security Requirements — Logging and Secrets

Logs must never contain raw phone numbers, API keys, or other sensitive
material — see `execution/redaction.py`. Paired with §26 for the
secret-scanning CI gate (`scripts/scan_sensitive_data.py`).

## §26. Security Requirements — Secret Scanning

`[content inferred from §25 pairing and scan_sensitive_data.py's own
docstring citation — not independently evidenced]` Committed secrets
(API keys) and raw E.164 phone numbers outside an explicit fixture
allowlist or the NANPA-reserved `555-01XX` fictional range must fail CI.

## §27. Manual Experiment Run

The credentialed run against real (non-FTC) provider APIs is gated behind
a protected GitHub Environment (`reputation-experiment-live`) requiring
manual approval, triggered only via `workflow_dispatch` — never on a
regular push or PR. See `.github/workflows/reputation-experiment-ci.yml`'s
`manual-experiment-run` job and `scripts/run_experiment.py`.

## §28. Isolation Guard

CI must hard-fail if any file under this repository imports or otherwise
references forbidden production symbols: `android.*`, `com.signalgate.*`,  <!-- isolation-guard: allow -->
`CallScreeningEngine`, `SourceEntity`, `UnifiedEntryEntity`, `Room`, etc.  <!-- isolation-guard: allow -->
See `scripts/verify_isolation.py` and `tests/isolation/test_isolation_guard.py`,
which additionally proves the guard has teeth rather than only checking
that it currently passes.

## §29. Reproducibility Record

Every run must record enough metadata to be reproducible after the fact:
`experiment_run_id`, corpus version (content hash), adapter version per
provider queried, provider API version (where knowable), git commit,
start/completion timestamps, a configuration hash, the provider set,
cache mode, timeout, and repetition count. See `domain/models.RunMetadata`,
`schemas/run.schema.json`, and `scripts/run_experiment.py`.

## §30–31. Report Assembly

Serializes analysis outputs into a structured `results/<run-id>/` layout
(`run.json`, `observations.jsonl`, `metrics.json`, `agreement.json`,
`latency.json`, `failures.json`). Public repository reports contain
aggregate statistics only — this module does not write raw provider
responses or the live corpus; callers are responsible for keeping those
in restricted storage per `docs/DATA_HANDLING.md`. See `analysis/reports.py`.

## Referenced sibling documents

These are cited alongside `EXPERIMENT_PLAN.md` but are separate files,
also not present in the original archive:

- **`docs/GROUND_TRUTH_PROTOCOL.md`** — the no-circular-validation rule
  (§11) and the policy that FTC complaint volume alone never justifies a
  `MALICIOUS` label (only `SUSPICIOUS`) — see `adapters/ftc.py`.
- **`docs/PROVIDER_SEMANTICS.md`** — per-provider confidence-scale
  documentation referenced by §8 and by the `first_orion.py` / `tns.py`
  stub adapters regarding carrier-integration vs. self-serve-API shape.
- **`docs/DATA_HANDLING.md`** — governs where the live corpus, cache
  files, and raw provider responses must be stored (never this
  repository) — see §30–31 and `execution/cache.py`.

Minimal placeholder versions of these three files are included in this
`docs/` directory, in the same spirit as this reconstruction: only what's
directly evidenced by the code, clearly marked as reconstructions.

---

### Citation index (for auditing this reconstruction)

Generated by searching every `.py` file under `src/`, `scripts/`, and
`tests/` for `EXPERIMENT_PLAN.md`. Re-run to verify nothing here was
invented beyond what's cited:

```bash
grep -rn "EXPERIMENT_PLAN.md" --include="*.py" . | grep -v __pycache__
```
