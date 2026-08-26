from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RelayMetrics:
    pending_depth: int = 0
    oldest_age_seconds: float = 0
    lease_expiry: int = 0
    attempts: int = 0
    delivery_latency_ms: float = 0
    delivered: int = 0
    failed: int = 0
    lag_seconds: float = 0
    alerts: list[str] = field(default_factory=list)
