from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from ai_dating.recommendations.constants import (
    BATCH_SIZE,
    CLUSTER_COSINE,
    DIVERSITY_PENALTY,
    EXPLORATION_SLOTS,
    WEIGHTS,
)


@dataclass(frozen=True)
class RankFeatures:
    candidate_id: UUID
    semantic_actor: float | None = None
    semantic_candidate: float | None = None
    goal: float | None = None
    facts: float | None = None
    distance: float | None = None
    activity: float | None = None
    quality: float | None = None
    self_embedding: tuple[float, ...] | None = None
    self_fact_keys: frozenset[tuple[str, str]] = frozenset()


@dataclass(frozen=True)
class ScoredCandidate:
    candidate_id: UUID
    score: float
    components: dict[str, float]
    features: RankFeatures


def cosine_similarity(
    left: list[float] | tuple[float, ...],
    right: list[float] | tuple[float, ...],
) -> float | None:
    if len(left) != len(right) or not left:
        return None
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right, strict=True):
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm <= 0.0 or right_norm <= 0.0:
        return None
    return dot / ((left_norm**0.5) * (right_norm**0.5))


def cosine_to_unit(similarity: float) -> float:
    return max(0.0, min(1.0, (similarity + 1.0) / 2.0))


def jaccard(left: set[tuple[str, str]], right: set[tuple[str, str]]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    return len(left & right) / len(union)


def fact_overlap(
    actor_self: set[tuple[str, str]],
    actor_desired: set[tuple[str, str]],
    candidate_self: set[tuple[str, str]],
    candidate_desired: set[tuple[str, str]],
) -> float:
    return (
        jaccard(actor_desired, candidate_self) + jaccard(candidate_desired, actor_self)
    ) / 2.0


def goal_alignment(
    search_mode: str, actor_goal: str | None, candidate_goal: str | None
) -> float:
    if search_mode != "dating":
        return 1.0
    if actor_goal is not None and actor_goal == candidate_goal:
        return 1.0
    return 0.5


def distance_decay(km: float, limit_km: float) -> float:
    if limit_km <= 0:
        return 0.0
    if km >= limit_km:
        return 0.0
    return 1.0 - (km / limit_km)


def activity_freshness(age_days: float, window_days: float) -> float:
    if window_days <= 0 or age_days >= window_days:
        return 0.0
    return 1.0 - (age_days / window_days)


def profile_quality(completion_percent: int) -> float:
    return max(0.0, min(1.0, completion_percent / 100.0))


def combine(components: dict[str, float | None]) -> tuple[float, dict[str, float]]:
    present = {name: value for name, value in components.items() if value is not None}
    weight_sum = sum(WEIGHTS[name] for name in present)
    if weight_sum <= 0:
        return 0.0, {}
    used = {name: present[name] for name in present}
    score = sum(WEIGHTS[name] * used[name] for name in used) / weight_sum
    return score, used


def score_one(features: RankFeatures) -> ScoredCandidate:
    score, used = combine(
        {
            "semantic_actor": features.semantic_actor,
            "semantic_candidate": features.semantic_candidate,
            "goal": features.goal,
            "facts": features.facts,
            "distance": features.distance,
            "activity": features.activity,
            "quality": features.quality,
        }
    )
    return ScoredCandidate(
        candidate_id=features.candidate_id,
        score=score,
        components=used,
        features=features,
    )


def score_all(rows: list[RankFeatures]) -> list[ScoredCandidate]:
    scored = [score_one(row) for row in rows]
    return sorted(scored, key=lambda row: (-row.score, str(row.candidate_id)))


def _is_near_duplicate(
    candidate: ScoredCandidate, selected: list[ScoredCandidate]
) -> bool:
    cand_facts = candidate.features.self_fact_keys
    cand_embed = candidate.features.self_embedding
    for other in selected:
        if cand_facts and (cand_facts & other.features.self_fact_keys):
            return True
        if cand_embed is None or other.features.self_embedding is None:
            continue
        similarity = cosine_similarity(cand_embed, other.features.self_embedding)
        if similarity is not None and similarity >= CLUSTER_COSINE:
            return True
    return False


def _adjusted(candidate: ScoredCandidate, selected: list[ScoredCandidate]) -> float:
    if selected and _is_near_duplicate(candidate, selected):
        return candidate.score - DIVERSITY_PENALTY
    return candidate.score


def _hash_unit(batch_id: UUID, candidate_id: UUID) -> float:
    digest = sha256(f"{batch_id}:{candidate_id}".encode()).digest()
    value = int.from_bytes(digest[:8], "big") / 2**64
    return min(max(value, 1e-16), 1.0 - 1e-16)


def _explore_pick(
    pool: list[ScoredCandidate], batch_id: UUID
) -> ScoredCandidate | None:
    if not pool:
        return None
    weighted = [row for row in pool if row.score > 0]
    source = weighted or pool
    best = source[0]
    best_key = -1.0
    for row in source:
        weight = max(row.score, 1e-9)
        key = _hash_unit(batch_id, row.candidate_id) ** (1.0 / weight)
        if key > best_key or (
            key == best_key and str(row.candidate_id) < str(best.candidate_id)
        ):
            best = row
            best_key = key
    return best


def diversify(
    scored: list[ScoredCandidate],
    batch_id: UUID,
    *,
    slots: int = BATCH_SIZE,
    exploration_slots: int = EXPLORATION_SLOTS,
) -> list[ScoredCandidate]:
    ordered = sorted(scored, key=lambda row: (-row.score, str(row.candidate_id)))
    greedy_n = max(0, slots - exploration_slots)
    if len(ordered) <= greedy_n:
        return ordered
    selected: list[ScoredCandidate] = []
    remaining = list(ordered)
    while remaining and len(selected) < greedy_n:
        pick = min(
            remaining,
            key=lambda row: (-_adjusted(row, selected), str(row.candidate_id)),
        )
        selected.append(pick)
        remaining = [row for row in remaining if row.candidate_id != pick.candidate_id]
    if exploration_slots and remaining and len(selected) < slots:
        explore_pool = [
            row
            for row in ordered
            if row.candidate_id not in {item.candidate_id for item in selected}
        ][:20]
        picked = _explore_pick(explore_pool, batch_id)
        if picked is not None:
            selected.append(picked)
    return selected
