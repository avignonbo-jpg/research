#!/usr/bin/env python3
"""Sensitive-data scanner — EXPERIMENT_PLAN.md §25-26.

Fails the build if any tracked file contains something that looks like a
committed API key/secret, or a raw E.164 phone number outside the explicit
allowlist of known-synthetic fixture files.

Usage:
    python scripts/scan_sensitive_data.py [--root PATH]

This is a heuristic regex scan, not a guarantee — it complements (does not
replace) the structural check in corpus/validation.py and code review.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXCLUDED_DIR_NAMES = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache", "results"}

SCANNED_SUFFIXES = {".py", ".toml", ".yml", ".yaml", ".md", ".json", ".cfg", ".ini", ".txt", ".jsonl", ".env"}

# Files explicitly reviewed and approved to contain synthetic (fictional,
# 555-exchange / reserved) phone numbers for schema/CI testing. Anything
# outside this allowlist that looks like a raw phone number fails the scan.
SYNTHETIC_FIXTURE_ALLOWLIST = {
    "src/reputation_experiment/corpus/public_synthetic_cases.jsonl",
    "tests/fixtures/sample_observations.jsonl",
}

SECRET_PATTERNS = [
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}['\"]?"),
    re.compile(r"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9_\-\.]{16,}"),
    re.compile(r"(?i)secret\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}['\"]?"),
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id shape, in case CI creds leak in here by accident
]

# Deliberately narrower than execution/redaction.py's patterns: this scanner
# is checking for RAW E.164-shaped numbers being committed, so it should not
# false-positive on things like version numbers or ordinary prose numbers.
RAW_PHONE_PATTERN = re.compile(r"\+1\d{10}\b")

# NANPA reserves NXX-555-0100 through NXX-555-0199 (any area code) as
# non-dialable fictional numbers for exactly this purpose — testing,
# documentation, and media use. A number in this range can never be a real
# subscriber number, so it is exempt from the raw-phone-number check
# everywhere in this repo, not just in the fixture allowlist below. The
# allowlist still exists as a second layer for any fixture file that needs
# a broader exemption than just this reserved range.
RESERVED_FICTIONAL_PHONE_PATTERN = re.compile(r"\+1\d{3}55501\d{2}\b")


def _raw_phone_violations_on_line(line: str) -> bool:
    """True if the line contains a raw-looking E.164 number that is NOT in
    the NANPA-reserved fictional range.
    """
    for match in RAW_PHONE_PATTERN.finditer(line):
        if not RESERVED_FICTIONAL_PHONE_PATTERN.fullmatch(match.group(0)):
            return True
    return False


def _iter_scanned_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SCANNED_SUFFIXES:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        yield path


def scan(root: Path) -> list[tuple[Path, int, str]]:
    violations: list[tuple[Path, int, str]] = []

    for path in _iter_scanned_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    violations.append((path, line_number, "possible committed secret"))

            if relative not in SYNTHETIC_FIXTURE_ALLOWLIST and _raw_phone_violations_on_line(line):
                violations.append((path, line_number, "possible raw E.164 phone number outside fixture allowlist"))

    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)

    violations = scan(args.root)

    if violations:
        print("SENSITIVE DATA SCAN FAILED:\n", file=sys.stderr)
        for path, line_number, reason in violations:
            print(f"  {path}:{line_number}: {reason}", file=sys.stderr)
        return 1

    print(f"OK: no committed secrets or unapproved raw phone numbers found under {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
