from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.recommendations.helpers import seed_exposure, seed_person

from ai_dating.ai.client import ProviderError, ProviderResult
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.jobs.generate_batch import _rerank_or_fallback
from ai_dating.recommendations.models import RecommendationItem
from ai_dating.recommendations.ranking import RankFeatures, ScoredCandidate
from ai_dating.recommendations.snapshots import erase_candidate_snapshots

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


def _pool(ids):
    return [
        ScoredCandidate(
            candidate_id=item,
            score=1.0 - index * 0.01,
            components={"goal": 1.0},
            features=RankFeatures(candidate_id=item),
        )
        for index, item in enumerate(ids)
    ]


def test_provider_failure_keeps_heuristic_order(db: Session, monkeypatch):
    settings = load_settings()
    actor_acc, actor_profile, _prefs = seed_person(db, gender="woman")
    people = [
        seed_person(db, gender="man", accepted=["woman"], lat=55.75 + index * 0.001)
        for index in range(3)
    ]
    ids = [row[0].account_id for row in people]
    pool = _pool(ids)

    def boom(*_args, **_kwargs):
        raise ProviderError("timeout")

    monkeypatch.setattr("ai_dating.ai.client.yandex_chat_completion", boom)

    class Job:
        job_id = uuid4()

    from ai_dating.recommendations.eligibility import load_actor

    loaded = load_actor(db, actor_acc.account_id)
    assert loaded is not None
    selected, fallback, _prompt, _model, reasons = _rerank_or_fallback(
        db,
        settings,
        Job(),
        loaded[3],
        pool,
        ids[-1],
        "none",
    )
    assert fallback == "no_llm"
    assert reasons is None
    assert [row.candidate_id for row in selected[:-1]] == ids[:4][: len(selected) - 1]
    assert selected[-1].candidate_id == ids[-1]


def test_malformed_payload_falls_back(db: Session, monkeypatch):
    settings = load_settings()
    actor_acc, _profile, _prefs = seed_person(db, gender="woman")
    people = [
        seed_person(db, gender="man", accepted=["woman"], lat=55.76 + index * 0.001)
        for index in range(2)
    ]
    ids = [row[0].account_id for row in people]
    monkeypatch.setattr(
        "ai_dating.ai.client.yandex_chat_completion",
        lambda *_a, **_k: ProviderResult(
            payload={"order": ["nope"]}, latency_ms=5, token_input=10, token_output=2
        ),
    )

    class Job:
        job_id = uuid4()

    from ai_dating.recommendations.eligibility import load_actor

    loaded = load_actor(db, actor_acc.account_id)
    assert loaded is not None
    _selected, fallback, _p, _m, reasons = _rerank_or_fallback(
        db, settings, Job(), loaded[3], _pool(ids), ids[-1], "none"
    )
    assert fallback == "no_llm"
    assert reasons is None


def test_erase_nulls_snapshot_content(db: Session):
    owner, _op, _ = seed_person(db, gender="woman")
    cand, _cp, _ = seed_person(db, gender="man", accepted=["woman"])
    seed_exposure(db, owner.account_id, cand.account_id)
    item = db.scalar(
        select(RecommendationItem).where(
            RecommendationItem.candidate_account_id == cand.account_id
        )
    )
    assert item is not None
    item.public_profile_snapshot = {"display_name": "secret", "photos": []}
    item.reason_snapshot = {"text": "private"}
    db.flush()
    erased = erase_candidate_snapshots(db, cand.account_id)
    assert erased == 1
    db.refresh(item)
    assert item.public_profile_snapshot is None
    assert item.reason_snapshot is None
    assert item.candidate_account_id == cand.account_id
    assert item.candidate_profile_version == 1
