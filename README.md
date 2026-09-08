# reputation-provider-comparison

Research-only harness for empirically comparing phone-reputation data
providers (FTC feed, Hiya, Nomorobo, Call Control, IPQualityScore, First
Orion, TNS) ahead of any decision to change SignalGate Pulse's decision
model. See the source planning document's "Provider Intelligence
Evaluation Track" section for the full rationale.

**This repository is deliberately decoupled from `consumer-v1`.** It must
never be imported by, or contribute a dependency to, the production
Android app. `scripts/verify_isolation.py` enforces that as a CI gate —
see "Isolation and secret-scan gates" below.

## Provider status

| Provider     | Adapter                       | Status                          |
|--------------|--------------------------------|----------------------------------|
| FTC          | `adapters/ftc.py`             | Implemented (public FTC feed)   |
| Hiya         | `adapters/hiya.py`            | Stub — raises `NotImplementedError` |
| Nomorobo     | `adapters/nomorobo.py`        | Stub — raises `NotImplementedError` |
| Call Control | `adapters/call_control.py`    | Stub — raises `NotImplementedError` |
| IPQS         | `adapters/ipqs.py`            | Stub — raises `NotImplementedError` |
| First Orion  | `adapters/first_orion.py`     | Stub — raises `NotImplementedError`; likely carrier-integrated, not a self-serve REST API — see the adapter's docstring |
| TNS          | `adapters/tns.py`             | Stub — raises `NotImplementedError`; likely carrier-integrated, not a self-serve REST API — see the adapter's docstring |

A stub adapter raising loudly is intentional: it keeps an unimplemented
provider from silently polluting a scorecard's reliability metrics.
`scripts/run_experiment.py` refuses up front if you ask it to run a
provider that isn't in `READY_PROVIDERS` yet.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Validate the synthetic corpus

```bash
reputation-experiment validate-corpus src/reputation_experiment/corpus/public_synthetic_cases.jsonl
```

Checks the corpus against its JSON Schema and the ground-truth protocol
(no provider may serve as its own ground truth — see
`corpus/validation.py`).

## Run the test suite

```bash
pytest tests/unit        # domain logic, normalization, metrics, agreement, combinations
pytest tests/contract    # every adapter: registry consistency, stub honesty, FTC error mapping
pytest tests/isolation   # the isolation/secret-scan guards actually work, and this repo passes them
```

## Isolation and secret-scan gates

Both run in CI on every push/PR (see
`.github/workflows/reputation-experiment-ci.yml`) and can be run locally:

```bash
python scripts/verify_isolation.py     # forbidden production references: android.*, CallScreeningEngine, Room, etc. (isolation-guard: allow)
python scripts/scan_sensitive_data.py  # committed secrets, raw E.164 numbers outside the fixture allowlist / NANPA-reserved 555-01XX range
```

A line that must legitimately *name* a forbidden symbol or matched
pattern (documentation explaining what the guard checks for) can be
marked `# isolation-guard: allow` — see `adapters/base.py` and
`domain/errors.py` for the only two current uses. Use sparingly; this is
an escape hatch for prose, never for real usage.

## Running a live experiment

Requires a `--phone-lookup` file (`{token: e164}`) sourced from the
restricted-access live corpus. **This file must never be committed** —
`.gitignore` blocks the conventional filename pattern as a backstop, but
the real control is that it should never exist inside a git working tree
in the first place; keep it in restricted storage and pass a path to it
at run time.

```bash
python scripts/run_experiment.py \
    --corpus src/reputation_experiment/corpus/public_synthetic_cases.jsonl \
    --phone-lookup /path/to/restricted/phone_lookup.json \
    --out results/

reputation-experiment score results/<run-id> \
    --corpus src/reputation_experiment/corpus/public_synthetic_cases.jsonl
```

The credentialed run against real (non-FTC) provider APIs runs only via
`workflow_dispatch` against the protected `reputation-experiment-live`
GitHub Environment (manual approval required) — see the CI workflow's
`manual-experiment-run` job.

## Repository layout

```
src/reputation_experiment/
  domain/        classification vocabulary, errors, normalized models
  adapters/      one module per provider, all sharing adapters/base.py's interface
  corpus/        loader + ground-truth-protocol validation
  execution/     retry policy, cache, redaction, batch runner
  analysis/      metrics, confusion matrix, pairwise agreement, provider
                 combinations, temporal analysis, report assembly
  cli.py         `reputation-experiment validate-corpus|score`
schemas/         JSON Schemas for corpus cases, observations, run metadata, metrics
scripts/         run_experiment.py, generate_report.py, verify_isolation.py, scan_sensitive_data.py
tests/
  unit/          domain + analysis logic
  contract/      adapter interface + FTC error-mapping contract
  isolation/     proves the CI gates actually work, not just that they pass today
  fixtures/      synthetic sample_observations.jsonl for report-generation tests
docs/            EXPERIMENT_PLAN.md and related design docs
```

## Known documentation gap

Several modules' docstrings cite section numbers in `docs/EXPERIMENT_PLAN.md`
(e.g. "§14", "§27", "§28"). That document was not present in the archive
this repository was built from. `docs/EXPERIMENT_PLAN.md` in this
repository is a **reconstruction**, assembled from those citations and
from the source planning document, not the original — see the note at
the top of that file. Replace it with the authoritative version if one
exists.
