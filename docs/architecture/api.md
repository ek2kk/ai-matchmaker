# API contracts

> **Style:** JSON over HTTPS under `/v1`; opaque application session; server derives actor and service fields.  
> **Status:** local prototype contracts are implemented; beta-only contracts below remain planned until their listed gates are closed.

## 1. Common rules

- All domain endpoints require `Authorization: Bearer <opaque session token>`. Backend hashes the token, loads an unexpired/non-revoked `auth_sessions` row and derives `account_id`; browser deployments may use an equivalent `HttpOnly Secure SameSite` cookie.
- IDs are UUID strings; timestamps are RFC3339 UTC. Client timestamps are metadata only and never canonical `occurred_at`.
- JSON requests reject unknown fields. Actor/subject, rank, score, reason snapshot, moderation, versions and event fields are server-owned.
- State-changing create/action endpoints require `Idempotency-Key` UUID. PATCH uses `expected_version`; identical retry is safe, different payload for the same key is `409`.
- Standard error:

```json
{
  "error": {
    "code": "version_conflict",
    "message": "Profile changed; reload and retry.",
    "request_id": "req_01K3J2TQ8G",
    "details": {"current_version": 4}
  }
}
```

Error codes: `validation_error` 422, `unauthenticated` 401, `forbidden` 403, `not_found` 404 (also used to avoid cross-account enumeration), `version_conflict`/`idempotency_conflict` 409, `rate_limited` 429, `generation_pending` 202 status payload, `dependency_unavailable` 503. Internal/provider detail is never returned.

List endpoints use `?limit=` with bounded default/max and opaque server cursor `?after=`. Response shape is `{"items": [...], "next_cursor": null|string}`. Cursors encode stable sort keys and query version; clients must not edit them.

## 2. Authentication

Detailed invariants are defined in [authentication design](../authentication/design.md).

| Endpoint | Auth / idempotency | Contract |
|---|---|---|
| `POST /v1/auth/local/register` | Public, local-only + idempotency | `{login,password}`; creates a test account and returns `{account_id,session_token,expires_at}`. Duplicate login returns `409 login_unavailable`. |
| `POST /v1/auth/local/sessions` | Public, local-only + idempotency | `{login,password}`; returns a fresh opaque session or generic `401 invalid_credentials`. |
| `POST /v1/auth/telegram/sessions` | Public in beta + idempotency | `{init_data}`; verifies Telegram signature/freshness and invite admission for a new identity, then returns `{account_id,session_token,expires_at}`. |
| `DELETE /v1/auth/sessions/current` | Authenticated + idempotency | Revokes current session and returns `204`. |

`local_password` mode is refused outside local loopback. Beta accepts only verified Telegram Mini App `initData` no older than five minutes; one Telegram user ID maps to one active account. A new identity additionally requires a valid one-time 32-byte random invite from `start_param`; only its `SHA-256` hash is stored, so a separate signature is unnecessary. Existing identities can start a new 24-hour revocable application session without another invite. A global admission stop affects new accounts only.

## 3. Onboarding, profile and preferences

| Endpoint | Auth / idempotency | Request | Response / validation / errors |
|---|---|---|---|
| `GET /v1/onboarding` | owner | none | Draft, gates (`facts_reviewed`, `calibration_done` included), `pending_jobs`, `extraction` status and server-computed completion; no other account |
| `PATCH /v1/onboarding/profile` | owner; optimistic version | editable self fields including `search_mode`, `city_code` and coarse `area_code`, `expected_version` | Updated private profile; beta accepts only `dating`, age 21–35 and Moscow; area is never returned to candidates; `409` stale version |
| `PATCH /v1/onboarding/preferences` | owner; optimistic version | accepted genders, age min/max, `search_mode`, `city_codes`, dating-only goals, `expected_version` | Updated preferences; beta validates age range 21–35 and Moscow city equality; distance is not a beta input |
| `GET /v1/profile` | owner | none | Full owner projection including fact visibility and moderation status |
| `GET /v1/profiles` | local developer/demo only; cursor | `limit` (default/max 50), `after` | Directory of synthetic/debug profiles for the developer. It is disabled outside local/demo environments and is never a beta user surface. |
| `GET /v1/profiles/{profile_id}` | local developer/demo only | none | Debug detail for the synthetic directory. Beta has no profile-by-ID discovery surface; candidate data is serialized only from an authorized recommendation item snapshot. |
| `PATCH /v1/profile` | owner; optimistic version | editable bio/name/answers/visibility controls | Updated owner projection; rank-relevant version bump; answer save enqueues `extract_profile_facts` |
| `GET /v1/profile/facts` | owner; cursor | `state=pending\|current\|confirmed\|rejected`, `limit`, `after` | Owner facts with minimized provenance (`fact_id`, `profile_side`, `fact_code`, scalar `value`, `preference_strength`, `review_state`, `visibility`, `purpose`, `confidence`, `provenance_excerpt`, versions). `extraction` status is included. Cross-account `404` |
| `POST /v1/profile/facts` | owner; idempotency | `fact_code`, scalar `value`, optional `profile_side`, `preference_strength`, `visibility` | Manual structured fact (`source_type=form`, confirmed, default `matching_only`). Supersedes any active fact for the same `(side, code, value)` |
| `POST /v1/profile/facts/{fact_id}/review` | owner; idempotency | `decision: accept\|edit\|reject`, optional scalar `value`, `visibility`, `expected_source_version` | `accept` confirms pending as `matching_only`; `edit` inserts confirmed `user_edit` and supersedes; `reject` inactivates pending or confirmed. Stale source `409`; other account `404` |
| `POST /v1/onboarding/calibration-sessions` | local prototype only; idempotency | empty object | Creates/returns versioned synthetic session and five labelled demo pairs; no real profile IDs. Disabled in beta. |
| `POST /v1/onboarding/calibration-sessions/{session_id}/choices` | local prototype only; idempotency | `demo_pair_id`, `selection: left\|right\|neither`, optional allowlisted `reason_code` | Upserts one pair choice; never creates real impression/like/pass |
| `POST /v1/onboarding/calibration-sessions/{session_id}/complete` | local prototype only; idempotency | `decision: complete\|skip` | `complete` requires all pairs chosen and current `calibration=granted`. `skip` is immediate. Emits canonical `calibration_completed` |
| `POST /v1/onboarding/complete` | owner; idempotency | `expected_profile_version`, `expected_preferences_version` | Commits user-controlled completion. Returns `202 profile_activation_pending` while moderation runs, `202 generation_pending` if already activated/queued, or same `200` result on retry; only missing/invalid user inputs are `422` |
| `POST /v1/profile/publish` | local developer/demo only; idempotency | empty object | Local prototype activation without photos. It is disabled outside local/demo environments; beta activation requires approved photo moderation. |

Profile PATCH example:

```json
{
  "expected_version": 3,
  "display_name": "Alex",
  "gender_code": "woman",
  "orientation_code": "heterosexual",
  "search_mode": "dating",
  "relationship_goal_code": "serious_relationship",
  "city_code": "moscow"
}
```

The response never echoes precise location outside the owner's private projection. Controlled vocabularies are served by `GET /v1/metadata/onboarding` and include `fact_keys`, `calibration_version`, and `calibration_reason_codes`; values are versioned and localized labels stay client-facing. Withdraw `calibration` consent to clear choices and `signal_snapshot`; the skip marker remains so onboarding can complete.

## 4. Photo lifecycle

| Endpoint | Auth / key | Contract |
|---|---|---|
| `POST /v1/profile/photos/upload-intents` | owner + idempotency | Request `{content_type, byte_size, content_sha256}`. Validate quota/type/size; return short-lived signed upload URL + opaque `upload_intent_id`, not arbitrary object key. |
| `POST /v1/profile/photos/{upload_intent_id}/complete` | owner + idempotency | Verify object exists, size/hash/ownership; create `profile_photos` pending row and moderation job. |
| `GET /v1/profile/photos` | owner | Ordered metadata and moderation states; signed owner preview URLs. |
| `PATCH /v1/profile/photos/{photo_id}` | owner + expected version | Change position only; collision validated transactionally. |
| `DELETE /v1/profile/photos/{photo_id}` | owner + idempotency | Soft delete immediately, enqueue object cleanup; cannot leave eligible profile below photo gate without hiding it. |

Only approved safe derivative URLs enter candidate payloads. Upload URLs accept one object and expire; client cannot promote moderation state.

## 5. Recommendation batches and feedback

### `GET /v1/recommendation-batches/current`

Returns `200` ready batch, `202` pending, or `200` with `status=insufficient_supply`. Delivery rechecks eligibility before serializing.

```json
{
  "recommendation_batch_id": "a3cc1fd0-4cc2-44ed-97d1-55db8ec047cd",
  "status": "ready",
  "expires_at": "2026-08-26T10:15:00Z",
  "items": [
    {
      "recommendation_item_id": "a63d0bd6-aee5-4f79-b60e-2dcd66cd42e2",
      "rank": 1,
      "profile": {
        "profile_id": "d2a85c90-a652-42fd-b8e1-93af2e278922",
        "display_name": "Sam",
        "age": 30,
        "answers": [],
        "photo_urls": []
      },
      "reason": {"version": 1, "codes": ["shared_goal", "prompt_theme"], "text": "..."}
    }
  ]
}
```

The profile/reason fields come from the persisted item snapshot, not a live profile join. API returns the item only when current candidate profile version still matches and its snapshot photo IDs remain approved; otherwise it omits/refills. Each item may include actor-owned `opened` and `decision` (`like`/`pass`/null). No candidate account ID, coordinates, score, model/prompt version or moderation signal is returned.

| Endpoint | Auth / key | Request and behavior |
|---|---|---|
| `POST /v1/recommendation-items/{item_id}/impression` | batch owner + idempotency | `{surface}`; server gets batch/rank/subject, inserts unique exposure and event. Returns `{exposure_id, recommendation_item_id}`. Any duplicate for the same item returns the existing success without another event; `409 already_exposed_elsewhere` is only for inconsistent different-item state. |
| `POST /v1/recommendation-items/{item_id}/open` | batch owner + idempotency | `{surface}`; requires valid impression, records first open. Returns `{action_id, recommendation_item_id}`. |
| `POST /v1/recommendation-items/{item_id}/feedback` | batch owner + idempotency | `{action: like|pass, reason_code?: enum}`; requires impression/current item. One terminal decision per item; conflicting retry is `409`. Reason allowed only for pass (`not_my_type`/`photos`/`location`/`other`). Returns `{action_id, recommendation_item_id, decision}` and, for like, `match: {match_id, conversation_id, matched_at} \| null`. |
| `POST /v1/recommendation-batches/current/refresh` | owner + idempotency | Queues normal slot 1 after expiry/consumption; slot 2 only after every slot-1 item has terminal feedback. Never infinite pagination. |
| `POST /v1/recommendation-batches/current/exploratory` | owner + idempotency | Available only from current `insufficient_supply`; queues a clearly labelled exploratory batch from the fully eligible/no-repeat pool. |

If block/moderation makes item stale, action returns `404` and hides it. The client cannot feed arbitrary candidate IDs into actions.

## 6. Matches, conversations and messages

| Endpoint | Contract |
|---|---|
| `GET /v1/matches?state=active&limit=20&after=...` | Authenticated member; cursor by `(matched_at,match_id)`, public-safe counterpart projection |
| `POST /v1/matches/{match_id}/unmatch` | Member + idempotency; active → unmatched, closes conversation and hides it from both interfaces; repeated key stable |
| `GET /v1/conversations?limit=20&after=...` | Member summaries only; cursor by last activity |
| `GET /v1/conversations/{conversation_id}/messages?limit=50&after=...` | Active/authorized member; allowed history only, cursor by `(allowed_at,message_id)` so async moderation cannot insert behind the cursor |
| `POST /v1/conversations/{conversation_id}/messages` | Active member + idempotency; `{client_message_id, body}`; synchronous policy/rate checks then immediate delivery and post-moderation. Before the first reply by the other participant, sender may create at most three messages. |
| `GET /v1/conversations/{conversation_id}/messages/{message_id}` | Member; allowed message for either member; held/rejected/removed status only to its sender |
| `POST /v1/conversations/{conversation_id}/read` | Member + idempotency; `{last_read_message_id}` must belong to conversation |

Allowed conversation history is ordered by server `allowed_at,message_id`. Post-moderation may remove already delivered content after high-confidence policy violation or report; the removal is reflected in both interfaces without disclosing safety signals. Idempotency additionally uses unique `(sender_account_id,client_message_id)`. A block makes conversation/profile/message endpoints return `404` to both sides except the blocker can see its own block settings.

## 7. Block and report

| Endpoint | Request | Behavior |
|---|---|---|
| `POST /v1/blocks` | `Idempotency-Key`; exactly one of `{profile_id, match_id}`, optional `reason_code` | Server resolves subject through an actor-scoped current profile or existing relationship, atomically blocks/invalidate/ends relationships; generic `204` |
| `DELETE /v1/blocks/{block_id}` | owner + idempotency | Ends block; does not restore old match, conversation or recommendation exposure |
| `GET /v1/blocks?limit=...&after=...` | owner | Minimal list sufficient to manage unblock; no subject private state |
| `POST /v1/reports` | `Idempotency-Key`; `{profile_id, message_id?, reason_code, details?}` | Validates actor access, creates report + block + audit; returns `{report_id,status:"received"}` |

Report accepts no arbitrary evidence object key; attachments, if later required, use a restricted upload intent. Rate limits never prevent the accompanying block.

## 8. Consent and privacy

| Endpoint | Contract |
|---|---|
| `GET /v1/privacy` | Current controls, active consent receipts/policy versions, export/deletion status |
| `POST /v1/consents` | Idempotency; `{purpose, policy_version, decision}` with server allowlist/current version; appends receipt |
| `PATCH /v1/privacy` | Expected version; `{discoverable?, show_distance?, allow_ai_matching?, allow_product_analytics?}`; dependent visibility revalidated |
| `POST /v1/privacy/exports` | Idempotency; queues one export, returns `202 {export_id,status}`; completed download uses short-lived URL after re-auth |
| `POST /v1/privacy/deletion-requests` | Idempotency + recent re-auth; immediately hides account and returns recovery/erase schedule |
| `DELETE /v1/privacy/deletion-requests/current` | Recent re-auth within recovery window; restores only if safety state allows |

Withdrawing AI matching hides discovery and deletes/invalidates derived embeddings/batches. Withdrawing optional analytics affects future collection and queues required historical action according to jurisdiction policy.

## 9. Authorization and contract proof

Each handler uses actor from a verified active session and loads resource through actor-scoped query, not `get(id)` followed by a best-effort check. Contract tests cover auth replay/exemption expiry, unknown fields, cross-account IDs, stale versions, reused idempotency keys, stale recommendation items, block symmetry, cursor tampering and provider-independent error shapes. API docs/OpenAPI are generated from implementation models when code exists; this document remains the behavior contract.
