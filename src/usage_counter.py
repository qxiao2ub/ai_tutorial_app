from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

# Persistent, no-database public counter.
# The app counts one visit per Streamlit session and keeps the displayed floor at 1,
# so a temporary counter-service failure can never make the UI show 0.
COUNTER_API_BASE = os.getenv(
    "ANISH_COUNTER_API_BASE",
    "https://abacus.jasoncameron.dev",
).rstrip("/")
COUNTER_NAMESPACE = os.getenv(
    "ANISH_COUNTER_NAMESPACE",
    "anish-ai-tutorial-6f4b2c9d",
).strip("/")
COUNTER_KEY = os.getenv(
    "ANISH_COUNTER_KEY",
    "total-app-visits",
).strip("/")
DISPLAY_FLOOR = max(int(os.getenv("ANISH_COUNTER_DISPLAY_FLOOR", "1")), 1)
REQUEST_TIMEOUT = float(os.getenv("ANISH_COUNTER_TIMEOUT", "3.0"))


def _url(action: str) -> str:
    return f"{COUNTER_API_BASE}/{action}/{COUNTER_NAMESPACE}/{COUNTER_KEY}"


def _request_json(url: str) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Anish-AI-Tutorial-App/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _extract_value(payload: dict[str, Any] | None) -> int | None:
    if not payload:
        return None
    candidates = [
        payload.get("value"),
        payload.get("count"),
        payload.get("Count"),
        payload.get("data"),
    ]
    for candidate in candidates:
        if isinstance(candidate, (int, float)):
            return int(candidate)
        if isinstance(candidate, dict):
            nested = candidate.get("value") or candidate.get("count") or candidate.get("Count")
            if isinstance(nested, (int, float)):
                return int(nested)
    return None


def increment_visit() -> tuple[int, bool]:
    """Increment once for a new Streamlit session; return (count, remote_ok)."""
    payload = _request_json(_url("hit"))
    value = _extract_value(payload)
    if value is None:
        return DISPLAY_FLOOR, False
    return max(value, DISPLAY_FLOOR), True


def get_count() -> tuple[int, bool]:
    """Read the persistent count without incrementing it."""
    payload = _request_json(_url("get"))
    value = _extract_value(payload)
    if value is None:
        return DISPLAY_FLOOR, False
    return max(value, DISPLAY_FLOOR), True
