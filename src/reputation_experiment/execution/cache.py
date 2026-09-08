"""Observation cache.

Implements the four cache modes from EXPERIMENT_PLAN.md §23:
  LIVE_ONLY                    — never read or write cache
  CACHE_ONLY                   — never query live, error if not cached
  CACHE_THEN_REFRESH           — return cached if present, else query live and cache
  CACHE_WITH_BACKGROUND_REFRESH — return cached immediately if present (even if
                                   stale), and separately trigger a live refresh

This is intentionally a simple file-backed JSON cache, not a production
cache — the experiment doesn't need one, and building a more elaborate cache
here would be effort spent on infrastructure the isolation contract already
says must never touch production systems anyway.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from reputation_experiment.domain.models import NormalizedObservation


class CacheMode(str, Enum):
    LIVE_ONLY = "LIVE_ONLY"
    CACHE_ONLY = "CACHE_ONLY"
    CACHE_THEN_REFRESH = "CACHE_THEN_REFRESH"
    CACHE_WITH_BACKGROUND_REFRESH = "CACHE_WITH_BACKGROUND_REFRESH"


class CacheMissError(Exception):
    """Raised in CACHE_ONLY mode when no cached observation exists."""


def _cache_key(provider: str, phone_number_token: str) -> str:
    return f"{provider}:{phone_number_token}"


def _serialize(observation: NormalizedObservation) -> dict:
    data = asdict(observation)
    for key in ("observed_at", "provider_timestamp", "expires_at"):
        if data.get(key) is not None:
            data[key] = data[key].isoformat() if isinstance(data[key], datetime) else data[key]
    data["normalized_classification"] = observation.normalized_classification.value
    return data


class ObservationCache:
    """File-backed cache. NOT committed to the repository — see
    docs/DATA_HANDLING.md and .gitignore; cache files belong under
    results/ or a path outside the repo entirely, same restriction as raw
    provider responses.
    """

    def __init__(self, cache_dir: str | Path):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, provider: str, phone_number_token: str) -> Path:
        return self._cache_dir / f"{_cache_key(provider, phone_number_token)}.json"

    def get(self, provider: str, phone_number_token: str) -> Optional[dict]:
        path = self._path_for(provider, phone_number_token)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, observation: NormalizedObservation) -> None:
        path = self._path_for(observation.provider, observation.phone_number_token)
        path.write_text(json.dumps(_serialize(observation), indent=2), encoding="utf-8")

    def get_or_fetch(
        self,
        *,
        provider: str,
        phone_number_token: str,
        mode: CacheMode,
        fetch: Callable[[], NormalizedObservation],
    ) -> tuple[dict | NormalizedObservation, bool]:
        """Returns (result, cache_hit). result is the raw cached dict on a
        cache hit, or a fresh NormalizedObservation on a live fetch.
        Deliberately returns the raw dict on hit rather than reconstructing
        a NormalizedObservation, so callers can see exactly what was cached
        without this layer silently reinterpreting it.
        """
        if mode == CacheMode.LIVE_ONLY:
            return fetch(), False

        cached = self.get(provider, phone_number_token)

        if mode == CacheMode.CACHE_ONLY:
            if cached is None:
                raise CacheMissError(
                    f"CACHE_ONLY mode: no cached observation for provider={provider}"
                )
            return cached, True

        if mode == CacheMode.CACHE_THEN_REFRESH:
            if cached is not None:
                return cached, True
            observation = fetch()
            self.put(observation)
            return observation, False

        if mode == CacheMode.CACHE_WITH_BACKGROUND_REFRESH:
            if cached is not None:
                # Caller is responsible for scheduling the background
                # refresh separately (e.g. via execution/runner.py's own
                # queue) — this method's job is only to return the
                # immediately-available cached value without blocking on a
                # live call.
                return cached, True
            observation = fetch()
            self.put(observation)
            return observation, False

        raise ValueError(f"Unknown cache mode: {mode}")
