"""Command-line entry point.

    reputation-experiment validate-corpus <path>
    reputation-experiment score <run-dir>

Deliberately thin — this wires together corpus validation and reporting for
convenience; the Manual Experiment Run workflow (.github/workflows) is the
actual live-run trigger and injects provider credentials at that layer, not
here.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reputation_experiment.analysis.metrics import score_provider
from reputation_experiment.analysis.reports import (
    load_observations,
    render_scorecard_table,
    write_scorecards,
)
from reputation_experiment.corpus.loader import load_corpus
from reputation_experiment.corpus.validation import validate_corpus
from reputation_experiment.domain.errors import CorpusValidationError


def _cmd_validate_corpus(args: argparse.Namespace) -> int:
    try:
        cases = load_corpus(args.path)
        validate_corpus(cases, strict=True)
    except CorpusValidationError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(cases)} cases in {args.path} passed schema + ground-truth-protocol validation")
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    observations_path = args.run_dir / "observations.jsonl"
    if not observations_path.exists():
        print(f"FAILED: {observations_path} does not exist", file=sys.stderr)
        return 1

    cases = load_corpus(args.corpus)
    ground_truth_by_case = {c.case_id: c for c in cases}
    observations = load_observations(observations_path)

    providers = sorted({o.provider for o in observations})
    scorecards = [
        score_provider(provider=p, observations=observations, ground_truth_by_case=ground_truth_by_case)
        for p in providers
    ]

    print(render_scorecard_table(scorecards))
    write_scorecards(args.run_dir, scorecards)
    print(f"\nWrote {args.run_dir / 'metrics.json'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reputation-experiment")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-corpus", help="Validate a corpus file against schema + ground-truth protocol"
    )
    validate_parser.add_argument("path", type=Path)
    validate_parser.set_defaults(func=_cmd_validate_corpus)

    score_parser = subparsers.add_parser(
        "score",
        help="Score a completed run's observations.jsonl against a corpus, writing metrics.json into run-dir",
    )
    score_parser.add_argument("run_dir", type=Path, help="Directory containing observations.jsonl (per analysis/reports.py's results/<run-id>/ layout)")
    score_parser.add_argument("--corpus", type=Path, required=True)
    score_parser.set_defaults(func=_cmd_score)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
