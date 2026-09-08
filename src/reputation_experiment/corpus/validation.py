"""Ground-truth protocol validation.

Enforces the rules from EXPERIMENT_PLAN.md §11 (Ground-Truth Rules) and
docs/GROUND_TRUTH_PROTOCOL.md that a schema check alone can't catch:

  - Ground truth must never be "provider X says it is spam" — that's
    circular validation. A corpus case's ground_truth_source must not name
    one of the candidate providers under comparison.
  - FTC-derived numbers must not be labeled MALICIOUS solely because they
    appear in FTC data (FTC data is unverified consumer complaints). Such
    cases must be PROBABLE/AMBIGUOUS, not VERIFIED MALICIOUS, unless there
    is independent corroboration recorded.
  - Public/committed fixtures must not contain a raw, real, private
    individual's phone number — see scripts/scan_sensitive_data.py for the
    complementary regex-based scan; this module checks the structural
    contract (token field present, no obviously-raw-E.164 value in it).
"""
from __future__ import annotations

from dataclasses import dataclass

from reputation_experiment.domain.classifications import (
    AdjudicationStatus,
    GroundTruthLabel,
)
from reputation_experiment.domain.errors import CorpusValidationError
from reputation_experiment.domain.models import CorpusCase

# Provider identifiers that must never appear as a case's sole
# ground_truth_source — using a candidate provider's own output to
# adjudicate a case that later evaluates that same provider is circular.
CANDIDATE_PROVIDER_IDS = frozenset(
    {"FTC", "HIYA", "NOMOROBO", "CALL_CONTROL", "IPQS", "FIRST_ORION", "TNS"}
)

# Sources whose data is explicitly unverified per its own publisher and
# therefore cannot alone justify a VERIFIED/MALICIOUS-HIGH-confidence label.
UNVERIFIED_SOURCES = frozenset({"FTC", "ftc_dnc_complaint"})


@dataclass(frozen=True)
class ValidationIssue:
    case_id: str
    rule: str
    message: str


def _looks_like_raw_e164(value: str) -> bool:
    """Heuristic: a phone_number_token should be an opaque hex/base64-ish
    string, not something that parses as a plausible E.164 number. This is
    a structural sanity check, not a replacement for
    scripts/scan_sensitive_data.py's broader regex scan across all files.
    """
    digits = "".join(ch for ch in value if ch.isdigit())
    return value.startswith("+") and len(digits) in range(10, 16)


def validate_case(case: CorpusCase) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if _looks_like_raw_e164(case.phone_number_token):
        issues.append(
            ValidationIssue(
                case.case_id,
                "no_raw_numbers",
                "phone_number_token looks like a raw E.164 number, not an opaque token — "
                "see domain.models.hmac_phone_token()",
            )
        )

    if case.ground_truth_source in CANDIDATE_PROVIDER_IDS:
        issues.append(
            ValidationIssue(
                case.case_id,
                "no_circular_validation",
                f"ground_truth_source={case.ground_truth_source!r} names a provider under "
                "comparison — ground truth must be established independently of the "
                "providers being evaluated (EXPERIMENT_PLAN.md §11)",
            )
        )

    if (
        case.ground_truth_source in UNVERIFIED_SOURCES
        and case.ground_truth_label == GroundTruthLabel.MALICIOUS
        and case.adjudication_status == AdjudicationStatus.VERIFIED
    ):
        issues.append(
            ValidationIssue(
                case.case_id,
                "unverified_source_not_verified_truth",
                f"ground_truth_source={case.ground_truth_source!r} is explicitly unverified "
                "consumer-reported data and cannot alone justify adjudication_status=VERIFIED "
                "— use PROBABLE or AMBIGUOUS unless independent corroboration is recorded "
                "(docs/GROUND_TRUTH_PROTOCOL.md)",
            )
        )

    return issues


def validate_corpus(cases: list[CorpusCase], *, strict: bool = True) -> list[ValidationIssue]:
    """Validate every case. If strict, raise on the first batch of issues
    found (used by CI); otherwise return the full issue list for a report.
    """
    all_issues: list[ValidationIssue] = []
    seen_case_ids: set[str] = set()

    for case in cases:
        if case.case_id in seen_case_ids:
            all_issues.append(
                ValidationIssue(case.case_id, "duplicate_case_id", "case_id appears more than once in corpus")
            )
        seen_case_ids.add(case.case_id)
        all_issues.extend(validate_case(case))

    if strict and all_issues:
        summary = "\n".join(f"  - {i.case_id}: [{i.rule}] {i.message}" for i in all_issues)
        raise CorpusValidationError(f"Corpus failed ground-truth-protocol validation:\n{summary}")

    return all_issues
