"""Isolation-guard tests — EXPERIMENT_PLAN.md §28.

Two kinds of check, and both matter:

  1. Positive: scripts/verify_isolation.py and scripts/scan_sensitive_data.py
     currently pass when run against THIS repository. This is a live check
     against the real tree, not a mock — if someone adds a forbidden import
     or a committed secret, this test starts failing before CI even needs
     to run the scripts as a separate step.
  2. Negative: the scripts actually detect a violation when one exists,
     using a disposable temp tree. A guard that always exits 0 would make
     check (1) meaningless, so this repo's test suite must prove the guard
     has teeth, not just that the repo currently happens to be clean.

The scripts under scripts/ are standalone (no package __init__.py), so
they're loaded here via importlib from their file path rather than a
normal package import.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture(scope="module")
def verify_isolation():
    return _load_module("verify_isolation", SCRIPTS_DIR / "verify_isolation.py")


@pytest.fixture(scope="module")
def scan_sensitive_data():
    return _load_module("scan_sensitive_data", SCRIPTS_DIR / "scan_sensitive_data.py")


# --- Positive: the real repo is currently clean ---------------------------


def test_repo_has_no_isolation_violations(verify_isolation):
    violations = verify_isolation.find_violations(REPO_ROOT)
    assert violations == [], (
        "This research repository must remain fully decoupled from "
        "consumer-v1 / Multi-Port production code — see the source "
        f"document's 'Architectural guardrail' section. Violations: {violations}"
    )


def test_repo_has_no_committed_secrets_or_raw_numbers(scan_sensitive_data):
    violations = scan_sensitive_data.scan(REPO_ROOT)
    assert violations == [], f"Sensitive-data scan found: {violations}"


# --- Negative: the guards actually catch a real violation -----------------


def test_isolation_guard_detects_forbidden_reference(tmp_path, verify_isolation):
    """Every token in the guard's own FORBIDDEN tuple must actually be
    caught when it appears in a scanned file. Built from FORBIDDEN itself
    (rather than a hand-written, hardcoded list of example lines) for two
    reasons: it can't silently drift out of sync with the real list, and
    it avoids ever writing a literal forbidden-token match directly into
    this repository's own source (which would trip this very guard when
    it scans this test file, as opposed to the disposable tmp_path files
    used here).
    """
    for i, token in enumerate(verify_isolation.FORBIDDEN):
        offending_file = tmp_path / f"leaky_module_{i}.py"
        offending_file.write_text(f"reference to the token appears here: {token}\n", encoding="utf-8")

    violations = verify_isolation.find_violations(tmp_path)
    found_tokens = {token for _path, _line_no, token in violations}

    assert found_tokens == set(verify_isolation.FORBIDDEN)


def test_isolation_guard_ignores_itself(verify_isolation):
    """The script's own FORBIDDEN tuple necessarily contains the strings it
    scans for — it must exclude its own file rather than flag itself.
    """
    violations = verify_isolation.find_violations(REPO_ROOT)
    self_violations = [
        (path, line_no, token)
        for path, line_no, token in violations
        if path.as_posix().endswith("scripts/verify_isolation.py")
    ]
    assert self_violations == []


def test_secret_scanner_detects_committed_api_key(tmp_path, scan_sensitive_data):
    # Assembled from parts at runtime, on purpose: a literal contiguous
    # "..._API_KEY = ..." assignment in this file's own source would trip
    # scan_sensitive_data.py when it scans this repository for real (see
    # test_repo_has_no_committed_secrets_or_raw_numbers above) — the same
    # self-scan problem as the isolation-guard negative test above, just
    # against the secret scanner's regex instead of the FORBIDDEN tuple.
    key_name = "HIYA" + "_API" + "_KEY"
    key_value = "sk_live_" + "abcdefghijklmnopqrstuvwx"
    offending_file = tmp_path / "config.py"
    offending_file.write_text(f'{key_name} = "{key_value}"\n', encoding="utf-8")

    violations = scan_sensitive_data.scan(tmp_path)

    assert len(violations) >= 1
    assert any(offending_file == path for path, _line_no, _reason in violations)


def test_secret_scanner_detects_raw_phone_number_outside_allowlist(tmp_path, scan_sensitive_data):
    # Same reasoning as above: assembled at runtime, and using exchange
    # 782 (not 555) so this is genuinely outside the NANPA-reserved
    # 555-01XX range and exercises the "real-looking number" path rather
    # than the exemption tested separately below.
    phone_number = "+1" + "2067824123"
    offending_file = tmp_path / "notes.md"
    offending_file.write_text(f"Test case: {phone_number} answered on the third ring.\n", encoding="utf-8")

    violations = scan_sensitive_data.scan(tmp_path)

    assert len(violations) >= 1
    assert any(offending_file == path for path, _line_no, _reason in violations)


def test_secret_scanner_exempts_nanpa_reserved_fictional_range(tmp_path, scan_sensitive_data):
    """555-0100 through 555-0199 (any area code) is NANPA's own reserved
    non-dialable fictional range — a number in it can never be real, so it
    must never fail this scan even outside the fixture allowlist.
    """
    offending_file = tmp_path / "notes.md"
    offending_file.write_text("Test case: +15555550142 answered on the third ring.\n", encoding="utf-8")

    violations = scan_sensitive_data.scan(tmp_path)

    assert violations == []


def test_secret_scanner_allows_the_actual_synthetic_corpus_fixture(scan_sensitive_data):
    """The real corpus/public_synthetic_cases.jsonl and
    tests/fixtures/sample_observations.jsonl files store opaque
    phone_number_token values, not raw E.164 numbers — they must never
    trip this scanner. This is checked against the real files, not a copy.
    """
    violations = scan_sensitive_data.scan(REPO_ROOT)
    fixture_paths = {
        "src/reputation_experiment/corpus/public_synthetic_cases.jsonl",
        "tests/fixtures/sample_observations.jsonl",
    }
    flagged_fixture_violations = [
        v for v in violations if v[0].relative_to(REPO_ROOT).as_posix() in fixture_paths
    ]
    assert flagged_fixture_violations == []
