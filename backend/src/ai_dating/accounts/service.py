from __future__ import annotations

from datetime import UTC, datetime
from typing import NoReturn
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.auth.crypto import (
    hash_password,
    normalize_login,
    validate_password,
    verify_password,
    verify_unknown,
)
from ai_dating.auth.models import AuthIdentity, AuthPasswordCredential
from ai_dating.auth.sessions import issue_session
from ai_dating.errors import AppError, request_id_of
from ai_dating.events.audit import write_audit
from ai_dating.events.enqueue import enqueue_event
from ai_dating.onboarding.vocab import FLOW_VERSION
from ai_dating.privacy.models import PrivacyControls


def _onboarding_started(account_id: UUID, request_id: str) -> dict:
    return {
        "event_name": "onboarding_started",
        "schema_version": 1,
        "producer": "api",
        "owner": "onboarding",
        "actor_account_id": str(account_id),
        "subject_account_id": None,
        "recommendation_batch_id": None,
        "recommendation_item_id": None,
        "match_id": None,
        "conversation_id": None,
        "request_id": request_id,
        "experiment_assignments": {},
        "privacy_classification": "product_pseudonymous",
        "properties": {"flow_version": FLOW_VERSION},
    }


def _invalid() -> NoReturn:
    raise AppError(401, "invalid_credentials", "Invalid credentials.")


def create_account(
    db: Session, login: str, password: str, ttl_seconds: int
) -> tuple[UUID, str, datetime]:
    login = normalize_login(login)
    validate_password(password)
    now = datetime.now(UTC)
    account_id = uuid4()
    db.add(
        Account(
            account_id=account_id,
            status="onboarding",
            date_of_birth=None,
            last_active_at=now,
            onboarding_completed_at=None,
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
            provider_subject=login,
            verified_at=now,
            created_at=now,
        )
    )
    db.add(
        AuthPasswordCredential(
            account_id=account_id,
            password_hash=hash_password(password),
            password_changed_at=now,
            created_at=now,
        )
    )
    db.add(
        PrivacyControls(
            account_id=account_id,
            discoverable=False,
            show_distance=False,
            allow_ai_matching=False,
            allow_product_analytics=False,
            version=1,
            updated_at=now,
        )
    )
    try:
        token, sess = issue_session(db, account_id, ttl_seconds)
        request_id = request_id_of()
        enqueue_event(db, _onboarding_started(account_id, request_id or "local"))
        write_audit(
            db,
            action="account_registered",
            actor_id=account_id,
            subject_account_id=account_id,
            resource_type="accounts",
            resource_id=account_id,
            request_id=request_id,
            metadata={},
        )
        db.flush()
    except IntegrityError as exc:
        raise AppError(409, "login_unavailable", "Login is unavailable.") from exc
    return account_id, token, sess.expires_at


def authenticate(
    db: Session, login: str, password: str, ttl_seconds: int
) -> tuple[UUID, str, datetime]:
    login = normalize_login(login)
    validate_password(password)
    identity = db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.provider == "local_password",
            AuthIdentity.provider_subject == login,
        )
    )
    if identity is None:
        verify_unknown(password)
        _invalid()
    cred = db.get(AuthPasswordCredential, identity.account_id)
    if cred is None or not verify_password(cred.password_hash, password):
        _invalid()
    account = db.get(Account, identity.account_id)
    if account is None or account.deleted_at is not None:
        _invalid()
    token, sess = issue_session(db, account.account_id, ttl_seconds)
    return account.account_id, token, sess.expires_at


def mint_session(
    db: Session, account_id: UUID, ttl_seconds: int
) -> tuple[UUID, str, datetime]:
    account = db.get(Account, account_id)
    if account is None or account.deleted_at is not None:
        _invalid()
    token, sess = issue_session(db, account_id, ttl_seconds)
    return account_id, token, sess.expires_at
