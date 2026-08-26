from __future__ import annotations

import json
from pathlib import Path


def load_manifest(path: str) -> dict | None:
    if not path:
        return None
    file = Path(path)
    if not file.is_file():
        return None
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def manifest_allows(
    payload: dict | None,
    *,
    prompt_version: str,
    model_version: str,
    projection_version: str,
) -> bool:
    if not payload or payload.get("decision") != "pass":
        return False
    return (
        payload.get("prompt_version") == prompt_version
        and payload.get("model_version") == model_version
        and payload.get("projection_version") == projection_version
    )
