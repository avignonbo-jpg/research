"""Redaction utilities.

Per EXPERIMENT_PLAN.md §25 (Security Requirements — Logging): logs MUST
redact phone numbers, API keys, authorization headers, provider tokens, and
personally identifying metadata. This module centralizes those patterns so
every log call and exception message goes through one redaction path rather
than each call site remembering to do it.
"""
from __future__ import annotations

import re

# E.164-ish and common US-formatted phone number patterns.
_PHONE_PATTERNS = [
    re.compile(r"\+\d{10,15}"),
    re.compile(r"\(\d{3}\)\s?\d{3}[-.\s]?\d{4}"),
    re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"),
]

# Common secret/credential-shaped substrings.
_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([A-Za-z0-9_\-\.]{8,})"),
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([A-Za-z0-9_\-\.]{8,})"),
    re.compile(r"(?i)(token\s*[:=]\s*)([A-Za-z0-9_\-\.]{8,})"),
    re.compile(r"(?i)(secret\s*[:=]\s*)([A-Za-z0-9_\-\.]{8,})"),
]


def redact_phone_numbers(text: str) -> str:
    for pattern in _PHONE_PATTERNS:
        text = pattern.sub("[REDACTED_PHONE]", text)
    return text


def redact_secrets(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: f"{m.group(1)}[REDACTED]", text)
    return text


def redact(text: str) -> str:
    """Apply all redaction passes. Call this on any string headed for a log
    line, exception message, or workflow artifact — never log a raw
    exception or raw request/response body without passing it through here
    first.
    """
    return redact_secrets(redact_phone_numbers(text))
