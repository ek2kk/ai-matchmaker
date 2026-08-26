from __future__ import annotations

from uuid import UUID, uuid4

from ai_dating.recommendations.ranking import (
    RankFeatures,
    combine,
    cosine_to_unit,
    diversify,
    goal_alignment,
    score_all,
    score_one,
)


def _id(n: int) -> UUID:
    return UUID(int=n)


def test_missing_semantic_renormalizes_over_present_weights():
    score, used = combine(
        {
            "semantic_actor": None,
            "semantic_candidate": None,
            "goal": 1.0,
            "facts": 0.0,
            "distance": 1.0,
            "activity": 1.0,
            "quality": 1.0,
        }
    )
    assert "semantic_actor" not in used
    expected = (0.15 + 0.10 * 0 + 0.10 + 0.10 + 0.05) / 0.50
    assert abs(score - expected) < 1e-9


def test_no_embedding_falls_back_to_non_semantic_score():
    scored = score_one(
        RankFeatures(
            candidate_id=_id(1),
            goal=1.0,
            facts=0.0,
            distance=0.5,
            activity=1.0,
            quality=1.0,
        )
    )
    assert "semantic_actor" not in scored.components
    expected = (0.15 * 1 + 0.10 * 0 + 0.10 * 0.5 + 0.10 * 1 + 0.05 * 1) / 0.50
    assert abs(scored.score - expected) < 1e-9


def test_ties_sort_by_candidate_id():
    left = RankFeatures(candidate_id=_id(2), quality=1.0)
    right = RankFeatures(candidate_id=_id(1), quality=1.0)
    ranked = score_all([left, right])
    assert [row.candidate_id for row in ranked] == [_id(1), _id(2)]


def test_goal_alignment_same_versus_other_allowed():
    assert (
        goal_alignment("dating", "serious_relationship", "serious_relationship") == 1.0
    )
    assert goal_alignment("dating", "serious_relationship", "unsure") == 0.5
    assert goal_alignment("friendship", None, None) == 1.0


def test_cosine_to_unit_maps_minus_one_to_one():
    assert cosine_to_unit(-1.0) == 0.0
    assert cosine_to_unit(1.0) == 1.0
    assert cosine_to_unit(0.0) == 0.5


def test_diversity_penalizes_shared_fact_theme():
    music = frozenset({("interest", "music")})
    travel = frozenset({("interest", "travel")})
    ranked = score_all(
        [
            RankFeatures(candidate_id=_id(1), quality=1.0, self_fact_keys=music),
            RankFeatures(candidate_id=_id(2), quality=0.55, self_fact_keys=music),
            RankFeatures(candidate_id=_id(3), quality=0.50, self_fact_keys=travel),
        ]
    )
    picked = diversify(ranked, uuid4(), slots=2, exploration_slots=0)
    assert [row.candidate_id for row in picked] == [_id(1), _id(3)]


def test_exploration_is_deterministic_for_batch_id():
    rows = [
        RankFeatures(candidate_id=_id(n), quality=1.0 - n * 0.01) for n in range(1, 8)
    ]
    ranked = score_all(rows)
    batch = UUID("11111111-1111-1111-1111-111111111111")
    first = diversify(ranked, batch)
    second = diversify(ranked, batch)
    assert [row.candidate_id for row in first] == [row.candidate_id for row in second]
    assert len(first) == 5
    greedy = {row.candidate_id for row in first[:4]}
    assert first[4].candidate_id not in greedy
