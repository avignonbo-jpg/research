#!/usr/bin/env python3
"""Generate a scorecard report from a completed run's observations.jsonl
against a corpus file.

Usage:
    python scripts/generate_report.py --corpus <path> --observations <path> [--out <dir>]

Reads observations.jsonl (one NormalizedObservation per line, as written by
analysis/reports.write_observations) and a corpus file, computes a
DetectionScorecard per provider, and writes metrics.json + a printed table.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reputation_experiment.corpus.loader import load_corpus  # noqa: E402
from reputation_experiment.analysis.metrics import score_provider  # noqa: E402
from reputation_experiment.analysis.reports import (  # noqa: E402
    load_observations,
    render_scorecard_table,
    write_scorecards,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    cases = load_corpus(args.corpus)
    ground_truth_by_case = {c.case_id: c for c in cases}
    observations = load_observations(args.observations)

    providers = sorted({o.provider for o in observations})
    scorecards = [
        score_provider(provider=p, observations=observations, ground_truth_by_case=ground_truth_by_case)
        for p in providers
    ]

    print(render_scorecard_table(scorecards))

    if args.out:
        write_scorecards(args.out, scorecards)
        print(f"\nWrote metrics.json to {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
