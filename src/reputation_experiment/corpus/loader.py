"""Corpus loading.

Reads a corpus file (JSONL — one CorpusCase per line) into CorpusCase
objects. See corpus/validation.py for schema and ground-truth-protocol
checks, which should always run immediately after loading and before any
case is used in a run.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterator

from reputation_experiment.domain.classifications import (
    AdjudicationStatus,
    CorpusClass,
    GroundTruthConfidence,
    GroundTruthLabel,
)
from reputation_experiment.domain.errors import CorpusValidationError
from reputation_experiment.domain.models import CorpusCase


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_case(raw: dict, *, line_number: int, source_path: Path) -> CorpusCase:
    try:
        return CorpusCase(
            case_id=raw["case_id"],
            phone_number_token=raw["phone_number_token"],
            corpus_class=CorpusClass(raw["corpus_class"]),
            ground_truth_label=GroundTruthLabel(raw["ground_truth_label"]),
            ground_truth_confidence=GroundTruthConfidence(raw["ground_truth_confidence"]),
            ground_truth_source=raw["ground_truth_source"],
            ground_truth_observed_at=_parse_datetime(raw["ground_truth_observed_at"]),
            adjudication_status=AdjudicationStatus(raw["adjudication_status"]),
            ground_truth_expires_at=(
                _parse_datetime(raw["ground_truth_expires_at"])
                if raw.get("ground_truth_expires_at")
                else None
            ),
            ground_truth_category=raw.get("ground_truth_category"),
            notes=raw.get("notes"),
        )
    except (KeyError, ValueError) as exc:
        raise CorpusValidationError(
            f"{source_path}:{line_number}: malformed corpus case — {exc}"
        ) from exc


def load_corpus(path: str | Path) -> list[CorpusCase]:
    """Load and parse a JSONL corpus file. Does NOT run ground-truth-protocol
    validation (see corpus/validation.py:validate_corpus) — callers should
    run that separately so parsing failures and protocol violations are
    reported distinctly.
    """
    source_path = Path(path)
    cases: list[CorpusCase] = []
    with source_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            cases.append(_parse_case(raw, line_number=line_number, source_path=source_path))
    return cases


def iter_corpus(path: str | Path) -> Iterator[CorpusCase]:
    """Streaming variant for large corpora."""
    source_path = Path(path)
    with source_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            yield _parse_case(json.loads(line), line_number=line_number, source_path=source_path)
