#!/usr/bin/env python3
"""Isolation guard — EXPERIMENT_PLAN.md §28.

Hard failure, not a convention: scans every source, build, and CI file
under this repository for forbidden production references. A match means
this "removable research module" has stopped being removable — the
experiment must never become a dependency of Pulse or Multi-Port.

Usage:
    python scripts/verify_isolation.py [--root PATH]

Exits non-zero and prints every violation found. Run from CI on every PR
touching this directory (see .github/workflows/reputation-experiment-ci.yml).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

FORBIDDEN = (
    "android.",
    "com.signalgate.",
    "SignalGateDatabase",
    "CallScreeningEngine",
    "SourceEntity",
    "UnifiedEntryEntity",
    "Room",
)

# File types worth scanning for forbidden references. Deliberately broad —
# the spec calls for scanning "source, build files, CI manifests, and
# documentation examples", not just .py files.
SCANNED_SUFFIXES = {".py", ".toml", ".yml", ".yaml", ".md", ".json", ".cfg", ".ini", ".txt"}

# Directories that should never be walked (VCS internals, virtualenvs, caches).
EXCLUDED_DIR_NAMES = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache"}

# This script's own FORBIDDEN tuple necessarily contains the strings it's
# looking for — exclude it from the scan rather than flag itself.
SELF_PATH_SUFFIX = "scripts/verify_isolation.py"

# A line containing this exact marker is exempt, regardless of which
# FORBIDDEN token(s) it contains. This exists because documentation and
# docstrings legitimately need to *name* the forbidden symbols to explain
# what this guard checks for (see adapters/base.py and domain/errors.py) —
# that is not the same thing as importing or using them, and a bare
# substring scan can't tell the two apart on its own. Use sparingly and
# only for genuine prose references, never to silence a real usage.
SUPPRESSION_MARKER = "isolation-guard: allow"


def _iter_scanned_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SCANNED_SUFFIXES:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        if str(path).replace("\\", "/").endswith(SELF_PATH_SUFFIX):
            continue
        yield path


def find_violations(root: Path) -> list[tuple[Path, int, str]]:
    violations: list[tuple[Path, int, str]] = []
    for path in _iter_scanned_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if SUPPRESSION_MARKER in line:
                continue
            for token in FORBIDDEN:
                if token in line:
                    violations.append((path, line_number, token))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)

    violations = find_violations(args.root)

    if violations:
        print("ISOLATION VIOLATION: forbidden production reference(s) found:\n", file=sys.stderr)
        for path, line_number, token in violations:
            print(f"  {path}:{line_number}: contains {token!r}", file=sys.stderr)
        print(
            "\nThis research module must remain fully removable without affecting "
            "Pulse or Multi-Port production behavior. See EXPERIMENT_PLAN.md §2-3.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: no forbidden production references found under {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
