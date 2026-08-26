from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ai_dating.auth.crypto import request_fingerprint
from ai_dating.deps import get_actor, get_db, require_idempotency_key
from ai_dating.errors import AppError
from ai_dating.idempotency import claim_idempotency
from ai_dating.onboarding.calibration import (
    complete_session,
    create_session,
    upsert_choice,
)
from ai_dating.onboarding.schemas import (
    CalibrationChoiceIn,
    CalibrationCompleteIn,
    CalibrationSessionIn,
    OnboardingCompleteIn,
    OnboardingPreferencesPatchIn,
    OnboardingProfilePatchIn,
)
from ai_dating.onboarding.service import (
    complete_onboarding,
    complete_view,
    onboarding_state,
    patch_onboarding_preferences,
    patch_onboarding_profile,
)

router = APIRouter()


@router.get("/v1/onboarding")
def get_onboarding(
    request: Request,
    db: Session = Depends(get_db),
    account_id: UUID | None = None,
) -> dict:
    account, _sess = get_actor(request, db)
    if account_id is not None and account_id != account.account_id:
        raise AppError(404, "not_found", "Not found.")
    return onboarding_state(db, account)


@router.patch("/v1/onboarding/profile")
def patch_profile(
    body: OnboardingProfilePatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    account, _sess = get_actor(request, db)
    return patch_onboarding_profile(db, account, body)


@router.patch("/v1/onboarding/preferences")
def patch_preferences(
    body: OnboardingPreferencesPatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    account, _sess = get_actor(request, db)
    return patch_onboarding_preferences(db, account, body)


@router.post("/v1/onboarding/complete", status_code=202)
def complete(
    body: OnboardingCompleteIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(
        str(body.expected_profile_version), str(body.expected_preferences_version)
    )
    row, replay = claim_idempotency(
        db,
        scope="onboarding.complete",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay:
        return complete_view(db, account)
    result = complete_onboarding(db, account, body)
    row.resource_type = "accounts"
    row.resource_id = account.account_id
    row.response_status = 202
    row.response_body = {"status": result["status"]}
    return result


def _now() -> datetime:
    return datetime.now(UTC)


@router.post("/v1/onboarding/calibration-sessions")
def post_calibration_session(
    body: CalibrationSessionIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    del body
    account, _sess = get_actor(request, db)
    digest = request_fingerprint("calibration-session")
    row, replay = claim_idempotency(
        db,
        scope="onboarding.calibration.create",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = create_session(db, account, _now())
    row.resource_type = "calibration_sessions"
    row.resource_id = UUID(result["calibration_session_id"])
    row.response_status = 200
    row.response_body = result
    return result


@router.post("/v1/onboarding/calibration-sessions/{session_id}/choices")
def post_calibration_choice(
    session_id: UUID,
    body: CalibrationChoiceIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(
        str(session_id), body.demo_pair_id, body.selection, str(body.reason_code)
    )
    row, replay = claim_idempotency(
        db,
        scope="onboarding.calibration.choice",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = upsert_choice(db, account, session_id, body, _now())
    row.resource_type = "calibration_sessions"
    row.resource_id = session_id
    row.response_status = 200
    row.response_body = result
    return result


@router.post("/v1/onboarding/calibration-sessions/{session_id}/complete")
def post_calibration_complete(
    session_id: UUID,
    body: CalibrationCompleteIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(str(session_id), body.decision)
    row, replay = claim_idempotency(
        db,
        scope="onboarding.calibration.complete",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = complete_session(db, account, session_id, body.decision, _now())
    row.resource_type = "calibration_sessions"
    row.resource_id = session_id
    row.response_status = 200
    row.response_body = result
    return result
