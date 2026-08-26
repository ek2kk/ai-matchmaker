from __future__ import annotations

import hashlib
import math
import re
import time

from ai_dating.ai.client import ProviderResult
from ai_dating.ai.schema import (
    FACT_CODES,
    REPEATABLE_MAX,
    canonical_value,
    normalize_token,
)


def extract_with_fake(prompt_code: str, answer_text: str) -> ProviderResult:
    del prompt_code
    started = time.perf_counter()
    facts: list[dict] = []
    seen: set[tuple[str, str]] = set()
    counts: dict[str, int] = {}
    tokens = re.findall(r"[^\W\d_][\w]{1,31}", answer_text)
    for raw in tokens:
        token = normalize_token(raw)
        if token is None:
            continue
        for code, spec in FACT_CODES.items():
            if spec["kind"] == "repeatable" and counts.get(code, 0) >= REPEATABLE_MAX:
                continue
            value = canonical_value(code, token)
            if value is None:
                continue
            key = (code, value)
            if key in seen:
                continue
            if spec["kind"] == "ordinal" and any(
                item["fact_code"] == code for item in facts
            ):
                continue
            seen.add(key)
            counts[code] = counts.get(code, 0) + 1
            facts.append(
                {
                    "fact_code": code,
                    "value": value,
                    "confidence": 0.7,
                    "excerpt": answer_text[:120],
                }
            )
    latency_ms = round((time.perf_counter() - started) * 1000)
    return ProviderResult(
        payload={"facts": facts},
        latency_ms=latency_ms,
        token_input=None,
        token_output=None,
    )


def embed_with_fake(text: str, dim: int) -> ProviderResult:
    started = time.perf_counter()
    digest = hashlib.sha256(text.encode()).digest()
    values: list[float] = []
    block_i = 0
    while len(values) < dim:
        block = hashlib.sha256(digest + block_i.to_bytes(4, "big")).digest()
        for byte in block:
            values.append((byte / 127.5) - 1.0)
            if len(values) == dim:
                break
        block_i += 1
    norm = math.sqrt(sum(item * item for item in values)) or 1.0
    vector = [item / norm for item in values]
    return ProviderResult(
        payload=vector,
        latency_ms=round((time.perf_counter() - started) * 1000),
        token_input=None,
        token_output=None,
    )
