#!/usr/bin/env python3
"""Run a live experiment: query every enabled provider for every corpus
case and write results/<run-id>/{run.json,observations.jsonl}.

Usage:
    python scripts/run_experiment.py \
        --corpus <path> \
        --phone-lookup <path> \
        [--providers FTC,HIYA,...] \
        [--out results/] \
        [--timeout 10] \
        [--cache-mode LIVE_ONLY|CACHE_ONLY|CACHE_THEN_REFRESH|CACHE_WITH_BACKGROUND_REFRESH]

--phone-lookup must point at a JSON file of {phone_number_token: e164}
sourced from the RESTRICTED-ACCESS live corpus. This is deliberately never
committed to this repository (see domain/models and execution/runner
docstrings) — supply it out of band (e.g. a path mounted into the
protected `reputation-experiment-live` GitHub Environment), never as a
repo file or a CI workflow secret rendered into plaintext.

--providers defaults to only the providers that currently have a real
(non-stub) adapter implementation. Naming a provider that is still a stub
(see adapters/*.py — most of them, right now) fails immediately with a
clear message rather than letting the batch crash partway through on a
NotImplementedError, which is what a stub adapter deliberately raises if
it's actually queried (see adapters/base.py's NotImplementedAdapter).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reputation_experiment.adapters.base import ProviderAdapter  # noqa: E402
from reputation_experiment.adapters.call_control import CallControlAdapter  # noqa: E402
from reputation_experiment.adapters.first_orion import FirstOrionAdapter  # noqa: E402
from reputation_experiment.adapters.ftc import FtcAdapter  # noqa: E402
from reputation_experiment.adapters.hiya import HiyaAdapter  # noqa: E402
from reputation_experiment.adapters.ipqs import IpqsAdapter  # noqa: E402
from reputation_experiment.adapters.nomorobo import NomoroboAdapter  # noqa: E402
from reputation_experiment.adapters.tns import TnsAdapter  # noqa: E402
from reputation_experiment.corpus.loader import load_corpus  # noqa: E402
from reputation_experiment.corpus.validation import validate_corpus  # noqa: E402
from reputation_experiment.execution.cache import CacheMode, ObservationCache  # noqa: E402
from reputation_experiment.execution.runner import RunConfig, run_batch  # noqa: E402
from reputation_experiment.analysis.reports import write_observations, write_run_metadata  # noqa: E402
from reputation_experiment.domain.models import RunMetadata  # noqa: E402

# Every known candidate provider, whether or not it's implemented yet.
ADAPTER_REGISTRY: dict[str, type[ProviderAdapter]] = {
    "FTC": FtcAdapter,
    "HIYA": HiyaAdapter,
    "NOMOROBO": NomoroboAdapter,
    "CALL_CONTROL": CallControlAdapter,
    "IPQS": IpqsAdapter,
    "FIRST_ORION": FirstOrionAdapter,
    "TNS": TnsAdapter,
}

# Providers with a real (non-stub) implementation as of this script.
# Update this set in the same change that removes NotImplementedAdapter
# from a given provider's adapter class.
READY_PROVIDERS = frozenset({"FTC"})


def _corpus_content_hash(path: Path) -> str:
    """corpus_version = a content hash, not a hand-maintained version
    string — this is exact, reproducible, and can't drift out of sync
    with what was actually queried, unlike a manually bumped version tag.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _configuration_hash(config: RunConfig, providers: list[str]) -> str:
    payload = json.dumps(
        {
            "timeout_seconds": config.timeout_seconds,
            "cache_mode": config.cache_mode.value,
            "repetitions": config.repetitions,
            "retry_policy": asdict(config.retry_policy),
            "providers": sorted(providers),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _build_adapters(requested: list[str]) -> list[ProviderAdapter]:
    unknown = [p for p in requested if p not in ADAPTER_REGISTRY]
    if unknown:
        raise SystemExit(f"Unknown provider id(s): {unknown}. Known: {sorted(ADAPTER_REGISTRY)}")

    not_ready = [p for p in requested if p not in READY_PROVIDERS]
    if not_ready:
        raise SystemExit(
            f"Provider(s) {not_ready} are still stubs (no live implementation) — "
            f"see adapters/{not_ready[0].lower()}.py. Only {sorted(READY_PROVIDERS)} "
            "can be included in a live run right now. Querying a stub adapter raises "
            "NotImplementedError by design; this script refuses up front instead of "
            "letting run_batch crash partway through the corpus."
        )

    return [ADAPTER_REGISTRY[p]() for p in requested]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument(
        "--phone-lookup",
        type=Path,
        required=True,
        help="Path to a JSON {token: e164} file from the restricted-access live corpus. Never commit this file.",
    )
    parser.add_argument(
        "--providers",
        type=str,
        default=",".join(sorted(READY_PROVIDERS)),
        help=f"Comma-separated provider ids to query. Default: {sorted(READY_PROVIDERS)}",
    )
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--cache-mode",
        type=str,
        choices=[m.name for m in CacheMode],
        default=CacheMode.LIVE_ONLY.name,
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".cache"),
        help="Required whenever --cache-mode is not LIVE_ONLY.",
    )
    args = parser.parse_args(argv)

    if not args.phone_lookup.exists():
        raise SystemExit(
            f"--phone-lookup file not found: {args.phone_lookup}\n"
            "This file is intentionally never committed to the repository — "
            "supply it out of band from restricted storage."
        )

    cases = load_corpus(args.corpus)
    validate_corpus(cases, strict=True)
    print(f"Loaded and validated {len(cases)} corpus cases from {args.corpus}")

    phone_lookup: dict[str, str] = json.loads(args.phone_lookup.read_text(encoding="utf-8"))

    requested_providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    adapters = _build_adapters(requested_providers)
    print(f"Running providers: {[a.PROVIDER_ID for a in adapters]}")

    config = RunConfig(timeout_seconds=args.timeout, cache_mode=CacheMode[args.cache_mode])
    cache = ObservationCache(args.cache_dir) if config.cache_mode != CacheMode.LIVE_ONLY else None

    observations = run_batch(
        adapters=adapters,
        cases=cases,
        phone_lookup=phone_lookup,
        config=config,
        cache=cache,
    )

    provider_ids = [a.PROVIDER_ID for a in adapters]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.out / run_id

    write_run_metadata(
        run_dir,
        RunMetadata(
            experiment_run_id=run_id,
            corpus_version=_corpus_content_hash(args.corpus),
            provider_adapter_version=";".join(f"{a.PROVIDER_ID}={a.ADAPTER_VERSION}" for a in adapters),
            # Not knowable before querying — providers don't publish a
            # queryable "API version" endpoint as far as public docs show.
            # Revisit once a real adapter surfaces this from a response
            # header/field, per-provider, rather than leaving one run-wide
            # placeholder.
            provider_api_version="n/a",
            git_commit=_git_commit(),
            run_started_at=datetime.now(timezone.utc),
            configuration_hash=_configuration_hash(config, provider_ids),
            provider_set=tuple(provider_ids),
            cache_mode=config.cache_mode.value,
            timeout_seconds=int(config.timeout_seconds),
            repetitions=config.repetitions,
            run_completed_at=datetime.now(timezone.utc),
        ),
    )
    write_observations(run_dir, observations)

    print(f"\nWrote {len(observations)} observations to {run_dir / 'observations.jsonl'}")
    print(f"Next: reputation-experiment score {run_dir} --corpus {args.corpus}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
