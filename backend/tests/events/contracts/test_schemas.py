from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from ai_dating.events import EventValidationError, validate_event

ACTOR = "0d4abf5f-a08e-4a63-a3c2-f25d5c5d8fe0"
SUBJECT = "f39090d6-0d39-4341-9b6c-321c8bed50d8"
BATCH = "a3cc1fd0-4cc2-44ed-97d1-55db8ec047cd"
ITEM = "a63d0bd6-aee5-4f79-b60e-2dcd66cd42e2"
MATCH = "f630c2a4-715e-48f7-9945-8514cef49015"
CONV = "405d0f64-b73c-409b-9f4f-3fc65d57a27b"
ACTION = "1c2e3f4a-5b6c-7d8e-9f01-23456789abcd"
LIKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
MSG = "11111111-2222-3333-4444-555555555555"
JOB = "99999999-8888-7777-6666-555555555555"
FACT = "12345678-1234-1234-1234-1234567890ab"
REPORT = "06693b13-6ca7-48f0-b625-f2a8427466f1"

REC_NULL = {
    "recommendation_batch_id": None,
    "recommendation_item_id": None,
    "match_id": None,
    "conversation_id": None,
}


def envelope(**overrides: object) -> dict:
    payload = {
        "event_id": str(uuid4()),
        "event_name": "impression",
        "schema_version": 1,
        "occurred_at": "2026-08-25T10:15:32.481Z",
        "producer": "api",
        "owner": "recommendations",
        "actor_account_id": ACTOR,
        "subject_account_id": SUBJECT,
        "recommendation_batch_id": BATCH,
        "recommendation_item_id": ITEM,
        "match_id": None,
        "conversation_id": None,
        "request_id": "req_01K3J2TQ8G",
        "experiment_assignments": {},
        "privacy_classification": "product_pseudonymous",
        "properties": {},
    }
    payload.update(overrides)
    return payload


VALID: dict[str, dict] = {
    "impression": envelope(
        properties={"surface": "daily_batch", "rank": 2, "batch_schema_version": 1}
    ),
    "open": envelope(
        event_name="open",
        properties={"action_id": ACTION, "surface": "daily_batch", "rank": 1},
    ),
    "like": envelope(
        event_name="like",
        owner="matching",
        properties={
            "action_id": ACTION,
            "like_id": LIKE,
            "is_reciprocal_at_commit": False,
        },
    ),
    "pass": envelope(event_name="pass", properties={"action_id": ACTION}),
    "pass_reason": envelope(
        event_name="pass_reason",
        properties={"action_id": ACTION, "reason_code": "not_my_type"},
    ),
    "match": envelope(
        event_name="match",
        owner="matching",
        match_id=MATCH,
        conversation_id=CONV,
        properties={"source": "reciprocal_like"},
    ),
    "message": envelope(
        event_name="message",
        owner="messaging",
        recommendation_batch_id=None,
        recommendation_item_id=None,
        match_id=MATCH,
        conversation_id=CONV,
        properties={
            "message_id": MSG,
            "sequence_kind": "first",
            "moderation_state": "allowed",
        },
    ),
    "reply": envelope(
        event_name="reply",
        owner="messaging",
        recommendation_batch_id=None,
        recommendation_item_id=None,
        match_id=MATCH,
        conversation_id=CONV,
        properties={
            "message_id": MSG,
            "reply_to_message_id": ACTION,
            "latency_seconds": 12,
        },
    ),
    "unmatch": envelope(
        event_name="unmatch",
        owner="matching",
        match_id=MATCH,
        properties={"initiator_role": "self", "match_age_seconds": 3600},
    ),
    "block": envelope(
        event_name="block",
        owner="safety",
        properties={"reason_code": "harassment", "had_active_match": True},
    ),
    "report": envelope(
        event_name="report",
        owner="safety",
        privacy_classification="security_restricted",
        match_id=MATCH,
        conversation_id=CONV,
        properties={
            "report_id": REPORT,
            "reason_code": "harassment",
            "target_type": "account",
        },
    ),
    "onboarding_started": envelope(
        event_name="onboarding_started",
        owner="onboarding",
        subject_account_id=None,
        **REC_NULL,
        properties={"flow_version": "v1"},
    ),
    "onboarding_step_completed": envelope(
        event_name="onboarding_step_completed",
        owner="onboarding",
        subject_account_id=None,
        **REC_NULL,
        properties={
            "flow_version": "v1",
            "step_code": "profile",
            "profile_version": 1,
            "preferences_version": 1,
        },
    ),
    "fact_reviewed": envelope(
        event_name="fact_reviewed",
        owner="profiles",
        subject_account_id=None,
        **REC_NULL,
        properties={
            "fact_id": FACT,
            "fact_category": "lifestyle",
            "decision": "accept",
            "source_type": "extracted",
            "extractor_version": "extract-1",
        },
    ),
    "calibration_completed": envelope(
        event_name="calibration_completed",
        owner="onboarding",
        subject_account_id=None,
        **REC_NULL,
        properties={
            "calibration_version": "c1",
            "items_seen": 4,
            "skipped": False,
            "synthetic_only": True,
        },
    ),
    "onboarding_completed": envelope(
        event_name="onboarding_completed",
        owner="onboarding",
        subject_account_id=None,
        **REC_NULL,
        properties={
            "flow_version": "v1",
            "profile_version": 2,
            "preferences_version": 1,
            "duration_seconds": 240,
        },
    ),
    "profile_activated": envelope(
        event_name="profile_activated",
        owner="profiles",
        producer="worker",
        actor_account_id=None,
        subject_account_id=ACTOR,
        **REC_NULL,
        properties={"profile_version": 2, "activation_latency_seconds": 30},
    ),
    "recommendation_generation_queued": envelope(
        event_name="recommendation_generation_queued",
        owner="recommendations",
        actor_account_id=None,
        subject_account_id=ACTOR,
        **REC_NULL,
        properties={
            "job_id": JOB,
            "trigger_code": "onboarding_complete",
            "profile_version": 2,
            "preferences_version": 1,
        },
    ),
}


def test_all_required_events_accept_valid_payload():
    for name, payload in VALID.items():
        validate_event(payload)


def test_onboarding_step_allows_null_versions():
    payload = deepcopy(VALID["onboarding_step_completed"])
    payload["properties"]["profile_version"] = None
    payload["properties"]["preferences_version"] = None
    validate_event(payload)


def test_unknown_field_rejected():
    payload = deepcopy(VALID["impression"])
    payload["dob"] = "1995-01-01"
    try:
        validate_event(payload)
    except EventValidationError:
        return
    raise AssertionError("expected rejection")


def test_pii_in_properties_rejected():
    keys = {
        "dob": "1995-01-01",
        "latitude": 55.75,
        "longitude": 37.62,
        "body": "hello",
        "message_body": "secret",
        "photo_url": "https://example.com/p.jpg",
        "details": "report free text",
        "prompt": "system prompt",
        "free_text": "bio",
    }
    for key, value in keys.items():
        payload = deepcopy(VALID["impression"])
        payload["properties"][key] = value
        try:
            validate_event(payload)
        except EventValidationError:
            continue
        raise AssertionError(f"expected rejection for {key}")


def test_report_details_rejected():
    payload = deepcopy(VALID["report"])
    payload["properties"]["details"] = "user wrote this"
    try:
        validate_event(payload)
    except EventValidationError:
        return
    raise AssertionError("expected rejection")


def test_unknown_reason_code_rejected():
    for name in ("block", "report"):
        payload = deepcopy(VALID[name])
        payload["properties"]["reason_code"] = "because_i_said_so"
        try:
            validate_event(payload)
        except EventValidationError:
            continue
        raise AssertionError(name)
