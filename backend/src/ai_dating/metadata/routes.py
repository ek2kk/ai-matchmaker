from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ai_dating.deps import get_actor, get_db
from ai_dating.onboarding.vocab import metadata_payload
from ai_dating.privacy.models import PRIVACY_POLICY_VERSION

router = APIRouter()


@router.get("/v1/metadata/onboarding")
def get_onboarding_metadata(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    get_actor(request, db)
    return metadata_payload(PRIVACY_POLICY_VERSION)
