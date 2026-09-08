"""Report assembly — EXPERIMENT_PLAN.md §30-31.

Serializes analysis outputs into the structured results/ layout:

  results/<run-id>/
    run.json
    observations.jsonl
    metrics.json
    agreement.json
    latency.json
    failures.json

Public repository reports contain aggregate statistics only — this module
does not write raw provider responses or the live corpus; callers are
responsible for keeping those in restricted storage per
docs/DATA_HANDLING.md.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from reputation_experiment.analysis.agreement import PairwiseAgreement
from reputation_experiment.analysis.metrics import DetectionScorecard
from reputation_experiment.domain.classifications import NormalizedClassification
from reputation_experiment.domain.models import NormalizedObservation, RunMetadata
from reputation_experiment.domain.normalization import build_observation


def _default_serializer(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "value"):  # Enum
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def write_run_metadata(run_dir: Path, metadata: RunMetadata) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(asdict(metadata), default=_default_serializer, indent=2), encoding="utf-8"
    )


def write_observations(run_dir: Path, observations: list[NormalizedObservation]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "observations.jsonl").open("w", encoding="utf-8") as handle:
        for obs in observations:
            handle.write(json.dumps(asdict(obs), default=_default_serializer) + "\n")


def load_observations(path: Path) -> list[NormalizedObservation]:
    """Read an observations.jsonl file written by write_observations() back
    into NormalizedObservation instances. Symmetric counterpart to
    write_observations — shared by scripts/generate_report.py and cli.py's
    `score` command so there is exactly one deserialization path for this
    format, not two that can drift apart.
    """
    observations: list[NormalizedObservation] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            observations.append(
                build_observation(
                    case_id=raw["case_id"],
                    phone_number_token=raw["phone_number_token"],
                    provider=raw["provider"],
                    normalized_classification=NormalizedClassification(raw["normalized_classification"]),
                    provider_classification=raw.get("provider_classification"),
                    provider_request_id=raw.get("provider_request_id"),
                    category=raw.get("category"),
                    provider_confidence_raw=raw.get("provider_confidence_raw"),
                    normalized_confidence=raw.get("normalized_confidence"),
                    provider_timestamp=(
                        datetime.fromisoformat(raw["provider_timestamp"]) if raw.get("provider_timestamp") else None
                    ),
                    expires_at=(datetime.fromisoformat(raw["expires_at"]) if raw.get("expires_at") else None),
                    latency_ms=raw.get("latency_ms"),
                    http_status=raw.get("http_status"),
                    error_type=raw.get("error_type"),
                    cache_hit=raw.get("cache_hit", False),
                    source_version=raw.get("source_version"),
                    observed_at=datetime.fromisoformat(raw["observed_at"]),
                )
            )
    return observations


def write_scorecards(run_dir: Path, scorecards: list[DetectionScorecard]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = [asdict(s) for s in scorecards]
    (run_dir / "metrics.json").write_text(
        json.dumps(payload, default=_default_serializer, indent=2), encoding="utf-8"
    )


def write_agreement_matrix(run_dir: Path, matrix: list[PairwiseAgreement]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = [asdict(p) for p in matrix]
    (run_dir / "agreement.json").write_text(
        json.dumps(payload, default=_default_serializer, indent=2), encoding="utf-8"
    )


def render_scorecard_table(scorecards: list[DetectionScorecard]) -> str:
    """Plain-text scorecard table for a PR comment / terminal summary —
    NOT a substitute for the full JSON reports, just a human-readable view.
    """
    header = (
        f"{'Provider':<14}{'TPR':>8}{'FPR':>8}{'Prec':>8}{'Recall':>8}{'F1':>8}"
        f"{'Coverage':>10}{'Indeterm':>10}{'Failure':>9}{'N':>8}"
    )
    lines = [header, "-" * len(header)]
    for s in scorecards:
        def fmt(v):
            return f"{v:.3f}" if v is not None else "n/a"

        lines.append(
            f"{s.provider:<14}{fmt(s.tpr):>8}{fmt(s.fpr):>8}{fmt(s.precision):>8}"
            f"{fmt(s.recall):>8}{fmt(s.f1):>8}{s.coverage_rate:>10.1%}"
            f"{s.indeterminate_rate:>10.1%}{s.failure_rate:>9.1%}{s.all_eligible_count:>8}"
        )
    return "\n".join(lines)
