"""Seed 10 local demo accounts for matching tests. Idempotent by login."""

from __future__ import annotations

from datetime import UTC, date, datetime
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.ai.client import embedding_model_version
from ai_dating.ai.embed import run_embedding
from ai_dating.ai.projection import build_projection
from ai_dating.ai.schema import EMBED_KINDS, PROJECTION_SCHEMA_VERSION
from ai_dating.auth.crypto import hash_password, request_fingerprint
from ai_dating.auth.models import AuthIdentity, AuthPasswordCredential
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.jobs.claim import claim_jobs
from ai_dating.jobs.generate_batch import process_generate_job
from ai_dating.media.images import render_derivative
from ai_dating.media.models import ProfilePhoto
from ai_dating.media.storage import open_store
from ai_dating.onboarding.models import CalibrationSession, OnboardingStepCompletion
from ai_dating.onboarding.vocab import (
    CALIBRATION_VERSION,
    FLOW_VERSION,
    STEP_CODES,
)
from ai_dating.privacy.models import PRIVACY_POLICY_VERSION, Consent, PrivacyControls
from ai_dating.profiles.models import (
    DatingPreferences,
    Profile,
    ProfileAnswer,
    ProfileEmbedding,
    ProfileFact,
)
from ai_dating.profiles.service import location_point
from ai_dating.recommendations.constants import JOB_TYPE_GENERATE
from ai_dating.recommendations.enqueue import enqueue_generation

PASSWORD = "demo-pass-1"
GOALS = [
    "serious_relationship",
    "friends_with_benefits",
    "unsure",
]
CONSENTS = ("terms_privacy", "dating_visibility", "ai_matching", "calibration")
PROMPTS = (
    "self_about",
    "self_weekend",
    "self_people",
    "partner_who",
    "partner_together",
    "partner_relationship",
)

# 5 women + 5 men, Moscow, reciprocal dating. Prefs accept all goals so
# opposite-gender pairs stay eligible; primary goal still varies for ranking.
PEOPLE: tuple[dict, ...] = (
    {
        "login": "demo.anna",
        "name": "Анна",
        "gender": "woman",
        "dob": date(2002, 3, 12),
        "goal": "serious_relationship",
        "area": "moscow_central",
        "lat": 55.7558,
        "lon": 37.6173,
        "answers": {
            "self_about": "Люблю книги, музеи и долгие разговоры за чаем.",
            "self_weekend": "Суббота в Третьяковке, воскресенье с книгой дома.",
            "self_people": "Ценю спокойствие, юмор и умение слушать.",
            "partner_who": "Ищу спокойного мужчину, с которым можно молчать и спорить.",
            "partner_together": "Прогулки по центру, кино, домашние ужины.",
            "partner_relationship": "Хочу серьёзные отношения без спешки.",
        },
        "self_facts": [
            ("interest", "books"),
            ("interest", "art"),
            ("interest", "cinema"),
            ("social_style", "introvert"),
            ("communication_style", "warm"),
            ("occupation_domain", "education"),
        ],
        "want_facts": [
            ("interest", "books", "prefer"),
            ("date_preference", "walking", "prefer"),
            ("communication_style", "warm", "strong_preference"),
        ],
    },
    {
        "login": "demo.maria",
        "name": "Мария",
        "gender": "woman",
        "dob": date(2002, 7, 4),
        "goal": "unsure",
        "area": "moscow_north",
        "lat": 55.835,
        "lon": 37.62,
        "answers": {
            "self_about": "Музыка, концерты и друзья. Работаю в дизайне.",
            "self_weekend": "Живой концерт или бар с подругами, иногда кино.",
            "self_people": "Люблю лёгкость и людей, которые не боятся странных тем.",
            "partner_who": "Кто-то весёлый, не обязательно сразу про семью.",
            "partner_together": "Концерты, спонтанные поездки, ночные разговоры.",
            "partner_relationship": "Пока не уверена, хочу познакомиться и понять.",
        },
        "self_facts": [
            ("interest", "music"),
            ("interest", "cinema"),
            ("nightlife_preference", "high"),
            ("social_style", "ambivert"),
            ("occupation_domain", "design"),
            ("spontaneity", "high"),
        ],
        "want_facts": [
            ("interest", "music", "prefer"),
            ("date_preference", "cinema", "prefer"),
            ("energy_level", "high", "prefer"),
        ],
    },
    {
        "login": "demo.elena",
        "name": "Елена",
        "gender": "woman",
        "dob": date(2001, 11, 21),
        "goal": "serious_relationship",
        "area": "moscow_west",
        "lat": 55.74,
        "lon": 37.48,
        "answers": {
            "self_about": "Готовлю, путешествую, работаю в бизнесе. Люблю гостей.",
            "self_weekend": "Рынок, ужин для друзей, иногда короткий выезд.",
            "self_people": "Прямота и тепло. Не люблю игры.",
            "partner_who": "Мужчина, с которым можно строить быт и ездить вдвоём.",
            "partner_together": "Рестораны, короткие поездки, готовить вместе.",
            "partner_relationship": "Семья и стабильность важнее приключений.",
        },
        "self_facts": [
            ("interest", "cooking"),
            ("interest", "travel"),
            ("travel_frequency", "occasional"),
            ("social_style", "extrovert"),
            ("values", "family"),
            ("occupation_domain", "business"),
        ],
        "want_facts": [
            ("interest", "travel", "prefer"),
            ("date_preference", "restaurants", "prefer"),
            ("values", "stability", "strong_preference"),
        ],
    },
    {
        "login": "demo.olga",
        "name": "Ольга",
        "gender": "woman",
        "dob": date(2002, 5, 8),
        "goal": "friends_with_benefits",
        "area": "moscow_south",
        "lat": 55.65,
        "lon": 37.62,
        "answers": {
            "self_about": "Зал, пробежки, вечера с друзьями. Семью пока не ищу.",
            "self_weekend": "Тренировка утром, вечером бар или танцы.",
            "self_people": "Энергия, тело, без тяжёлых разговоров на первом свидании.",
            "partner_who": "Спортивный, лёгкий на подъём, без давления про отношения.",
            "partner_together": "Зал, короткие поездки, домашние вечера.",
            "partner_relationship": "Хочу близко и свободно, без обязательств.",
        },
        "self_facts": [
            ("interest", "fitness"),
            ("fitness_level", "high"),
            ("nightlife_preference", "high"),
            ("energy_level", "high"),
            ("occupation_domain", "healthcare"),
        ],
        "want_facts": [
            ("interest", "fitness", "strong_preference"),
            ("date_preference", "home_evening", "prefer"),
            ("fitness_level", "high", "prefer"),
        ],
    },
    {
        "login": "demo.daria",
        "name": "Дарья",
        "gender": "woman",
        "dob": date(2004, 1, 30),
        "goal": "unsure",
        "area": "moscow_east",
        "lat": 55.75,
        "lon": 37.78,
        "answers": {
            "self_about": "Игры, код, научная фантастика. Работаю в IT.",
            "self_weekend": "Кооп с друзьями или хакатон, иногда выставка.",
            "self_people": "Нерды, которые умеют объяснять сложное просто.",
            "partner_who": "Кто-то из технологий или просто любопытный.",
            "partner_together": "Игры, прогулки, иногда кино фантастика.",
            "partner_relationship": "Пока смотрю, что получится.",
        },
        "self_facts": [
            ("interest", "gaming"),
            ("interest", "technology"),
            ("social_style", "introvert"),
            ("occupation_domain", "software_engineering"),
            ("communication_style", "direct"),
        ],
        "want_facts": [
            ("interest", "gaming", "prefer"),
            ("interest", "technology", "prefer"),
            ("date_preference", "home_evening", "prefer"),
        ],
    },
    {
        "login": "demo.ivan",
        "name": "Иван",
        "gender": "man",
        "dob": date(2001, 2, 14),
        "goal": "serious_relationship",
        "area": "moscow_central",
        "lat": 55.76,
        "lon": 37.63,
        "answers": {
            "self_about": "Историк по образованию, читаю много, гуляю по центру.",
            "self_weekend": "Книжный, кофе, иногда театр.",
            "self_people": "Тихие умные разговоры важнее шумных вечеринок.",
            "partner_who": "Спокойная девушка, которой интересны книги и город.",
            "partner_together": "Прогулки, музеи, готовить простые ужины.",
            "partner_relationship": "Хочу отношения, которые растут медленно.",
        },
        "self_facts": [
            ("interest", "books"),
            ("interest", "travel"),
            ("social_style", "introvert"),
            ("communication_style", "warm"),
            ("occupation_domain", "education"),
        ],
        "want_facts": [
            ("interest", "books", "strong_preference"),
            ("date_preference", "walking", "prefer"),
            ("communication_style", "warm", "prefer"),
        ],
    },
    {
        "login": "demo.pavel",
        "name": "Павел",
        "gender": "man",
        "dob": date(2001, 9, 18),
        "goal": "unsure",
        "area": "moscow_north",
        "lat": 55.84,
        "lon": 37.61,
        "answers": {
            "self_about": "Играю на гитаре, хожу на концерты, снимаю короткое видео.",
            "self_weekend": "Концерт или студия, иногда спонтанная поездка.",
            "self_people": "Лёгкость, музыкальный вкус, без пафоса.",
            "partner_who": "Девушка, с которой не скучно и можно молчать под музыку.",
            "partner_together": "Концерты, кино, ночные прогулки.",
            "partner_relationship": "Не тороплю ярлыки.",
        },
        "self_facts": [
            ("interest", "music"),
            ("interest", "cinema"),
            ("social_style", "ambivert"),
            ("occupation_domain", "arts"),
            ("spontaneity", "high"),
        ],
        "want_facts": [
            ("interest", "music", "prefer"),
            ("date_preference", "cinema", "prefer"),
            ("energy_level", "medium", "prefer"),
        ],
    },
    {
        "login": "demo.dmitry",
        "name": "Дмитрий",
        "gender": "man",
        "dob": date(2000, 6, 2),
        "goal": "serious_relationship",
        "area": "moscow_west",
        "lat": 55.735,
        "lon": 37.49,
        "answers": {
            "self_about": "Готовлю, коллекционирую винил, работаю в бизнесе.",
            "self_weekend": "Рынок, ужин дома, иногда выставка.",
            "self_people": "Тепло и ясность. Не люблю неопределённость годами.",
            "partner_who": "Девушка, с которой хочется строить дом, не только даты.",
            "partner_together": "Рестораны, готовка, короткие поездки.",
            "partner_relationship": "Семья и стабильность.",
        },
        "self_facts": [
            ("interest", "cooking"),
            ("interest", "art"),
            ("values", "family"),
            ("social_style", "extrovert"),
            ("occupation_domain", "business"),
            ("travel_frequency", "occasional"),
        ],
        "want_facts": [
            ("interest", "cooking", "prefer"),
            ("date_preference", "restaurants", "prefer"),
            ("values", "family", "strong_preference"),
        ],
    },
    {
        "login": "demo.nikita",
        "name": "Никита",
        "gender": "man",
        "dob": date(2001, 4, 25),
        "goal": "friends_with_benefits",
        "area": "moscow_south",
        "lat": 55.655,
        "lon": 37.615,
        "answers": {
            "self_about": "Тренер, много спорта, мало офиса. Не ищу брак.",
            "self_weekend": "Зал, пробежка, вечером друзья.",
            "self_people": "Тело, энергия, без драмы.",
            "partner_who": "Спортивная, свободная, без разговоров про свадьбу.",
            "partner_together": "Тренировки, короткие поездки, домашние вечера.",
            "partner_relationship": "Близко и без обязательств.",
        },
        "self_facts": [
            ("interest", "fitness"),
            ("fitness_level", "high"),
            ("energy_level", "high"),
            ("occupation_domain", "other"),
            ("nightlife_preference", "medium"),
        ],
        "want_facts": [
            ("interest", "fitness", "strong_preference"),
            ("date_preference", "short_trip", "prefer"),
            ("fitness_level", "high", "prefer"),
        ],
    },
    {
        "login": "demo.alexey",
        "name": "Алексей",
        "gender": "man",
        "dob": date(2003, 12, 9),
        "goal": "unsure",
        "area": "moscow_east",
        "lat": 55.752,
        "lon": 37.79,
        "answers": {
            "self_about": "Пишу код, играю в стратегии, иногда фотографирую город.",
            "self_weekend": "Катка с друзьями или хакатон, редко бар.",
            "self_people": "Любопытство важнее светскости.",
            "partner_who": "Девушка, которой не скучно про игры и технологии.",
            "partner_together": "Кооп, прогулки, иногда кино.",
            "partner_relationship": "Пока без плана, хочу понять химию.",
        },
        "self_facts": [
            ("interest", "gaming"),
            ("interest", "technology"),
            ("interest", "photography"),
            ("social_style", "introvert"),
            ("occupation_domain", "software_engineering"),
        ],
        "want_facts": [
            ("interest", "technology", "prefer"),
            ("date_preference", "home_evening", "prefer"),
            ("communication_style", "direct", "prefer"),
        ],
    },
)


def _now() -> datetime:
    return datetime.now(UTC)


def _existing_login(db: Session, login: str) -> Account | None:
    identity = db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.provider == "local_password",
            AuthIdentity.provider_subject == login,
        )
    )
    if identity is None:
        return None
    return db.get(Account, identity.account_id)


def _insert_person(db: Session, spec: dict, now: datetime) -> Profile:
    account_id = uuid4()
    gender = spec["gender"]
    accepted = ["man"] if gender == "woman" else ["woman"]
    db.add(
        Account(
            account_id=account_id,
            status="active",
            date_of_birth=spec["dob"],
            last_active_at=now,
            onboarding_completed_at=now,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
    )
    db.add(
        AuthIdentity(
            identity_id=uuid4(),
            account_id=account_id,
            provider="local_password",
            provider_subject=spec["login"],
            verified_at=now,
            created_at=now,
        )
    )
    db.add(
        AuthPasswordCredential(
            account_id=account_id,
            password_hash=hash_password(PASSWORD),
            password_changed_at=now,
            created_at=now,
        )
    )
    db.add(
        PrivacyControls(
            account_id=account_id,
            discoverable=True,
            show_distance=False,
            allow_ai_matching=True,
            allow_product_analytics=False,
            version=1,
            updated_at=now,
        )
    )
    for purpose in CONSENTS:
        db.add(
            Consent(
                consent_id=uuid4(),
                account_id=account_id,
                purpose=purpose,
                policy_version=PRIVACY_POLICY_VERSION,
                decision="granted",
                occurred_at=now,
                source="seed",
                evidence_hash=request_fingerprint(
                    purpose, PRIVACY_POLICY_VERSION, "granted", spec["login"]
                ),
            )
        )
    profile = Profile(
        profile_id=uuid4(),
        account_id=account_id,
        display_name=spec["name"],
        bio=None,
        gender_code=gender,
        orientation_code="heterosexual",
        search_mode="dating",
        relationship_goal_code=spec["goal"],
        relationship_status="single",
        city_code="moscow",
        location=location_point(spec["lat"], spec["lon"]),
        public_area_code=spec["area"],
        visibility="eligible",
        moderation_state="approved",
        activated_at=now,
        completion_percent=100,
        version=1,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(profile)
    prefs = DatingPreferences(
        account_id=account_id,
        search_mode="dating",
        accepted_gender_codes=accepted,
        age_min=21,
        age_max=35,
        max_distance_km=50,
        city_codes=["moscow"],
        relationship_goal_codes=list(GOALS),
        dealbreakers={},
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(prefs)
    answers = spec["answers"]
    for code in PROMPTS:
        db.add(
            ProfileAnswer(
                answer_id=uuid4(),
                profile_id=profile.profile_id,
                prompt_code=code,
                answer_text=answers[code],
                visibility="eligible_only",
                version=1,
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
        )
    for code, value in spec["self_facts"]:
        db.add(
            ProfileFact(
                fact_id=uuid4(),
                profile_id=profile.profile_id,
                profile_side="self",
                fact_code=code,
                value=value,
                preference_strength=None,
                source_type="form",
                source_id=None,
                source_version=None,
                provenance_excerpt=None,
                confidence=None,
                review_state="confirmed",
                visibility="matching_only",
                valid_from=now,
                reviewed_at=now,
                superseded_at=None,
            )
        )
    for code, value, strength in spec["want_facts"]:
        db.add(
            ProfileFact(
                fact_id=uuid4(),
                profile_id=profile.profile_id,
                profile_side="desired_partner",
                fact_code=code,
                value=value,
                preference_strength=strength,
                source_type="form",
                source_id=None,
                source_version=None,
                provenance_excerpt=None,
                confidence=None,
                review_state="confirmed",
                visibility="matching_only",
                valid_from=now,
                reviewed_at=now,
                superseded_at=None,
            )
        )
    for step in STEP_CODES:
        db.add(
            OnboardingStepCompletion(
                account_id=account_id,
                flow_version=FLOW_VERSION,
                step_code=step,
                completed_at=now,
                profile_version=1,
                preferences_version=1,
            )
        )
    db.add(
        CalibrationSession(
            calibration_session_id=uuid4(),
            account_id=account_id,
            calibration_version=CALIBRATION_VERSION,
            state="skipped",
            synthetic_only=True,
            signal_snapshot={},
            started_at=now,
            completed_at=now,
        )
    )
    db.flush()
    _seed_photo(db, profile, now)
    return profile


def _seed_photo(db: Session, profile: Profile, now: datetime) -> None:
    from io import BytesIO

    from PIL import Image

    existing = db.scalar(
        select(ProfilePhoto).where(
            ProfilePhoto.profile_id == profile.profile_id,
            ProfilePhoto.deleted_at.is_(None),
        )
    )
    if existing is not None:
        return
    image = Image.new("RGB", (64, 64), (80, 120, 180))
    original = BytesIO()
    image.save(original, format="JPEG")
    body = original.getvalue()
    derived, width, height = render_derivative(image, 64)
    photo_id = uuid4()
    object_key = f"photos/{profile.account_id}/{photo_id}"
    derived_key = f"{object_key}-derived.jpg"
    store = open_store(load_settings())
    store.put(object_key, body, "image/jpeg")
    store.put(derived_key, derived, "image/jpeg")
    db.add(
        ProfilePhoto(
            photo_id=photo_id,
            profile_id=profile.profile_id,
            object_key=object_key,
            derived_object_key=derived_key,
            position=0,
            moderation_state="approved",
            content_hash=sha256(body).hexdigest(),
            content_type="image/jpeg",
            byte_size=len(body),
            width=width,
            height=height,
            version=1,
            created_at=now,
            moderated_at=now,
            deleted_at=None,
        )
    )


def _has_embeddings(db: Session, profile: Profile, model_version: str) -> bool:
    kinds = set(
        db.scalars(
            select(ProfileEmbedding.kind).where(
                ProfileEmbedding.profile_id == profile.profile_id,
                ProfileEmbedding.source_version == profile.version,
                ProfileEmbedding.model_version == model_version,
                ProfileEmbedding.projection_schema_version == PROJECTION_SCHEMA_VERSION,
            )
        )
    )
    return set(EMBED_KINDS) <= kinds


def _embed_profile(db: Session, settings, profile: Profile, now: datetime) -> None:
    model_version = embedding_model_version(settings)
    if _has_embeddings(db, profile, model_version):
        return
    prefs = db.get(DatingPreferences, profile.account_id)
    answers = list(
        db.scalars(
            select(ProfileAnswer).where(
                ProfileAnswer.profile_id == profile.profile_id,
                ProfileAnswer.deleted_at.is_(None),
            )
        )
    )
    facts = list(
        db.scalars(
            select(ProfileFact).where(
                ProfileFact.profile_id == profile.profile_id,
                ProfileFact.superseded_at.is_(None),
                ProfileFact.review_state == "confirmed",
            )
        )
    )
    for kind in EMBED_KINDS:
        exists = db.scalar(
            select(ProfileEmbedding.embedding_id).where(
                ProfileEmbedding.profile_id == profile.profile_id,
                ProfileEmbedding.kind == kind,
                ProfileEmbedding.source_version == profile.version,
                ProfileEmbedding.model_version == model_version,
                ProfileEmbedding.projection_schema_version == PROJECTION_SCHEMA_VERSION,
            )
        )
        if exists is not None:
            continue
        projection = build_projection(
            kind, profile=profile, prefs=prefs, answers=answers, facts=facts
        )
        result = run_embedding(settings, str(projection["text"]))
        vector = result.payload
        if not isinstance(vector, list):
            raise RuntimeError(f"embedding failed for {profile.profile_id} {kind}")
        db.add(
            ProfileEmbedding(
                embedding_id=uuid4(),
                profile_id=profile.profile_id,
                kind=kind,
                source_version=profile.version,
                model_version=model_version,
                projection_schema_version=PROJECTION_SCHEMA_VERSION,
                embedding=vector,
                created_at=now,
            )
        )
        db.flush()


def _profiles_for_logins(db: Session) -> list[tuple[str, Profile, DatingPreferences]]:
    rows: list[tuple[str, Profile, DatingPreferences]] = []
    for spec in PEOPLE:
        account = _existing_login(db, spec["login"])
        if account is None:
            continue
        profile = db.scalar(
            select(Profile).where(Profile.account_id == account.account_id)
        )
        prefs = db.get(DatingPreferences, account.account_id)
        if profile is None or prefs is None:
            continue
        rows.append((spec["login"], profile, prefs))
    return rows


def _sync_existing(db: Session, spec: dict, now: datetime) -> None:
    account = _existing_login(db, spec["login"])
    if account is None:
        return
    account.date_of_birth = spec["dob"]
    account.last_active_at = now
    account.updated_at = now
    profile = db.scalar(select(Profile).where(Profile.account_id == account.account_id))
    if profile is None:
        return
    profile.relationship_goal_code = spec["goal"]
    profile.updated_at = now
    _seed_photo(db, profile, now)


def main() -> None:
    settings = load_settings()
    engine = create_sync_engine(settings)
    now = _now()
    created: list[str] = []
    skipped: list[str] = []
    with Session(engine) as db:
        for spec in PEOPLE:
            if _existing_login(db, spec["login"]) is not None:
                _sync_existing(db, spec, now)
                skipped.append(spec["login"])
                continue
            _insert_person(db, spec, now)
            created.append(spec["login"])
        db.commit()
    with Session(engine) as db:
        ids = [
            profile.profile_id for _login, profile, _prefs in _profiles_for_logins(db)
        ]
        if ids:
            db.execute(
                update(ProfileAnswer)
                .where(
                    ProfileAnswer.profile_id.in_(ids),
                    ProfileAnswer.deleted_at.is_(None),
                )
                .values(visibility="eligible_only")
            )
            db.commit()
    with Session(engine) as db:
        for login, profile, _prefs in _profiles_for_logins(db):
            print(f"embedding {login}…", flush=True)
            _embed_profile(db, settings, profile, now)
            db.commit()
        for _login, profile, prefs in _profiles_for_logins(db):
            enqueue_generation(
                db,
                profile=profile,
                prefs=prefs,
                now=now,
                trigger_code="onboarding_complete",
            )
        db.commit()
    while True:
        with Session(engine) as db:
            jobs = claim_jobs(
                db,
                limit=20,
                lease_seconds=settings.job_lease_seconds,
                job_types=(JOB_TYPE_GENERATE,),
            )
        if not jobs:
            break
        with Session(engine) as db:
            for job in jobs:
                process_generate_job(db, settings, job)
    print(f"password: {PASSWORD}")
    print(f"created: {len(created)} skipped: {len(skipped)}")
    for spec in PEOPLE:
        print(
            f"  {spec['login']:14} {spec['name']:8} {spec['gender']:6} {spec['goal']}"
        )


if __name__ == "__main__":
    main()
