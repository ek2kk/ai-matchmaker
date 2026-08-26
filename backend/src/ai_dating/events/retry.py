from __future__ import annotations

import random
from datetime import timedelta

ERROR_CODES = frozenset(
    {"schema_invalid", "sink_timeout", "sink_unavailable", "sink_rejected"}
)


def backoff_delay(attempts: int) -> timedelta:
    capped = min(15 * 60, 10 * (2 ** max(0, attempts - 1)))
    jitter = random.uniform(0, capped * 0.1)
    return timedelta(seconds=capped + jitter)
