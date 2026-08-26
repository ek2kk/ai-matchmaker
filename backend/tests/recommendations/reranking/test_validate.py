from uuid import uuid4

from ai_dating.ai.rerank import RerankRejected, parse_rerank_payload, pin_exploration
from ai_dating.recommendations.ranking import RankFeatures, ScoredCandidate


def _scored(ident):
    return ScoredCandidate(
        candidate_id=ident,
        score=1.0,
        components={},
        features=RankFeatures(candidate_id=ident),
    )


def test_parse_rejects_unknown_and_duplicate_ids():
    one, two = uuid4(), uuid4()
    try:
        parse_rerank_payload(
            {"order": [str(one), str(one)], "reasons": {str(one): [], str(two): []}},
            [one, two],
        )
        raise AssertionError("expected reject")
    except RerankRejected as exc:
        assert exc.code == "schema_invalid"
    try:
        parse_rerank_payload(
            {
                "order": [str(one), str(two)],
                "reasons": {str(one): ["shared_goal"], str(two): ["shared_goal"]},
            },
            [one, uuid4()],
        )
        raise AssertionError("expected reject")
    except RerankRejected as exc:
        assert exc.code == "schema_invalid"


def test_parse_rejects_forbidden_evidence():
    one, two = uuid4(), uuid4()
    try:
        parse_rerank_payload(
            {
                "order": [str(two), str(one)],
                "reasons": {
                    str(one): ["exact_location"],
                    str(two): ["shared_goal"],
                },
            },
            [one, two],
        )
        raise AssertionError("expected reject")
    except RerankRejected as exc:
        assert exc.code == "forbidden_evidence"


def test_parse_accepts_permutation():
    one, two = uuid4(), uuid4()
    result = parse_rerank_payload(
        {
            "order": [str(two), str(one)],
            "reasons": {str(one): ["prompt_theme"], str(two): ["shared_goal"]},
        },
        [one, two],
    )
    assert result.ordered_ids == (two, one)


def test_pin_exploration_keeps_last_slot():
    ids = [uuid4() for _ in range(6)]
    pool = [_scored(item) for item in ids]
    explore = ids[-1]
    pinned = pin_exploration(list(reversed(pool)), explore, limit=5)
    assert pinned[-1].candidate_id == explore
    assert len(pinned) == 5
    assert explore not in {row.candidate_id for row in pinned[:-1]}
