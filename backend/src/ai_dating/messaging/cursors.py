from __future__ import annotations

import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime
from uuid import UUID

from ai_dating.errors import AppError


def encode_cursor(ts: datetime, item_id: UUID) -> str:
    payload = json.dumps(
        {
            "v": 1,
            "t": ts.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "id": str(item_id),
        },
        separators=(",", ":"),
    )
    return urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(after: str) -> tuple[datetime, UUID]:
    try:
        padded = after + "=" * (-len(after) % 4)
        data = json.loads(urlsafe_b64decode(padded))
        if data.get("v") != 1:
            raise ValueError
        raw = str(data["t"])
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw), UUID(str(data["id"]))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise AppError(422, "validation_error", "Invalid request.") from None
