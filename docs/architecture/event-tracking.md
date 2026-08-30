# Event tracking

> **Contract owner:** backend analytics contract module.  
> **Delivery:** domain transaction → `outbox_events` → at-least-once relay → ClickHouse raw events.  
> **Rule:** product analytics cannot authorize or enforce user-facing state.

## 1. Canonical envelope

Every event is a JSON object with these required fields:

| Field | Type | Semantics |
|---|---|---|
| `event_id` | UUID string | Generated server-side once; global deduplication key |
| `event_name` | string | Stable lower `snake_case` name |
| `schema_version` | integer | Starts at 1 per event name; positive |
| `occurred_at` | RFC3339 UTC | Server time when the domain transition is applied inside its transaction; visible/durable only after commit, never client clock |
| `producer` | string | `api`, `worker`, or named backend module |
| `owner` | string | Domain team/module responsible for meaning |
| `actor_account_id` | UUID or null | Pseudonymous initiator; null only for system action |
| `subject_account_id` | UUID or null | Person acted on; never inferred by client |
| `recommendation_batch_id` | UUID or null | Required for recommendation interactions |
| `recommendation_item_id` | UUID or null | Required for `impression/open/like/pass/pass_reason` |
| `match_id` | UUID or null | Required for match/conversation lifecycle where applicable |
| `conversation_id` | UUID or null | Required for message/reply where applicable |
| `request_id` | string | Correlation across logs/traces; not an idempotency key |
| `experiment_assignments` | object | Stable `experiment_key:variant@version`; `{}` when none |
| `privacy_classification` | string | `product_pseudonymous` or `security_restricted` |
| `properties` | object | Event-specific, schema-validated; no arbitrary client properties |

Account IDs are identifiers, not anonymous data. Raw event access is restricted. Exact location, DOB, email, message body, photo URL, free text, report details and model prompts are prohibited in product event payloads.

## 2. Required events

All product events are produced server-side after the corresponding authoritative write/validation. Block/report additionally create a separate restricted `security_audit_log` record; the ClickHouse projection contains only minimized reason categories.

| Event | Owner / producer | Moment | Required event-specific fields | Rec refs | Privacy / delivery |
|---|---|---|---|---|---|
| `impression` | recommendations / API | Unique exposure inserted after authenticated client render acknowledgement | `surface`, `rank`, `batch_schema_version` | batch + item required | product pseudonymous; outbox, dedup `event_id` and unique exposure |
| `open` | recommendations / API | First card detail open action committed | `action_id`, `surface`, `rank` | batch + item required | product pseudonymous; unique item/actor/action row |
| `like` | matching / API | Terminal like action and active like committed | `action_id`, `like_id`, `is_reciprocal_at_commit` | batch + item required | product pseudonymous; unique terminal decision |
| `pass` | recommendations / API | Pass action committed for exposed item | `action_id` | batch + item required | product pseudonymous; unique item/actor/action row |
| `pass_reason` | recommendations / API | Optional allowlisted reason committed with the pass action | `action_id`, `reason_code` | batch + item required | product pseudonymous; no free text |
| `match` | matching / API | Second active reciprocal like creates unique match | `source=reciprocal_like` | completing like's batch/item, `match_id` and `conversation_id` required in MVP | product pseudonymous; same transaction as match |
| `message` | messaging / API | Message passes synchronous policy/rate checks and is delivered | `message_id`, `sequence_kind=first_or_followup`, `moderation_state=allowed` | rec refs null; match + conversation required | no body; post-moderation can later remove content |
| `reply` | messaging / API | Newly delivered message follows latest allowed message by other member within 7 days | `message_id`, `reply_to_message_id`, `latency_seconds` | match + conversation required | no body; emitted with message creation |
| `unmatch` | matching / API | Active match transitions to unmatched | `initiator_role=self`, `match_age_seconds` | `match_id` required | product pseudonymous; reason omitted unless allowlisted |
| `block` | safety / API | Block + relationship invalidation committed | `reason_code` allowlisted, `had_active_match` | match nullable | product projection + restricted audit; immediate enforcement from PG |
| `report` | safety / API | Report + automatic block committed | `report_id`, `reason_code`, `target_type` | match nullable | minimized product projection + restricted audit |

For `message`/`reply` the subject is the other conversation member. For `match`, the event actor is the account whose second like completed reciprocity; subject is the other member, and recommendation refs come from that completing like. Analytics treats both participants symmetrically from `match_id`, never assumes actor “caused” quality. For system moderation changes, use security audit events, not these product events.

### Onboarding and generation lifecycle events

These are canonical product events under the same envelope/schema/delivery rules. They contain no raw answers, facts, location or photo data.

| Event | Owner / producer | Moment | Required properties | Identity / idempotency |
|---|---|---|---|---|
| `onboarding_started` | auth / API | First local registration or verified beta SMS OTP creates application account | `flow_version`, `auth_mode` | actor only; once per account/flow version |
| `onboarding_step_completed` | onboarding / API | A named user-controlled step first satisfies its server validation | `flow_version`, allowlisted `step_code`, `profile_version`, `preferences_version` | actor only; once per account/flow/step; later edits do not fake another completion |
| `fact_reviewed` | profiles / API | Accept/edit/reject decision and fact version commit | `fact_id`, `fact_category`, `decision`, `source_type`, `extractor_version` nullable | actor only; one event per committed fact review version. Event `source_type` is `extracted` when the reviewed row is `free_text`, otherwise `user_entered`. `extractor_version` is the prompt version for extracted rows |
| `calibration_completed` | onboarding / API | Synthetic calibration completes or is explicitly skipped | `calibration_version`, `items_seen`, `skipped`, `synthetic_only` | actor only; stable completion action ID. Idempotent retry of the same complete/skip does not enqueue a second event |
| `onboarding_completed` | onboarding / API | All user-controlled gates commit, independent of pending async moderation | `flow_version`, `profile_version`, `preferences_version`, `duration_seconds` | actor only; once for initial flow, idempotent retry returns existing state |
| `profile_activated` | profiles / worker | Server-controlled photo/profile moderation and visibility gates first pass | `profile_version`, `activation_latency_seconds` | actor is null, subject is account; once per activation epoch (MVP has one initial epoch) |
| `recommendation_generation_queued` | recommendations / API or worker | Deduplicated generation job commits | `job_id`, `trigger_code`, `profile_version`, `preferences_version` | subject is target account; one event per unique job `dedup_key` |
| `recommendation_batch_ready` | recommendations / worker | Ready batch is committed | `batch_kind`, `item_count`, `fallback_mode` | subject is batch owner; no candidate IDs or reason text |
| `fact_extraction_ready` | profiles / worker | Deferred extraction writes review-only suggestions | `answer_version`, `suggestion_count` | subject is owner; no fact values or source text |

`step_code`, `fact_category`, `decision` and `trigger_code` are versioned allowlists in the per-event JSON Schema. All seven events use `privacy_classification = product_pseudonymous`; consent/age decisions separately create restricted security audit receipts. `onboarding_completed` is the funnel boundary; `profile_activated` starts the recommendation readiness latency clock.

## 3. JSON contract examples

### Impression payload

```json
{
  "event_id": "66f2835e-31e9-4a91-a508-9553fbf76b31",
  "event_name": "impression",
  "schema_version": 1,
  "occurred_at": "2026-08-25T10:15:32.481Z",
  "producer": "api",
  "owner": "recommendations",
  "actor_account_id": "0d4abf5f-a08e-4a63-a3c2-f25d5c5d8fe0",
  "subject_account_id": "f39090d6-0d39-4341-9b6c-321c8bed50d8",
  "recommendation_batch_id": "a3cc1fd0-4cc2-44ed-97d1-55db8ec047cd",
  "recommendation_item_id": "a63d0bd6-aee5-4f79-b60e-2dcd66cd42e2",
  "match_id": null,
  "conversation_id": null,
  "request_id": "req_01K3J2TQ8G",
  "experiment_assignments": {"ranker_v0": "control@1"},
  "privacy_classification": "product_pseudonymous",
  "properties": {"surface": "daily_batch", "rank": 2, "batch_schema_version": 1}
}
```

### Match payload

```json
{
  "event_id": "59a783fb-6e12-4839-a38e-24c52b1801bc",
  "event_name": "match",
  "schema_version": 1,
  "occurred_at": "2026-08-25T11:04:01.008Z",
  "producer": "api",
  "owner": "matching",
  "actor_account_id": "f39090d6-0d39-4341-9b6c-321c8bed50d8",
  "subject_account_id": "0d4abf5f-a08e-4a63-a3c2-f25d5c5d8fe0",
  "recommendation_batch_id": "a3cc1fd0-4cc2-44ed-97d1-55db8ec047cd",
  "recommendation_item_id": "a63d0bd6-aee5-4f79-b60e-2dcd66cd42e2",
  "match_id": "f630c2a4-715e-48f7-9945-8514cef49015",
  "conversation_id": "405d0f64-b73c-409b-9f4f-3fc65d57a27b",
  "request_id": "req_01K3J5NMCN",
  "experiment_assignments": {"ranker_v0": "control@1"},
  "privacy_classification": "product_pseudonymous",
  "properties": {"source": "reciprocal_like"}
}
```

### Report product projection

```json
{
  "event_id": "77273bce-048d-4880-896c-eb60030da86a",
  "event_name": "report",
  "schema_version": 1,
  "occurred_at": "2026-08-25T11:17:42.031Z",
  "producer": "api",
  "owner": "safety",
  "actor_account_id": "0d4abf5f-a08e-4a63-a3c2-f25d5c5d8fe0",
  "subject_account_id": "f39090d6-0d39-4341-9b6c-321c8bed50d8",
  "recommendation_batch_id": null,
  "recommendation_item_id": null,
  "match_id": "f630c2a4-715e-48f7-9945-8514cef49015",
  "conversation_id": "405d0f64-b73c-409b-9f4f-3fc65d57a27b",
  "request_id": "req_01K3J68ENY",
  "experiment_assignments": {},
  "privacy_classification": "security_restricted",
  "properties": {
    "report_id": "06693b13-6ca7-48f0-b625-f2a8427466f1",
    "reason_code": "harassment",
    "target_type": "account"
  }
}
```

Conceptual JSON Schema fragment shared by event definitions:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["event_id", "event_name", "schema_version", "occurred_at", "producer", "owner", "actor_account_id", "subject_account_id", "recommendation_batch_id", "recommendation_item_id", "match_id", "conversation_id", "request_id", "experiment_assignments", "privacy_classification", "properties"],
  "additionalProperties": false,
  "properties": {
    "event_id": {"type": "string", "format": "uuid"},
    "event_name": {"type": "string", "pattern": "^[a-z][a-z0-9_]+$"},
    "schema_version": {"type": "integer", "minimum": 1},
    "occurred_at": {"type": "string", "format": "date-time"},
    "producer": {"type": "string"},
    "owner": {"type": "string"},
    "actor_account_id": {"type": ["string", "null"], "format": "uuid"},
    "subject_account_id": {"type": ["string", "null"], "format": "uuid"},
    "recommendation_batch_id": {"type": ["string", "null"], "format": "uuid"},
    "recommendation_item_id": {"type": ["string", "null"], "format": "uuid"},
    "match_id": {"type": ["string", "null"], "format": "uuid"},
    "conversation_id": {"type": ["string", "null"], "format": "uuid"},
    "request_id": {"type": "string"},
    "experiment_assignments": {"type": "object"},
    "privacy_classification": {"enum": ["product_pseudonymous", "security_restricted"]},
    "properties": {"type": "object"}
  }
}
```

Implementation stores one complete schema per event/version in the backend repository; the fragment is documentation, not a deployable registry file.

## 4. Versioning and compatibility

- Additive optional field: same schema version only when old consumers ignore it and meaning is unchanged.
- Required field, type, enum semantics or meaning change: increment per-event `schema_version`.
- Producers validate before outbox insert. CI contract fixtures validate current and previous supported versions.
- Consumers reject unknown major semantics to dead-letter/quarantine, never silently coerce.
- Event name is never reused for a different action. Corrections use a new event with `correction_of_event_id`, defined by its own schema.
- Registry MVP is versioned JSON Schema files in backend source control. External schema registry is Later, when multiple producer repositories exist.

## 5. Delivery, retries and idempotency

1. Domain write and outbox insert commit in one Postgres transaction.
2. Relay uses a short transaction with `SKIP LOCKED` to set `lease_owner/lease_until`, commits, then inserts a bounded batch to ClickHouse without holding a DB transaction.
3. A second short transaction marks `delivered_at`; crash between sink insert and mark causes duplicate delivery with the same `event_id`. Expired leases are claimable.
4. ClickHouse raw table uses `ReplacingMergeTree(ingested_at)` ordered by `(event_name, occurred_date, event_id)`. Queries/marts deduplicate by `event_id`; correctness must not depend on background merge timing.
5. Retry uses exponential backoff with jitter, 10 s to 15 min. After 24 h, row remains retryable and pages the owner; no drop-on-error.
6. Outbox rows are retained at least 7 days after verified delivery; ClickHouse raw retention starts at 13 months (**Assumption**, legal review required).

A failed batch is split to isolate a deterministic sink/schema rejection; valid rows continue, while the bad row remains pending with its `event_id`, error code and alert. There is no silent dead-letter drop.

No cross-event delivery ordering is guaranteed, including for one account; consumers order analytically by `occurred_at,event_id` and must tolerate late events. Domain state is never rebuilt from ClickHouse ordering. Kafka becomes mandatory at the triggers in [overview.md](overview.md), not simply because events exist.

## 6. Product events versus security audit

| Property | Product events | Security/moderation audit |
|---|---|---|
| Purpose | Funnels, ranking evaluation, product reliability | Investigation, consent proof, employee access, enforcement |
| Store | ClickHouse raw + marts | Append-only Postgres restricted schema; optional protected archive |
| Payload | Pseudonymous IDs, allowlisted categories | Minimum evidence needed for case; may be more sensitive |
| Access | Analytics/ML roles by purpose | Trust & Safety/security only, break-glass audited |
| Retention | 13 months Assumption | `TBD-SEC01`, jurisdiction and case dependent |
| Deletion | Delete/anonymize subject IDs according to policy | Legal hold/abuse exception only with documented basis |

## 7. Funnels and metrics

| Funnel / metric | Numerator | Denominator / cohort | Guardrail |
|---|---|---|---|
| Activation | onboarding complete + first impression | verified accounts starting onboarding | Exclude demo calibration |
| Eligible supply | reciprocal eligible candidate count | activated discoverable accounts | Segment by market/preferences, not protected attribute dashboard by default |
| Candidate coverage | unique eligible candidates retrieved in 7d | eligible pool snapshot | Exact-search audit sample |
| Impression → open | unique opened items | unique impressions | Dedup by actor/item |
| Like rate | likes | impressions | Diagnostic only; not primary objective |
| Pass/reason | passes by code | impressions/passes | No free text in analytics |
| Match rate | unique matches | actors with impressions and eligible opportunity | Correct for reciprocal exposure lag |
| First message | matches with first delivered message in 24 h | matches | Removed/rejected messages excluded |
| Reply | matches with reply in 48 h | matches with first delivered message | Stronger quality proxy |
| Conversation quality | 4+ alternating allowed messages in 7d | replied matches | Monitor unmatch/block/report |
| Safety | block/report per 100 impressions and matches | exposure/match cohorts | Zero tolerance for eligibility leaks |
| Retention | activated user returns in W1/W4 and has meaningful action | activated cohort | Supply-aware segmentation |

Ranking promotion uses reply/conversation/retention with block/report/unmatch guardrails. A like-rate gain with worse replies or safety is rejected.

## 8. Backfill and replay

Backfill tools are read-only on domain tables and write new versioned analytical events/marts with `is_backfill=true` in a dedicated schema; they never synthesize canonical user actions. Relay replay selects explicit event IDs/time range, records operator/reason in security audit, preserves `event_id`, rate limits sink traffic and provides dry-run counts. Deletion requests propagate to raw/marts through an auditable erasure job.
