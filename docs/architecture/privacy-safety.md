# Privacy and safety

> **Status:** technical safety design, not a completed legal compliance program. Jurisdiction-dependent requirements remain `TBD` and block public launch.

## 1. Principles

- Adults 21+ only: account cannot become discoverable until age gate passes.
- Purpose limitation: collect/use data only for an explicit product or safety purpose.
- Data minimization: exact location, DOB, raw text/media and identifiers stay out of analytics/model calls unless required.
- User control: separate consents, fact visibility, discoverability, export and deletion.
- Fail closed: unknown eligibility, moderation or consent state never exposes a profile.
- Symmetric safety: block removes access/recommendations/messaging in both directions without notifying the subject of reason.

## 2. Consent and privacy controls

Required receipts are versioned and append-only: terms/privacy acknowledgement, dating profile visibility, AI matching. Optional purposes have separate switches: product analytics where legally required, model improvement/evaluation, calibration use, future social enrichment. Bundled consent is forbidden when purposes can be separated.

Withdrawal takes effect for new processing immediately, disables dependent features and queues deletion/anonymization of derived data. It cannot erase already completed security obligations without legal review. UI shows current purpose, policy version, decision time and consequences.

Facts default `private`; `matching_only` permits minimized rank/model projection but not candidate display; `eligible_only` permits display after reciprocal eligibility. There is no “public internet” profile in MVP.

## 3. Location, age and sensitive attributes

- Store DOB restricted; return computed age only. Never return DOB to another user.
- Request coarse chosen location, not background/continuous GPS. `location` is used server-side for distance; candidate sees `public_area_code` and optional distance band, never coordinates.
- Gender identity/orientation/preferences are sensitive. Compatibility uses explicit accepted-gender intent in both directions, not model inference.
- **TBD-SEC01:** launch jurisdiction determines age assurance, parental/minor handling, retention, export/deletion SLA and special-category data basis.
- **Decision P02:** MVP uses user-declared DOB and coarse Moscow location without continuous GPS; stronger age/location assurance remains a closed-beta risk review.
- **TBD-SEC04:** threat model/legal review decides whether message/report/location columns need application-level encryption and separate key custody beyond managed at-rest encryption.

## 4. Visibility and authorization

Every profile read requires an actor from an active application session and server-side join against current account/profile state, reciprocal eligibility where applicable, blocks and moderation. Clients never query dating tables directly. Database credentials are not an authorization mechanism.

Visibility states:

| State | Recommendation | Existing match/message | Owner access |
|---|---|---|---|
| `hidden` onboarding | No | None | Draft edit |
| `eligible` approved | Yes after all rules | Yes | Full |
| `paused` | No new exposure | Existing conversations remain in MVP until user closes | Full |
| `suspended` | No | No message/profile access; counterpart sees generic unavailable state | Appeal/status only |
| `deletion_pending/deleted` | No | Closed/removed | Export/status until erase window |

**Decision (MVP):** pause preserves existing conversations while stopping discovery. Suspension denies conversation access; implementation must not expose the enforcement reason to the counterpart.

## 5. Block, report and moderation

`block` transaction:

1. creates active block and restricted audit;
2. invalidates ready recommendation items both directions;
3. ends active match/conversation as `blocked`;
4. denies profile/message access immediately;
5. emits minimized product event after commit.

`report` always includes block behavior, accepts allowlisted reason + optional details/evidence, opens/links a moderation case and returns a generic success. The reported person is not told reporter identity or details.

Photo/text lifecycle is `pending → approved|rejected`; content is private while pending. Automated high-confidence rejection is appealable; ambiguous/severe cases are held for human review. Existing approved content can be re-held when a credible report or policy change requires it.

## 6. Abuse controls

Initial limits are configuration values with security owner approval:

| Action | Default beta limit | Failure behavior |
|---|---:|---|
| Local auth attempts | Loopback-only server; generic invalid credentials | No account enumeration; local-password mode fails startup outside local environment |
| Profile edits | 30/hour/account | `429` with retry time |
| Photo uploads | 10/day/account, 10 MB each | Reject before signed upload/processing |
| Batch generation | 2 successful/day/account | Serve current batch or cooldown |
| Likes/passes | Bounded by exposed items | Reject IDs not owned/exposed |
| Messages | 20/minute and 200/day/account (**Assumption**) | Temporary throttle; severe spam escalation |
| Reports | 20/day/account; never block genuine severe report path | Queue abuse review, preserve block |

Object upload validates MIME by content, size, dimensions and object key ownership; strips metadata and creates safe derivatives. Signed URLs are short-lived. Virus/malware scan requirement for image-only MVP is `TBD-SEC03`; format decode/re-encode and content moderation are mandatory.

## 7. Employee and operator access

Separate staff identity, least-privilege roles and MFA are required. No direct production database browsing for routine support. Admin UI exposes minimum case data; profile/message/report access needs case/ticket reason and writes `security_audit_log`. Break-glass access expires, alerts security and is reviewed. Service credentials live in managed secret stores, never repository, frontend env or logs. No case-view or resolve HTTP endpoint ships until that staff identity/MFA model is approved; reports still open restricted pending cases.

## 8. Retention, export and deletion

Proposed conservative defaults pending legal review:

| Data | Default | Deletion behavior |
|---|---:|---|
| Active profile/messages | Account lifetime | Delete on account request, subject to explicit safety/legal hold |
| Deleted account recovery window | 7 days | Profile hidden immediately; hard erase after window |
| Delivered outbox rows | 7 days | Purge after verified sink delivery |
| Product raw events | 13 months | Delete/anonymize account identifiers on valid request |
| Model raw sampled payload | Off by default; ≤30 days if approved | Expiring restricted store |
| Reports/audit/evidence | `TBD-SEC01` | Case/legal basis specific; access remains restricted |
| Media objects/derivatives | Account/photo lifetime | Queue erase, verify object deletion and CDN expiry |

Export is an authenticated asynchronous job producing a short-lived encrypted archive of user-authored/profile, consent, match/message and action data where applicable. It excludes other users' private data and internal safety signals. Deletion is idempotent, auditable and retries partial media/provider/analytics erasure until terminal success.

## 9. Safe failure scenarios

| Failure | Safe behavior |
|---|---|
| Moderation provider down | New content remains pending/non-public |
| Consent lookup unavailable | No new exposure/model processing |
| Block write succeeds, event sink down | Enforcement works from Postgres; outbox retries |
| Signed URL leak | Short expiry; revoke/rotate object key when reported |
| Employee tool unavailable | Product remains usable; severe report SLA pages operator |
| Analytics deletion fails | Retry + alert; do not mark deletion complete |
| Model produces sensitive reason | Reject model output; heuristic reason/fallback |

## 10. Audit and proof

Security tests cover cross-account IDOR, block symmetry, stale batch delivery, conversation membership, signed upload ownership, consent withdrawal and deletion retries. Quarterly access review and restore/delete drills are **proposed**; cadence/owner is `TBD-OPS01`. Severe safety incident response, notification and escalation runbook must exist before closed beta invites.

## 11. Later boundaries

No social network import, scraping or display of people who have not knowingly consented. Any future connector requires source-specific opt-in, data subject rights, provenance, purpose/retention, revocation propagation and a separate review. Agents may prepare suggestions only after a separate authorization design; no message, like, profile edit or external action without explicit user confirmation.
