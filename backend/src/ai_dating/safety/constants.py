from __future__ import annotations

REASON_CODES = frozenset({"harassment", "spam", "fake_profile", "underage", "other"})
SEVERITY = {
    "underage": "high",
    "harassment": "high",
    "spam": "medium",
    "fake_profile": "medium",
    "other": "medium",
}
DEFAULT_REASON = "other"
