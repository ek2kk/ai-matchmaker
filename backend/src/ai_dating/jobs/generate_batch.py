from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import structlog
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.ai.client import embedding_model_version
from ai_dating.ai.schema import PROJECTION_SCHEMA_VERSION
from ai_dating.config import Settings
from ai_dating.jobs.claim import ClaimedJob
from ai_dating.privacy.models import BackgroundJob
from ai_dating.profiles.facts import matching_facts
from ai_dating.profiles.models import DatingPreferences, Profile, ProfileEmbedding
from ai_dating.recommendations.constants import (
    ACTIVITY_DAYS,
    BATCH_SCHEMA_VERSION,
    BATCH_SIZE,
    BATCH_TTL_HOURS,
    ELIGIBILITY_VERSION,
    FEATURE_SCHEMA_VERSION,
    ITEM_SCHEMA_VERSION,
    JOB_TYPE_GENERATE,
    POLICY_VERSION,
    RANKER_VERSION,
    RERANK_POOL,
    RETRIEVE_LIMIT,
    SCORE_LIMIT,
)
from ai_dating.recommendations.eligibility import (
    ActorSnapshot,
    EligibilityError,
    EligibleCandidate,
    current_embeddings,
    eligible_candidates,
    load_actor,
)
from ai_dating.recommendations.enqueue import enqueue_generation
from ai_dating.recommendations.models import RecommendationBatch, RecommendationItem
from ai_dating.recommendations.ranking import (
    RankFeatures,
    ScoredCandidate,
    activity_freshness,
    cosine_similarity,
    cosine_to_unit,
    distance_decay,
    diversify,
    fact_overlap,
    goal_alignment,
    profile_quality,
    score_all,
)
from ai_dating.recommendations.snapshots import item_profile_snapshot, render_reason

log = structlog.get_logger("ai_dating.jobs")


def _now() -> datetime:
    return datetime.now(UTC)


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(60, 2 ** max(1, attempts)))


def _mark(
    db: Session,
    job_id: UUID,
    *,
    status: str,
    error_code: str | None = None,
    run_after: datetime | None = None,
    commit: bool = True,
) -> None:
    row = db.get(BackgroundJob, job_id)
    if row is None:
        return
    now = _now()
    row.status = status
    row.last_error_code = error_code
    row.lease_until = None
    row.updated_at = now
    if run_after is not None:
        row.run_after = run_after
    if commit:
        db.commit()


def _quantize(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(value, 5)))


def _fact_keys(facts: list, side: str) -> set[tuple[str, str]]:
    return {(row.fact_code, row.value) for row in facts if row.profile_side == side}


def _retrieve(
    actor_desired: list[float] | None,
    candidates: list[EligibleCandidate],
    self_by_profile: dict[UUID, ProfileEmbedding],
) -> tuple[list[EligibleCandidate], str]:
    if actor_desired is None:
        return list(candidates), "no_embedding"
    with_vec: list[tuple[float, EligibleCandidate]] = []
    without: list[EligibleCandidate] = []
    for row in candidates:
        embedding = self_by_profile.get(row.profile_id)
        if embedding is None:
            without.append(row)
            continue
        similarity = cosine_similarity(actor_desired, embedding.embedding)
        distance = 1.0 if similarity is None else 1.0 - similarity
        with_vec.append((distance, row))
    with_vec.sort(key=lambda item: (item[0], str(item[1].account_id)))
    picked = [row for _distance, row in with_vec[:RETRIEVE_LIMIT]][:SCORE_LIMIT]
    if len(picked) < SCORE_LIMIT:
        picked.extend(without[: SCORE_LIMIT - len(picked)])
    return picked, "none"


def _features(
    actor: ActorSnapshot,
    actor_facts: list,
    actor_self: list[float] | None,
    actor_desired: list[float] | None,
    candidate: EligibleCandidate,
    cand_facts: list,
    self_embed: ProfileEmbedding | None,
    desired_embed: ProfileEmbedding | None,
    now: datetime,
) -> RankFeatures:
    semantic_actor = None
    semantic_candidate = None
    self_vector = None
    if actor_desired is not None and self_embed is not None:
        similarity = cosine_similarity(actor_desired, self_embed.embedding)
        if similarity is not None:
            semantic_actor = cosine_to_unit(similarity)
            self_vector = tuple(self_embed.embedding)
    if actor_self is not None and desired_embed is not None:
        similarity = cosine_similarity(desired_embed.embedding, actor_self)
        if similarity is not None:
            semantic_candidate = cosine_to_unit(similarity)
    limit_km = float(min(actor.max_distance_km, candidate.max_distance_km))
    age_days = max(0.0, (now - candidate.last_active_at).total_seconds() / 86400.0)
    return RankFeatures(
        candidate_id=candidate.account_id,
        semantic_actor=semantic_actor,
        semantic_candidate=semantic_candidate,
        goal=goal_alignment(
            actor.search_mode,
            actor.relationship_goal_code,
            candidate.relationship_goal_code,
        ),
        facts=fact_overlap(
            _fact_keys(actor_facts, "self"),
            _fact_keys(actor_facts, "desired_partner"),
            _fact_keys(cand_facts, "self"),
            _fact_keys(cand_facts, "desired_partner"),
        ),
        distance=distance_decay(candidate.distance_km, limit_km),
        activity=activity_freshness(age_days, float(ACTIVITY_DAYS)),
        quality=profile_quality(candidate.completion_percent),
        self_embedding=self_vector,
        self_fact_keys=frozenset(_fact_keys(cand_facts, "self")),
    )


def _snapshot(
    actor: ActorSnapshot,
    eligible: list[EligibleCandidate],
    considered: list[EligibleCandidate],
    fallback_mode: str,
    quota_slot: int,
    retrieve_fallback: str,
) -> dict:
    return {
        "policy_version": POLICY_VERSION,
        "eligibility_version": ELIGIBILITY_VERSION,
        "ranker_version": RANKER_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "quota_slot": quota_slot,
        "fallback_mode": fallback_mode,
        "retrieve_fallback": retrieve_fallback,
        "actor": {
            "account_id": str(actor.account_id),
            "profile_id": str(actor.profile_id),
            "profile_version": actor.profile_version,
            "preferences_version": actor.preferences_version,
        },
        "eligible_count": len(eligible),
        "considered_account_ids": [str(row.account_id) for row in considered],
    }


def _reason_snapshot(scored: ScoredCandidate) -> dict | None:
    codes: list[str] = []
    components = scored.components
    if components.get("goal", 0) >= 0.5:
        codes.append("shared_goal")
    if components.get("facts", 0) >= 0.3:
        codes.append("prompt_theme")
    if components.get("semantic_actor", 0) >= 0.5:
        codes.append("similar_intent")
    if components.get("distance", 0) >= 0.5:
        codes.append("distance_band")
    return render_reason(codes)


def _profile_snapshot(db: Session, candidate: EligibleCandidate) -> dict | None:
    account = db.get(Account, candidate.account_id)
    profile = db.get(Profile, candidate.profile_id)
    if account is None or profile is None or account.date_of_birth is None:
        return None
    return item_profile_snapshot(db, account, profile)


def _persist(
    db: Session,
    *,
    actor: ActorSnapshot,
    generation_key: str,
    fallback_mode: str,
    eligible: list[EligibleCandidate],
    considered: list[EligibleCandidate],
    picked: list[tuple[ScoredCandidate, EligibleCandidate, str | None]],
    now: datetime,
    batch_id: UUID,
    quota_slot: int,
    retrieve_fallback: str,
    prompt_version: str | None = None,
    model_version: str | None = None,
    reasons: dict | None = None,
) -> None:
    expires = now + timedelta(hours=BATCH_TTL_HOURS)
    db.execute(
        insert(RecommendationBatch)
        .values(
            recommendation_batch_id=batch_id,
            owner_account_id=actor.account_id,
            status="ready",
            generation_key=generation_key,
            batch_schema_version=BATCH_SCHEMA_VERSION,
            input_snapshot=_snapshot(
                actor,
                eligible,
                considered,
                fallback_mode,
                quota_slot,
                retrieve_fallback,
            ),
            eligibility_version=ELIGIBILITY_VERSION,
            ranker_version=RANKER_VERSION,
            prompt_version=prompt_version,
            model_version=model_version,
            fallback_mode=fallback_mode,
            candidate_count=len(eligible),
            item_count=len(picked),
            created_at=now,
            ready_at=now,
            expires_at=expires,
        )
        .on_conflict_do_nothing(index_elements=["generation_key"])
    )
    existing = db.scalar(
        select(RecommendationBatch).where(
            RecommendationBatch.generation_key == generation_key
        )
    )
    if existing is None or existing.recommendation_batch_id != batch_id:
        return
    for rank, (scored, candidate, embed_version) in enumerate(picked, start=1):
        db.add(
            RecommendationItem(
                recommendation_item_id=uuid4(),
                recommendation_batch_id=batch_id,
                candidate_account_id=candidate.account_id,
                item_schema_version=ITEM_SCHEMA_VERSION,
                rank=rank,
                semantic_actor=_quantize(scored.components.get("semantic_actor")),
                semantic_candidate=_quantize(
                    scored.components.get("semantic_candidate")
                ),
                goal_alignment=_quantize(scored.components.get("goal")),
                prompt_fact_overlap=_quantize(scored.components.get("facts")),
                distance_decay=_quantize(scored.components.get("distance")),
                activity_freshness=_quantize(scored.components.get("activity")),
                profile_quality=_quantize(scored.components.get("quality")),
                final_score=_quantize(scored.score) or Decimal("0"),
                public_profile_snapshot=_profile_snapshot(db, candidate),
                reason_snapshot=(
                    reasons.get(candidate.account_id)
                    if reasons is not None
                    else _reason_snapshot(scored)
                ),
                candidate_profile_version=candidate.profile_version,
                candidate_embedding_version=embed_version,
                created_at=now,
            )
        )


def _rerank_or_fallback(
    db: Session,
    settings: Settings,
    job: ClaimedJob,
    actor: ActorSnapshot,
    pool: list[ScoredCandidate],
    explore_id,
    retrieve_fallback: str,
) -> tuple[list[ScoredCandidate], str, str | None, str | None, dict | None]:
    from decimal import Decimal as Dec
    from json import dumps

    from sqlalchemy import func

    from ai_dating.ai.client import (
        ProviderError,
        yandex_chat_completion,
        yandex_model_version,
    )
    from ai_dating.ai.models import AiOperation
    from ai_dating.ai.rerank import (
        RERANK_PROJECTION_VERSION,
        RERANK_PROMPT_VERSION,
        RERANK_SYSTEM,
        RerankRejected,
        parse_rerank_payload,
        pin_exploration,
        reason_for,
    )
    from ai_dating.recommendations.snapshots import rerank_projection

    heuristic = pin_exploration(pool, explore_id, limit=BATCH_SIZE)
    by_scored = {row.candidate_id: row for row in pool}
    projections = []
    for row in pool:
        account = db.get(Account, row.candidate_id)
        profile = db.scalar(
            select(Profile).where(Profile.account_id == row.candidate_id)
        )
        if account is None or profile is None or account.date_of_birth is None:
            return heuristic, "no_llm", None, None, None
        snap = item_profile_snapshot(db, account, profile)
        projections.append(
            {
                "candidate_id": str(row.candidate_id),
                **rerank_projection(snap, row.components),
            }
        )
    user = dumps(
        {
            "projection_version": RERANK_PROJECTION_VERSION,
            "actor": {
                "search_mode": actor.search_mode,
                "relationship_goal_code": actor.relationship_goal_code,
                "city_code": actor.city_code,
            },
            "candidates": projections,
        },
        separators=(",", ":"),
    )
    input_tokens = max(1, len(user) // 4)
    model_name = yandex_model_version(settings)
    now = _now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    spent = db.scalar(
        select(func.coalesce(func.sum(AiOperation.estimated_cost_rub), 0)).where(
            AiOperation.operation_type == "rerank",
            AiOperation.created_at >= start,
        )
    )
    spent_val = float(spent or 0)
    est = (input_tokens / 1000.0) * settings.rerank_input_price_per_1k_rub + (
        settings.rerank_max_output_tokens / 1000.0
    ) * settings.rerank_output_price_per_1k_rub
    status = "provider_error"
    safety = "skipped"
    latency = None
    token_in = input_tokens
    token_out = None
    cost = None
    try:
        if (
            input_tokens > settings.rerank_max_input_tokens
            or est > settings.rerank_max_cost_rub
        ):
            raise RerankRejected("token_cap")
        if spent_val + est > settings.rerank_daily_cost_rub:
            raise RerankRejected("cost_cap")
        result = yandex_chat_completion(
            settings,
            system=RERANK_SYSTEM,
            user=user,
            timeout=settings.rerank_timeout_seconds,
            max_tokens=settings.rerank_max_output_tokens,
        )
        latency = result.latency_ms
        token_in = result.token_input or input_tokens
        token_out = result.token_output
        if (
            token_in > settings.rerank_max_input_tokens
            or (token_out or 0) > settings.rerank_max_output_tokens
        ):
            raise RerankRejected("token_cap")
        cost = (token_in / 1000.0) * settings.rerank_input_price_per_1k_rub + (
            (token_out or 0) / 1000.0
        ) * settings.rerank_output_price_per_1k_rub
        if cost > settings.rerank_max_cost_rub:
            raise RerankRejected("cost_cap")
        parsed = parse_rerank_payload(
            result.payload, [row.candidate_id for row in pool]
        )
        ordered = [by_scored[ident] for ident in parsed.ordered_ids]
        selected = pin_exploration(ordered, explore_id, limit=BATCH_SIZE)
        reasons = {ident: reason_for(parsed, ident) for ident in parsed.ordered_ids}
        status = "succeeded"
        safety = "passed"
        db.add(
            AiOperation(
                ai_operation_id=uuid4(),
                job_id=job.job_id,
                operation_type="rerank",
                prompt_version=RERANK_PROMPT_VERSION,
                model_version=model_name,
                source_entity_type="account",
                source_entity_id=actor.account_id,
                source_version=actor.profile_version,
                latency_ms=latency,
                token_input=token_in,
                token_output=token_out,
                estimated_cost_rub=Dec(str(round(cost, 4))),
                result_status=status,
                safety_result=safety,
                created_at=_now(),
            )
        )
        return selected, retrieve_fallback, RERANK_PROMPT_VERSION, model_name, reasons
    except (ProviderError, RerankRejected) as exc:
        code = getattr(exc, "code", str(exc) or "provider_error")
        if code in {"schema_invalid"}:
            status, safety = "schema_invalid", "rejected"
        elif code in {"forbidden_evidence"}:
            status, safety = "safety_rejected", "rejected"
        elif code in {
            "timeout",
            "rate_limited",
            "provider_error",
            "provider_unconfigured",
        }:
            status, safety = "provider_error", "skipped"
        else:
            status, safety = "schema_invalid", "rejected"
        db.add(
            AiOperation(
                ai_operation_id=uuid4(),
                job_id=job.job_id,
                operation_type="rerank",
                prompt_version=RERANK_PROMPT_VERSION,
                model_version=model_name,
                source_entity_type="account",
                source_entity_id=actor.account_id,
                source_version=actor.profile_version,
                latency_ms=latency,
                token_input=token_in,
                token_output=token_out,
                estimated_cost_rub=None if cost is None else Dec(str(round(cost, 4))),
                result_status=status,
                safety_result=safety,
                created_at=_now(),
            )
        )
        log.info("rerank_fallback", error_code=code, job_id=str(job.job_id))
        return heuristic, "no_llm", RERANK_PROMPT_VERSION, model_name, None


def process_generate_job(db: Session, settings: Settings, job: ClaimedJob) -> None:
    payload = job.payload
    try:
        account_id = UUID(str(payload["account_id"]))
        profile_version = int(payload["profile_version"])
        preferences_version = int(payload["preferences_version"])
        policy_version = str(payload.get("policy_version") or POLICY_VERSION)
        generation_key = str(payload["generation_key"])
        trigger_code = str(payload.get("trigger_code") or "profile_updated")
        quota_slot = int(payload.get("quota_slot") or 0)
    except (KeyError, ValueError, TypeError):
        _mark(db, job.job_id, status="failed", error_code="schema_invalid")
        return
    if job.job_type != JOB_TYPE_GENERATE:
        _mark(db, job.job_id, status="failed", error_code="schema_invalid")
        return
    loaded = load_actor(db, account_id)
    if loaded is None:
        _mark(db, job.job_id, status="succeeded", error_code="stale")
        return
    _account, profile, prefs, actor = loaded
    now = _now()
    if (
        profile.version != profile_version
        or prefs.version != preferences_version
        or policy_version != POLICY_VERSION
    ):
        enqueue_generation(
            db,
            profile=profile,
            prefs=prefs,
            now=now,
            trigger_code="profile_updated",
        )
        _mark(db, job.job_id, status="succeeded", error_code="stale")
        return
    existing = db.scalar(
        select(RecommendationBatch).where(
            RecommendationBatch.generation_key == generation_key
        )
    )
    if existing is not None:
        if existing.item_count > 0:
            _mark(db, job.job_id, status="succeeded")
            return
        db.execute(
            delete(RecommendationItem).where(
                RecommendationItem.recommendation_batch_id
                == existing.recommendation_batch_id
            )
        )
        db.delete(existing)
        db.flush()
    try:
        eligible = eligible_candidates(db, actor, now=now)
    except EligibilityError as exc:
        _mark(db, job.job_id, status="failed", error_code=exc.code)
        return
    model_version = embedding_model_version(settings)
    actor_embeds = current_embeddings(
        db,
        [
            (actor.profile_id, actor.profile_version, "self"),
            (actor.profile_id, actor.profile_version, "desired_partner"),
        ],
        model_version=model_version,
        projection_schema_version=PROJECTION_SCHEMA_VERSION,
    )
    actor_self = actor_embeds.get((actor.profile_id, "self"))
    actor_desired = actor_embeds.get((actor.profile_id, "desired_partner"))
    actor_self_vec = None if actor_self is None else actor_self.embedding
    actor_desired_vec = None if actor_desired is None else actor_desired.embedding
    cand_specs = [
        (row.profile_id, row.profile_version, kind)
        for row in eligible
        for kind in ("self", "desired_partner")
    ]
    cand_embeds = current_embeddings(
        db,
        cand_specs,
        model_version=model_version,
        projection_schema_version=PROJECTION_SCHEMA_VERSION,
    )
    self_by_profile = {
        profile_id: row
        for (profile_id, kind), row in cand_embeds.items()
        if kind == "self"
    }
    considered, fallback = _retrieve(actor_desired_vec, eligible, self_by_profile)
    if actor_desired_vec is None:
        fallback = "no_embedding"
    actor_facts = matching_facts(db, actor.profile_id)
    facts_by_profile: dict[UUID, list] = {}
    if considered:
        from ai_dating.profiles.models import ProfileFact

        fact_rows = list(
            db.scalars(
                select(ProfileFact).where(
                    ProfileFact.profile_id.in_([row.profile_id for row in considered]),
                    ProfileFact.superseded_at.is_(None),
                    ProfileFact.review_state == "confirmed",
                    ProfileFact.visibility.in_(("matching_only", "eligible_only")),
                )
            )
        )
        for row in fact_rows:
            facts_by_profile.setdefault(row.profile_id, []).append(row)
    features = [
        _features(
            actor,
            actor_facts,
            actor_self_vec,
            actor_desired_vec,
            candidate,
            facts_by_profile.get(candidate.profile_id, []),
            cand_embeds.get((candidate.profile_id, "self")),
            cand_embeds.get((candidate.profile_id, "desired_partner")),
            now,
        )
        for candidate in considered
    ]
    scored = score_all(features)
    batch_id = uuid4()
    pool = diversify(scored, batch_id, slots=RERANK_POOL) if scored else []
    explore_id = pool[-1].candidate_id if len(pool) > 1 else None
    from ai_dating.ai.rerank import pin_exploration

    selected = pin_exploration(pool, explore_id, limit=BATCH_SIZE)
    retrieve_fallback = fallback
    prompt_version = None
    model_name = None
    llm_reasons = None
    if settings.rerank_enabled and pool:
        selected, fallback, prompt_version, model_name, llm_reasons = (
            _rerank_or_fallback(
                db,
                settings,
                job,
                actor,
                pool,
                explore_id,
                retrieve_fallback,
            )
        )
    by_id = {row.account_id: row for row in considered}
    refreshed = load_actor(db, account_id)
    if refreshed is None:
        _mark(db, job.job_id, status="succeeded", error_code="stale")
        return
    _account, profile, prefs, actor_now = refreshed
    if (
        actor_now.profile_version != actor.profile_version
        or actor_now.preferences_version != actor.preferences_version
    ):
        enqueue_generation(
            db,
            profile=profile,
            prefs=prefs,
            now=now,
            trigger_code="profile_updated",
        )
        _mark(db, job.job_id, status="succeeded", error_code="stale")
        return
    picked_rows: list[tuple[ScoredCandidate, EligibleCandidate, str | None]] = []
    for item in selected:
        candidate = by_id[item.candidate_id]
        live = db.get(Profile, candidate.profile_id)
        live_prefs = db.get(DatingPreferences, candidate.account_id)
        if (
            live is None
            or live_prefs is None
            or live.version != candidate.profile_version
            or live_prefs.version != candidate.preferences_version
        ):
            retry = job.attempts < job.max_attempts
            _mark(
                db,
                job.job_id,
                status="queued" if retry else "failed",
                error_code="source_drift",
                run_after=now + _backoff(job.attempts) if retry else None,
            )
            return
        embed = cand_embeds.get((candidate.profile_id, "self"))
        picked_rows.append(
            (item, candidate, None if embed is None else embed.model_version)
        )
    if not picked_rows:
        fallback = "insufficient_supply"
    _persist(
        db,
        actor=actor,
        generation_key=generation_key,
        fallback_mode=fallback,
        eligible=eligible,
        considered=considered,
        picked=picked_rows,
        now=now,
        batch_id=batch_id,
        quota_slot=quota_slot,
        retrieve_fallback=retrieve_fallback,
        prompt_version=prompt_version,
        model_version=model_name,
        reasons=llm_reasons,
    )
    _mark(db, job.job_id, status="succeeded", commit=False)
    db.commit()
    log.info(
        "recommendation_batch_ok",
        job_id=str(job.job_id),
        item_count=len(picked_rows),
        fallback_mode=fallback,
        trigger_code=trigger_code,
    )
