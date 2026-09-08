"""Nomorobo adapter — STUB.

Nomorobo exposes a developer API for phone number checks (spam/robocall
reputation derived from honeypot-style observed call behavior). Not
implemented in this pass: no credentials or live response schema were
available. See hiya.py's docstring for the pattern to follow when wiring
this up for real.
"""
from __future__ import annotations

from reputation_experiment.adapters.base import NotImplementedAdapter
from reputation_experiment.domain.normalization import ConfidenceInterpretation


class NomoroboAdapter(NotImplementedAdapter):
    PROVIDER_ID = "NOMOROBO"
    CONFIDENCE_INTERPRETATION = ConfidenceInterpretation.NOT_DOCUMENTED
    ADAPTER_VERSION = "0.0.0-stub"
