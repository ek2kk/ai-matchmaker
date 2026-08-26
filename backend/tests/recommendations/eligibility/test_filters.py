from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from tests.recommendations.helpers import seed_exposure, seed_person, seed_ready_item

from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.recommendations.eligibility import (
    eligible_candidates,
    eligible_sql,
    load_actor,
)

pytestmark = [pytest.mark.postgres]


@pytest.fixture
def db():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    engine = create_sync_engine(settings)
    with Session(engine) as session:
        yield session
        session.rollback()


def _pair(db: Session, **candidate_kw):
    actor_acc, _actor_profile, _actor_prefs = seed_person(db, gender="woman")
    params = {"gender": "man", "accepted": ["woman"]}
    params.update(candidate_kw)
    cand_acc, _cand_profile, _cand_prefs = seed_person(db, **params)
    loaded = load_actor(db, actor_acc.account_id)
    assert loaded is not None
    return loaded[3], cand_acc.account_id


def _ids(db, actor):
    now = datetime(2026, 8, 26, 12, tzinfo=UTC)
    return {row.account_id for row in eligible_candidates(db, actor, now=now)}


def test_reciprocal_happy_path(db: Session):
    actor, candidate_id = _pair(db)
    assert candidate_id in _ids(db, actor)


def test_gender_must_match_both_ways(db: Session):
    actor, candidate_id = _pair(db, accepted=["man"])
    assert candidate_id not in _ids(db, actor)


def test_age_must_match_both_ways(db: Session):
    actor, too_old = _pair(db, dob_year=1980)
    assert too_old not in _ids(db, actor)
    actor, narrow = _pair(db, age_min=21, age_max=22)
    assert narrow not in _ids(db, actor)


def test_distance_uses_tighter_reciprocal_limit(db: Session):
    actor, far = _pair(db, lat=56.75, lon=37.62, max_distance_km=500)
    assert far not in _ids(db, actor)
    actor, tight = _pair(db, lat=55.76, lon=37.62, max_distance_km=1)
    assert tight not in _ids(db, actor)


def test_goals_must_intersect_when_dating(db: Session):
    actor, candidate_id = _pair(
        db, goal="friends_with_benefits", goals=["friends_with_benefits"]
    )
    assert candidate_id not in _ids(db, actor)


def test_search_mode_must_match(db: Session):
    actor, candidate_id = _pair(
        db, search_mode="friendship", goal="serious_relationship", goals=[]
    )
    assert candidate_id not in _ids(db, actor)


def test_activity_visibility_moderation_privacy(db: Session):
    stale = datetime(2026, 8, 26, 12, tzinfo=UTC) - timedelta(days=40)
    actor, inactive = _pair(db, last_active=stale)
    assert inactive not in _ids(db, actor)
    actor, hidden = _pair(db, visibility="hidden")
    assert hidden not in _ids(db, actor)
    actor, pending = _pair(db, moderation="pending")
    assert pending not in _ids(db, actor)
    actor, paused = _pair(db, status="paused")
    assert paused not in _ids(db, actor)
    actor, private = _pair(db, discoverable=False)
    assert private not in _ids(db, actor)
    actor, no_ai = _pair(db, allow_ai_matching=False)
    assert no_ai not in _ids(db, actor)


def test_prior_exposure_excludes_pair(db: Session):
    actor, candidate_id = _pair(db)
    seed_exposure(db, actor.account_id, candidate_id)
    assert candidate_id not in _ids(db, actor)


def test_prior_like_excludes_pair(db: Session):
    from ai_dating.matching.models import Like
    from ai_dating.recommendations.models import RecommendationAction

    actor_acc, _actor_profile, _actor_prefs = seed_person(db, gender="woman")
    cand_acc, cand_profile, _cand_prefs = seed_person(
        db, gender="man", accepted=["woman"]
    )
    item = seed_ready_item(db, actor_acc, cand_acc, cand_profile)
    now = datetime(2026, 8, 26, 12, tzinfo=UTC)
    action = RecommendationAction(
        action_id=uuid4(),
        recommendation_item_id=item.recommendation_item_id,
        actor_account_id=actor_acc.account_id,
        action="like",
        reason_code=None,
        created_at=now,
    )
    db.add(action)
    db.flush()
    db.add(
        Like(
            like_id=uuid4(),
            actor_account_id=actor_acc.account_id,
            subject_account_id=cand_acc.account_id,
            recommendation_item_id=item.recommendation_item_id,
            recommendation_action_id=action.action_id,
            state="active",
            created_at=now,
            updated_at=now,
        )
    )
    db.flush()
    loaded = load_actor(db, actor_acc.account_id)
    assert loaded is not None
    assert cand_acc.account_id not in _ids(db, loaded[3])


def test_either_direction_block_excludes_pair(db: Session):
    from ai_dating.safety.models import Block

    actor, candidate_id = _pair(db)
    db.add(
        Block(
            block_id=uuid4(),
            blocker_account_id=candidate_id,
            blocked_account_id=actor.account_id,
            reason_code="other",
            created_at=datetime(2026, 8, 26, 12, tzinfo=UTC),
            ended_at=None,
        )
    )
    db.flush()
    assert candidate_id not in _ids(db, actor)


def test_missing_approved_photo_excludes_pair(db: Session):
    actor, candidate_id = _pair(db, photo=False)
    assert candidate_id not in _ids(db, actor)


def test_explain_uses_distance_function(db: Session):
    actor, _candidate_id = _pair(db)
    now = datetime(2026, 8, 26, 12, tzinfo=UTC)
    stmt = eligible_sql(actor, now=now)
    sql = str(stmt.compile(dialect=db.get_bind().dialect))
    assert "dwithin" in sql.lower()
    assert "hnsw" not in sql.lower()
    explained = db.execute(stmt).all()
    assert explained is not None
    rows = eligible_candidates(db, actor, now=now)
    assert rows
