from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.errors import AppError, request_id_of
from ai_dating.events.enqueue import enqueue_event
from ai_dating.onboarding.models import CalibrationChoice, CalibrationSession
from ai_dating.onboarding.steps import (
    _granted,
    load_preferences,
    load_profile,
    record_step,
)
from ai_dating.onboarding.vocab import CALIBRATION_VERSION, REASON_CODES

DEMO_LABEL = "пример, не реальный участник"
SELECTIONS = ("left", "right", "neither")

DEMO_PAIRS = (
    {
        "demo_pair_id": "demo-v1-pair-01",
        "label": DEMO_LABEL,
        "left": {
            "demo_id": "demo-v1-mira",
            "display_name": "Mira",
            "summary": "Weekends outdoors, texts first, likes cooking.",
            "traits": {
                "activity_style": "active",
                "communication_style": "text_first",
                "interest_tags": ["outdoors", "cooking"],
            },
        },
        "right": {
            "demo_id": "demo-v1-nolan",
            "display_name": "Nolan",
            "summary": "Quiet evenings at home, fine with calls.",
            "traits": {
                "activity_style": "low_key",
                "communication_style": "calls_ok",
                "interest_tags": ["home", "film"],
            },
        },
    },
    {
        "demo_pair_id": "demo-v1-pair-02",
        "label": DEMO_LABEL,
        "left": {
            "demo_id": "demo-v1-sasha",
            "display_name": "Sasha",
            "summary": "Small-group hangouts and live music.",
            "traits": {
                "social_style": "small_group",
                "interest_tags": ["music"],
                "schedule_preference": "weeknights",
            },
        },
        "right": {
            "demo_id": "demo-v1-ira",
            "display_name": "Ira",
            "summary": "One-on-one walks and flexible timing.",
            "traits": {
                "social_style": "one_on_one",
                "interest_tags": ["walking"],
                "schedule_preference": "flexible",
            },
        },
    },
    {
        "demo_pair_id": "demo-v1-pair-03",
        "label": DEMO_LABEL,
        "left": {
            "demo_id": "demo-v1-leo",
            "display_name": "Leo",
            "summary": "Sports-heavy weekends, in-person first.",
            "traits": {
                "activity_style": "active",
                "communication_style": "in_person",
                "schedule_preference": "weekends",
            },
        },
        "right": {
            "demo_id": "demo-v1-kate",
            "display_name": "Kate",
            "summary": "Balanced weeks, reading and art.",
            "traits": {
                "activity_style": "balanced",
                "interest_tags": ["reading", "art"],
                "schedule_preference": "weeknights",
            },
        },
    },
    {
        "demo_pair_id": "demo-v1-pair-04",
        "label": DEMO_LABEL,
        "left": {
            "demo_id": "demo-v1-owen",
            "display_name": "Owen",
            "summary": "Travel and film, mixed social energy.",
            "traits": {
                "social_style": "mixed",
                "interest_tags": ["travel", "film"],
            },
        },
        "right": {
            "demo_id": "demo-v1-nina",
            "display_name": "Nina",
            "summary": "Home cooking and low-key nights.",
            "traits": {
                "activity_style": "low_key",
                "interest_tags": ["cooking", "home"],
            },
        },
    },
    {
        "demo_pair_id": "demo-v1-pair-05",
        "label": DEMO_LABEL,
        "left": {
            "demo_id": "demo-v1-rudi",
            "display_name": "Rudi",
            "summary": "Weekday texts, weekend hikes.",
            "traits": {
                "communication_style": "text_first",
                "activity_style": "active",
                "schedule_preference": "weekends",
            },
        },
        "right": {
            "demo_id": "demo-v1-ella",
            "display_name": "Ella",
            "summary": "Calls after work, flexible plans.",
            "traits": {
                "communication_style": "calls_ok",
                "schedule_preference": "flexible",
            },
        },
    },
)

PAIR_IDS = tuple(item["demo_pair_id"] for item in DEMO_PAIRS)
PAIR_BY_ID = {item["demo_pair_id"]: item for item in DEMO_PAIRS}


def _public_pairs() -> list[dict]:
    return [
        {
            "demo_pair_id": item["demo_pair_id"],
            "label": item["label"],
            "left": {
                "demo_id": item["left"]["demo_id"],
                "display_name": item["left"]["display_name"],
                "summary": item["left"]["summary"],
            },
            "right": {
                "demo_id": item["right"]["demo_id"],
                "display_name": item["right"]["display_name"],
                "summary": item["right"]["summary"],
            },
        }
        for item in DEMO_PAIRS
    ]


def _session(db: Session, account_id: UUID) -> CalibrationSession | None:
    return db.scalar(
        select(CalibrationSession).where(
            CalibrationSession.account_id == account_id,
            CalibrationSession.calibration_version == CALIBRATION_VERSION,
        )
    )


def calibration_done(db: Session, account_id: UUID) -> bool:
    row = _session(db, account_id)
    return row is not None and row.state in {"completed", "skipped"}


def _choices(db: Session, session_id: UUID) -> list[CalibrationChoice]:
    return list(
        db.scalars(
            select(CalibrationChoice).where(
                CalibrationChoice.calibration_session_id == session_id
            )
        )
    )


def _choice_payload(rows: list[CalibrationChoice]) -> list[dict]:
    return [
        {
            "demo_pair_id": row.demo_pair_id,
            "selection": row.selection,
            "reason_code": row.reason_code,
        }
        for row in rows
    ]


def session_view(db: Session, row: CalibrationSession) -> dict:
    return {
        "calibration_session_id": str(row.calibration_session_id),
        "calibration_version": row.calibration_version,
        "state": row.state,
        "synthetic_only": row.synthetic_only,
        "pairs": _public_pairs(),
        "choices": _choice_payload(_choices(db, row.calibration_session_id)),
        "label": DEMO_LABEL,
    }


def _signal(rows: list[CalibrationChoice]) -> dict:
    weights: dict[str, dict[str, int]] = {}
    for row in rows:
        if row.selection == "neither":
            continue
        pair = PAIR_BY_ID[row.demo_pair_id]
        traits = pair[row.selection]["traits"]
        for key, value in traits.items():
            bucket = weights.setdefault(key, {})
            if isinstance(value, list):
                for tag in value:
                    bucket[tag] = bucket.get(tag, 0) + 1
            else:
                bucket[value] = bucket.get(value, 0) + 1
    return {"version": CALIBRATION_VERSION, "weights": weights}


def create_session(db: Session, account: Account, now: datetime) -> dict:
    row = _session(db, account.account_id)
    if row is None:
        stmt = (
            insert(CalibrationSession)
            .values(
                calibration_session_id=uuid4(),
                account_id=account.account_id,
                calibration_version=CALIBRATION_VERSION,
                state="started",
                synthetic_only=True,
                signal_snapshot={},
                started_at=now,
                completed_at=None,
            )
            .on_conflict_do_nothing(
                index_elements=["account_id", "calibration_version"]
            )
        )
        db.execute(stmt)
        db.flush()
        row = _session(db, account.account_id)
        if row is None:
            raise AppError(500, "internal_error", "Could not start calibration.")
    elif row.state == "skipped":
        for choice in _choices(db, row.calibration_session_id):
            db.delete(choice)
        row.state = "started"
        row.signal_snapshot = {}
        row.started_at = now
        row.completed_at = None
        db.flush()
    return session_view(db, row)


def upsert_choice(
    db: Session, account: Account, session_id: UUID, body, now: datetime
) -> dict:
    row = db.get(CalibrationSession, session_id)
    if row is None or row.account_id != account.account_id:
        raise AppError(404, "not_found", "Not found.")
    if row.state != "started":
        raise AppError(409, "version_conflict", "Calibration already finished.")
    if body.demo_pair_id not in PAIR_BY_ID:
        raise AppError(422, "validation_error", "Invalid request.")
    if body.selection not in SELECTIONS:
        raise AppError(422, "validation_error", "Invalid request.")
    if body.reason_code is not None and body.reason_code not in REASON_CODES:
        raise AppError(422, "validation_error", "Invalid request.")
    existing = db.scalar(
        select(CalibrationChoice).where(
            CalibrationChoice.calibration_session_id == session_id,
            CalibrationChoice.demo_pair_id == body.demo_pair_id,
        )
    )
    if existing is None:
        db.add(
            CalibrationChoice(
                calibration_choice_id=uuid4(),
                calibration_session_id=session_id,
                demo_pair_id=body.demo_pair_id,
                selection=body.selection,
                reason_code=body.reason_code,
                created_at=now,
            )
        )
    else:
        existing.selection = body.selection
        existing.reason_code = body.reason_code
    db.flush()
    return session_view(db, row)


def _complete_event(account_id: UUID, items_seen: int, skipped: bool) -> dict:
    return {
        "event_name": "calibration_completed",
        "schema_version": 1,
        "producer": "api",
        "owner": "onboarding",
        "actor_account_id": str(account_id),
        "subject_account_id": None,
        "recommendation_batch_id": None,
        "recommendation_item_id": None,
        "match_id": None,
        "conversation_id": None,
        "request_id": request_id_of() or "local",
        "experiment_assignments": {},
        "privacy_classification": "product_pseudonymous",
        "properties": {
            "calibration_version": CALIBRATION_VERSION,
            "items_seen": items_seen,
            "skipped": skipped,
            "synthetic_only": True,
        },
    }


def complete_session(
    db: Session, account: Account, session_id: UUID, decision: str, now: datetime
) -> dict:
    row = db.get(CalibrationSession, session_id)
    if row is None or row.account_id != account.account_id:
        raise AppError(404, "not_found", "Not found.")
    if row.state in {"completed", "skipped"}:
        return session_view(db, row)
    if decision == "skip":
        row.state = "skipped"
        row.signal_snapshot = {}
        row.completed_at = now
        items = db.scalar(
            select(func.count())
            .select_from(CalibrationChoice)
            .where(CalibrationChoice.calibration_session_id == session_id)
        )
        enqueue_event(db, _complete_event(account.account_id, int(items or 0), True))
    elif decision == "complete":
        if not _granted(db, account.account_id, "calibration"):
            raise AppError(422, "validation_error", "Calibration consent is required.")
        rows = _choices(db, session_id)
        seen = {item.demo_pair_id for item in rows}
        if seen != set(PAIR_IDS):
            raise AppError(422, "validation_error", "Choose every demo pair.")
        row.state = "completed"
        row.signal_snapshot = _signal(rows)
        row.completed_at = now
        enqueue_event(db, _complete_event(account.account_id, len(rows), False))
    else:
        raise AppError(422, "validation_error", "Invalid request.")
    record_step(
        db,
        account,
        "calibration",
        profile=load_profile(db, account.account_id),
        prefs=load_preferences(db, account.account_id),
    )
    return session_view(db, row)


def clear_calibration(db: Session, account_id: UUID, now: datetime) -> None:
    row = _session(db, account_id)
    if row is None:
        row = CalibrationSession(
            calibration_session_id=uuid4(),
            account_id=account_id,
            calibration_version=CALIBRATION_VERSION,
            state="skipped",
            synthetic_only=True,
            signal_snapshot={},
            started_at=now,
            completed_at=now,
        )
        db.add(row)
        return
    for choice in _choices(db, row.calibration_session_id):
        db.delete(choice)
    row.signal_snapshot = {}
    row.state = "skipped"
    row.completed_at = now
