"""Classification vocabulary.

Per EXPERIMENT_PLAN.md §7: the experiment MUST distinguish provider-native
classifications (never discarded — see NormalizedObservation.provider_classification)
from a deliberately small normalized vocabulary used for cross-provider analysis.

UNKNOWN, UNAVAILABLE, and ERROR are kept distinct on purpose. A provider failing
to answer is not evidence that a number is clean — folding those into LEGITIMATE
would let an unreliable provider look artificially "safe". This mirrors the same
principle already established in SignalGate Pulse's CallTier.SECURITY_FAILURE:
exception != ALLOW, and (here) provider failure != LEGITIMATE.
"""
from __future__ import annotations

from enum import Enum


class NormalizedClassification(str, Enum):
    """The small, fixed vocabulary every adapter must map its provider's
    native classification into. See domain/normalization.py for the mapping
    rules and adapters/*.py for provider-specific mappings.
    """

    SPAM = "SPAM"
    SCAM = "SCAM"
    FRAUD = "FRAUD"
    ROBOCALL = "ROBOCALL"
    TELEMARKETING = "TELEMARKETING"
    SUSPICIOUS = "SUSPICIOUS"
    LEGITIMATE = "LEGITIMATE"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


# Binary evaluation policy (EXPERIMENT_PLAN.md, "Binary evaluation policy").
# Frozen mapping, defined separately from native-category evaluation so a
# provider that returns UNKNOWN or errors frequently cannot look artificially
# clean by being silently folded into LEGITIMATE.
MALICIOUS_CLASSIFICATIONS = frozenset(
    {
        NormalizedClassification.SPAM,
        NormalizedClassification.SCAM,
        NormalizedClassification.FRAUD,
        NormalizedClassification.ROBOCALL,
        NormalizedClassification.TELEMARKETING,
    }
)

LEGITIMATE_CLASSIFICATIONS = frozenset({NormalizedClassification.LEGITIMATE})

# SUSPICIOUS is reported separately and excluded from the primary binary
# calculation unless a preregistered threshold maps it — never auto-included
# here. Excluding it from both sets below means it must be handled
# explicitly by callers (see analysis/metrics.py BinaryEvaluationPolicy).
INDETERMINATE_CLASSIFICATIONS = frozenset({NormalizedClassification.UNKNOWN})

FAILURE_CLASSIFICATIONS = frozenset(
    {NormalizedClassification.UNAVAILABLE, NormalizedClassification.ERROR}
)


def is_malicious(classification: NormalizedClassification) -> bool:
    return classification in MALICIOUS_CLASSIFICATIONS


def is_legitimate(classification: NormalizedClassification) -> bool:
    return classification in LEGITIMATE_CLASSIFICATIONS


def is_failure(classification: NormalizedClassification) -> bool:
    """True for UNAVAILABLE/ERROR — a provider that could not answer.

    Callers MUST check this before treating a missing/failed observation as
    equivalent to LEGITIMATE. See analysis/combinations.py for how failures
    are excluded from UNION/INTERSECTION/MAJORITY votes rather than counted
    as a legitimate vote.
    """
    return classification in FAILURE_CLASSIFICATIONS


class GroundTruthLabel(str, Enum):
    """§ Ground-truth protocol: kept separate from provider classifications
    to avoid circular validation (a provider's own output must never be used
    to adjudicate the ground truth used to score that same provider).
    """

    MALICIOUS = "MALICIOUS"
    LEGITIMATE = "LEGITIMATE"
    AMBIGUOUS = "AMBIGUOUS"
    SPOOFED_NUMBER = "SPOOFED_NUMBER"


class GroundTruthConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AdjudicationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PROBABLE = "PROBABLE"
    DISPUTED = "DISPUTED"
    EXPIRED = "EXPIRED"


class CorpusClass(str, Enum):
    """§9 Test Corpus required classes A-G."""

    KNOWN_MALICIOUS = "KNOWN_MALICIOUS"
    LEGITIMATE_BUSINESS = "LEGITIMATE_BUSINESS"
    ORDINARY_PERSONAL = "ORDINARY_PERSONAL"
    RECENTLY_REPORTED = "RECENTLY_REPORTED"
    HISTORICAL_RECOVERED = "HISTORICAL_RECOVERED"
    SPOOFING_EXAMPLE = "SPOOFING_EXAMPLE"
    GRAY_ZONE = "GRAY_ZONE"
