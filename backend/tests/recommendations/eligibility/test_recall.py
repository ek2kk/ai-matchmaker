from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from tests.recommendations.helpers import seed_person

from ai_dating.ai.schema import PROJECTION_SCHEMA_VERSION
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.jobs.generate_batch import _retrieve
from ai_dating.recommendations.constants import SCORE_LIMIT
from ai_dating.recommendations.eligibility import (
    current_embeddings,
    eligible_candidates,
    eligible_sql,
    load_actor,
)
from ai_dating.recommendations.ranking import cosine_similarity

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


def test_exact_cosine_recall_and_latency(db: Session):
    lat = 71.0 + (uuid4().int % 10_000) / 10_000.0
    lon = 21.0 + (uuid4().int % 10_000) / 10_000.0
    actor_acc, _actor_profile, _prefs = seed_person(
        db, gender="woman", lat=lat, lon=lon, max_distance_km=5
    )
    for index in range(12):
        seed_person(
            db,
            gender="man",
            accepted=["woman"],
            lat=lat + index * 0.0002,
            lon=lon,
            max_distance_km=5,
        )
    loaded = load_actor(db, actor_acc.account_id)
    assert loaded is not None
    actor = loaded[3]
    now = datetime(2026, 8, 26, 12, tzinfo=UTC)
    stmt = eligible_sql(actor, now=now)
    sql = str(stmt.compile(dialect=db.get_bind().dialect)).lower()
    assert "dwithin" in sql
    assert "hnsw" not in sql
    started = perf_counter()
    eligible = eligible_candidates(db, actor, now=now)
    elapsed_ms = (perf_counter() - started) * 1000
    assert elapsed_ms < 500
    assert len(eligible) >= 12
    embeds = current_embeddings(
        db,
        [(row.profile_id, row.profile_version, "self") for row in eligible]
        + [(actor.profile_id, actor.profile_version, "desired_partner")],
        model_version="gte-base",
        projection_schema_version=PROJECTION_SCHEMA_VERSION,
    )
    desired = embeds[(actor.profile_id, "desired_partner")]
    self_by_profile = {
        profile_id: row for (profile_id, kind), row in embeds.items() if kind == "self"
    }
    picked, _mode = _retrieve(desired.embedding, eligible, self_by_profile)
    brute = sorted(
        eligible,
        key=lambda row: (
            -(
                cosine_similarity(
                    desired.embedding, self_by_profile[row.profile_id].embedding
                )
                or -1.0
            ),
            str(row.account_id),
        ),
    )[:SCORE_LIMIT]
    assert {row.account_id for row in picked} == {row.account_id for row in brute}
