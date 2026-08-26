from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ai_dating.recommendations.snapshots import LLM_REASON_CODES, render_reason

RERANK_PROMPT_VERSION = "rerank-v1"
RERANK_PROJECTION_VERSION = "rerank-proj-v1"
RERANK_SYSTEM = (
    "Reorder the supplied candidate IDs for mutual dating compatibility. "
    "Use only the provided fields. Do not infer sensitive traits. "
    "Return JSON only: "
    '{"order":["uuid",...],"reasons":{"uuid":["shared_goal"]}}. '
    "order must be a permutation of every supplied ID and only those IDs. "
    "reasons keys must be those IDs. Allowed reason codes: "
    "shared_goal, prompt_theme, distance_band."
)


@dataclass(frozen=True)
class RerankResult:
    ordered_ids: tuple[UUID, ...]
    reasons: dict[UUID, tuple[str, ...]]


class RerankRejected(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def parse_rerank_payload(payload: object, supplied: list[UUID]) -> RerankResult:
    if not isinstance(payload, dict):
        raise RerankRejected("schema_invalid")
    raw_order = payload.get("order")
    raw_reasons = payload.get("reasons")
    if not isinstance(raw_order, list) or not isinstance(raw_reasons, dict):
        raise RerankRejected("schema_invalid")
    if len(raw_order) != len(supplied):
        raise RerankRejected("schema_invalid")
    try:
        ordered = [UUID(str(item)) for item in raw_order]
    except (ValueError, TypeError) as exc:
        raise RerankRejected("schema_invalid") from exc
    if len(set(ordered)) != len(ordered):
        raise RerankRejected("schema_invalid")
    if set(ordered) != set(supplied):
        raise RerankRejected("schema_invalid")
    reasons: dict[UUID, tuple[str, ...]] = {}
    for key, value in raw_reasons.items():
        try:
            ident = UUID(str(key))
        except (ValueError, TypeError) as exc:
            raise RerankRejected("schema_invalid") from exc
        if ident not in set(supplied):
            raise RerankRejected("schema_invalid")
        if not isinstance(value, list):
            raise RerankRejected("schema_invalid")
        codes = tuple(str(item) for item in value)
        if any(code not in LLM_REASON_CODES for code in codes):
            raise RerankRejected("forbidden_evidence")
        reasons[ident] = codes
    if set(reasons) != set(supplied):
        raise RerankRejected("schema_invalid")
    return RerankResult(ordered_ids=tuple(ordered), reasons=reasons)


def pin_exploration(ordered: list, explore_id: UUID | None, *, limit: int) -> list:
    if explore_id is None or limit <= 0:
        return ordered[:limit]
    explore = [row for row in ordered if row.candidate_id == explore_id]
    rest = [row for row in ordered if row.candidate_id != explore_id]
    if not explore:
        return ordered[:limit]
    head = rest[: max(0, limit - 1)]
    return (head + explore)[:limit]


def reason_for(result: RerankResult, candidate_id: UUID) -> dict | None:
    return render_reason(list(result.reasons.get(candidate_id, ())))
