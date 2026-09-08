# DATA_HANDLING.md

> **Reconstruction, not the original** — assembled from citations in
> `domain/models.py`, `execution/cache.py`, and `analysis/reports.py`.
> See `docs/EXPERIMENT_PLAN.md`'s reconstruction notice for the full
> caveat.

## What may be committed to this repository

Only the synthetic corpus (`src/reputation_experiment/corpus/public_synthetic_cases.jsonl`)
belongs in version control. It stores an opaque `phone_number_token`
(HMAC-derived, per `domain/models.hmac_phone_token`) for each case, never
a raw E.164 number.

## What must never be committed

- **The live corpus's real E.164 numbers.** If a live corpus is used, it
  stays outside this repository in restricted storage. `scripts/run_experiment.py`
  takes a `--phone-lookup` path for exactly this reason — the file is
  passed in at run time, never checked in. `.gitignore` blocks the
  conventional filename pattern as a backstop, not as the actual control.
- **Cached provider responses.** `execution/cache.ObservationCache` writes
  to a directory the caller chooses (`--cache-dir`); that directory must
  never be committed. `.gitignore` covers `.cache/` and `cache/`.
- **Raw provider API credentials.** Supplied via environment variables in
  the protected `reputation-experiment-live` GitHub Environment, never
  hardcoded. `scripts/scan_sensitive_data.py` fails CI on a committed
  secret pattern.
- **Actual run outputs under `results/`.** The directory itself is
  tracked (`results/.gitkeep`) so a fresh clone has somewhere to write,
  but generated run data is gitignored — aggregate metrics from a real
  run may still be sensitive pending review, and results are
  regenerable by re-running the experiment.

## Logging

Logs must never contain raw phone numbers or API keys — see
`execution/redaction.py`, which is applied before anything is written to
a log line, not after.
