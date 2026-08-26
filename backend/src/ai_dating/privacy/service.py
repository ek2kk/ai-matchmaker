from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.auth.crypto import request_fingerprint
from ai_dating.errors import AppError
from ai_dating.events.audit import write_audit
from ai_dating.jobs.enqueue import enqueue_job
from ai_dating.onboarding.steps import maybe_record_account_step
from ai_dating.privacy.models import (
    DECISIONS,
    PRIVACY_POLICY_VERSION,
    PURPOSES,
    Consent,
    PrivacyControls,
)

_PURPOSE_FLAG = {
    "ai_matching": "allow_ai_matching",
    "product_analytics": "allow_product_analytics",
    "dating_visibility": "discoverable",
}


def _controls(db: Session, account_id: UUID) -> PrivacyControls:
    row = db.scalar(
        select(PrivacyControls).where(PrivacyControls.account_id == account_id)
    )
    if row is None:
        raise AppError(404, "not_found", "Not found.")
    return row


def latest_consents(db: Session, account_id: UUID) -> list[Consent]:
    rows = db.scalars(
        select(Consent)
        .where(Consent.account_id == account_id)
        .order_by(Consent.occurred_at.desc())
    ).all()
    seen: dict[str, Consent] = {}
    for row in rows:
        if row.purpose not in seen:
            seen[row.purpose] = row
    return list(seen.values())


def privacy_view(db: Session, account: Account, consent_id: UUID | None) -> dict:
    if consent_id is not None:
        owned = db.scalar(
            select(Consent).where(
                Consent.consent_id == consent_id,
                Consent.account_id == account.account_id,
            )
        )
        if owned is None:
            raise AppError(404, "not_found", "Not found.")
    controls = _controls(db, account.account_id)
    receipts = latest_consents(db, account.account_id)
    return {
        "version": controls.version,
        "discoverable": controls.discoverable,
        "show_distance": controls.show_distance,
        "allow_ai_matching": controls.allow_ai_matching,
        "allow_product_analytics": controls.allow_product_analytics,
        "consents": [
            {
                "consent_id": str(item.consent_id),
                "purpose": item.purpose,
                "policy_version": item.policy_version,
                "decision": item.decision,
                "occurred_at": item.occurred_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            for item in receipts
        ],
    }


def append_consent(
    db: Session,
    account: Account,
    *,
    purpose: str,
    policy_version: str,
    decision: str,
    request_id: str,
) -> Consent:
    if purpose not in PURPOSES or decision not in DECISIONS:
        raise AppError(422, "validation_error", "Invalid request.")
    if policy_version != PRIVACY_POLICY_VERSION:
        raise AppError(422, "validation_error", "Invalid request.")
    now = datetime.now(UTC)
    row = Consent(
        consent_id=uuid4(),
        account_id=account.account_id,
        purpose=purpose,
        policy_version=policy_version,
        decision=decision,
        occurred_at=now,
        source="api",
        evidence_hash=request_fingerprint(purpose, policy_version, decision),
    )
    db.add(row)
    controls = _controls(db, account.account_id)
    granted = decision == "granted"
    flag = _PURPOSE_FLAG.get(purpose)
    if flag == "allow_ai_matching":
        controls.allow_ai_matching = granted
        if not granted:
            _hide_and_queue(db, account.account_id, controls, now)
    elif flag == "allow_product_analytics":
        controls.allow_product_analytics = granted
    elif flag == "discoverable":
        controls.discoverable = granted
    controls.updated_at = now
    write_audit(
        db,
        action="consent_recorded",
        actor_id=account.account_id,
        subject_account_id=account.account_id,
        resource_type="consents",
        resource_id=row.consent_id,
        request_id=request_id,
        metadata={"purpose": purpose, "decision": decision},
    )
    if purpose == "calibration" and decision in {"withdrawn", "rejected"}:
        from ai_dating.onboarding.calibration import clear_calibration

        clear_calibration(db, account.account_id, now)
    maybe_record_account_step(db, account)
    return row


def patch_privacy(
    db: Session,
    account: Account,
    *,
    expected_version: int,
    discoverable: bool | None,
    show_distance: bool | None,
    allow_ai_matching: bool | None,
    allow_product_analytics: bool | None,
    request_id: str,
) -> dict:
    controls = _controls(db, account.account_id)
    if controls.version != expected_version:
        raise AppError(
            409,
            "version_conflict",
            "Privacy changed; reload and retry.",
            details={"current_version": controls.version},
        )
    now = datetime.now(UTC)
    if discoverable is not None and discoverable != controls.discoverable:
        append_consent(
            db,
            account,
            purpose="dating_visibility",
            policy_version=PRIVACY_POLICY_VERSION,
            decision="granted" if discoverable else "withdrawn",
            request_id=request_id,
        )
    if (
        allow_ai_matching is not None
        and allow_ai_matching != controls.allow_ai_matching
    ):
        append_consent(
            db,
            account,
            purpose="ai_matching",
            policy_version=PRIVACY_POLICY_VERSION,
            decision="granted" if allow_ai_matching else "withdrawn",
            request_id=request_id,
        )
    if (
        allow_product_analytics is not None
        and allow_product_analytics != controls.allow_product_analytics
    ):
        append_consent(
            db,
            account,
            purpose="product_analytics",
            policy_version=PRIVACY_POLICY_VERSION,
            decision="granted" if allow_product_analytics else "withdrawn",
            request_id=request_id,
        )
    if show_distance is not None:
        controls.show_distance = show_distance
    controls.version += 1
    controls.updated_at = now
    write_audit(
        db,
        action="privacy_updated",
        actor_id=account.account_id,
        subject_account_id=account.account_id,
        resource_type="privacy_controls",
        resource_id=account.account_id,
        request_id=request_id,
        metadata={},
    )
    return privacy_view(db, account, None)


def _hide_and_queue(
    db: Session, account_id: UUID, controls: PrivacyControls, now: datetime
) -> None:
    controls.discoverable = False
    controls.allow_ai_matching = False
    enqueue_job(
        db,
        job_type="invalidate_derived_matching",
        dedup_key=f"invalidate_derived_matching:{account_id}",
        payload={"account_id": str(account_id)},
        now=now,
    )
