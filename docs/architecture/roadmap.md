# Roadmap

> **Current state:** the local prototype is complete. The next work is beta hardening; each phase starts only after its entry conditions and stops if failure criteria show supply, safety or contract quality is insufficient. Calendar dates and team capacity are `TBD`.

## Phase 0: foundation

**Goal:** create the smallest operable product skeleton and prove privacy/safety invariants before real users.

| Item | Definition |
|---|---|
| Entry | Product approves `TBD-P01`, `TBD-P02`, `TBD-P04`; founder is the named product, platform, CI/CD, Trust & Safety and incident-response owner |
| Deliverables | Backend/frontend bootstrap; local login/password and DB sessions; initial Alembic schema/grants; private Yandex Object Storage; config/secrets; account/profile/preferences/consent; outbox/ClickHouse path; logs/metrics/traces; staging |
| Proof | Cross-account auth tests, migration/restore drill, consent withdrawal, media isolation, event dedup, no sensitive logging |
| Success | Internal users complete structured onboarding; domain/event state reconstructs correctly |
| Failure / stop | Age/location or block enforcement cannot be proved; no transition to closed beta until legal, safety SLA and recovery gates are closed |
| Main risk | Bootstrap expands into platform work; reject infrastructure without a current launch gate |

## Phase 1: closed beta and cold start

**Goal:** prove a narrow market has enough mutually eligible supply and users finish onboarding.

| Item | Definition |
|---|---|
| Entry | Foundation gates pass; approved production SMS OTP, waitlist admission by reciprocal-eligibility graph, capped invite cohort and incident runbook ready |
| Deliverables | `dating`-only 21–35 Moscow onboarding, reviewed facts, photo/text moderation, profile visibility, blocks/reports, MFA operator queue, supply dashboard and kill switches; synthetic calibration remains prototype-only |
| Proof | Funnel events reconcile with DB samples; demo actions cannot create real interaction; safety SLA exercised |
| Success | ≥70% onboarding completion and ≥20 eligible candidates for 80% of activated users in target segment |
| Failure / stop | Eligible supply target missed after controlled acquisition, severe incident lacks response, or users confuse demo profiles with real people |
| Main risk | Ranking work masks supply problem; measure market density before model sophistication |

## Phase 2: recommendation v0 and messaging

**Goal:** deliver small reproducible batches that create safe reciprocal conversations.

| Item | Definition |
|---|---|
| Entry | Stable eligible supply and reviewed onboarding data; HNSW/exact recall benchmark exists |
| Deliverables | Reciprocal eligibility, embeddings, transparent heuristic and diversity, optional bounded LLM rerank, two gated daily batches, explicit exploratory fallback, batch/item snapshots, exposure/no-repeat, like/pass/match, post-moderated conversations/messages |
| Proof | Zero filter/block/moderation leaks; concurrent likes create one match; LLM failure falls back; stored batch reconstructs exposure |
| Success | p95 generation <30 s, first batch <60 s, ≥50% matches send first message; baseline reply/safety measured |
| Failure / stop | Any safety leak, p95 >60 s, provider cost exceeds approved cap, LLM shows no offline gain over heuristic |
| Main risk | Like optimization degrades conversation/safety; promote only with reply and safety guardrails |

## Phase 3: measurement and calibration

**Goal:** establish trustworthy evidence before learned ranking.

| Item | Definition |
|---|---|
| Entry | Event schemas stable through one beta cycle; deletion/consent propagation verified |
| Deliverables | ClickHouse raw/marts, funnel and eligible-recall dashboards, evaluation sets, experiment assignments, cost/latency/safety scorecards, replay/backfill tools |
| Proof | Metric recomputation from canonical events, dedup under repeated delivery, experiment exposure integrity, no raw sensitive fields in analytics |
| Success | Stable semantics/sample sufficient for predeclared experiment analysis; measured heuristic/LLM incremental value |
| Failure / stop | Schema churn prevents comparable cohorts, data leakage/consent gap, or missing counterfactual/exposure context |
| Main risk | Dashboard confidence exceeds data quality; require reconciliation and uncertainty reporting |

## Phase 4: learned ranking

**Goal:** improve reciprocal conversation quality only when data supports it.

| Item | Definition |
|---|---|
| Entry | Predeclared sample-size gate, consent/legal approval, leakage/bias review, stable reply/safety labels |
| Deliverables | Offline dataset pipeline, simple learned ranker, shadow scoring, model/version registry contract, canary/rollback; feature store only if proven necessary |
| Proof | Offline gain over v0, no hard-filter path, shadow latency/cost, online guardrails and rollback drill |
| Success | Statistically credible improvement in reply/conversation proxy with non-inferior block/report/unmatch and retention |
| Failure / stop | Like-only gain, subgroup/supply harm, feature staleness, unacceptable cost/latency or weak rollback |
| Main risk | Feedback loops/popularity bias; keep exposure logging and capped freshness, then add exploration only after a separate data/safety decision |

## Phase 5: optional enrichment and agents

**Goal:** consider new value only through explicit consent and action boundaries.

| Item | Definition |
|---|---|
| Entry | Separate product case, DPIA/legal/security review as applicable, source/API terms, data-subject consent and revocation design |
| Deliverables | Source-specific opt-in/provenance/deletion; agent suggestions with scoped tools and confirmation before side effects |
| Proof | No non-user/scraped data, revocation propagates, staff/model access audited, action confirmation cannot be bypassed |
| Success | Incremental user outcome outweighs privacy, safety, cost and support load |
| Failure / stop | Consent is ambiguous, source data includes uninformed people, or agent can message/like/edit without confirmation |
| Main risk | Secondary use violates user expectations; default remains no enrichment/agent |

## Explicitly not built in MVP

- Kafka, Redis/Celery, domain microservices, multi-region active-active;
- infinite swipe feed, boosts/payments, voice/video;
- learned ranking, feature store, realtime training platform;
- social scraping/import, people enrichment without informed consent;
- autonomous agents or automatic messages/likes;
- real-profile calibration without separate revocable `calibration_use` consent;
- external schema registry while one backend repository owns all producers.

## Decision gates summary

| Gate | Promote when | Stay/rollback when |
|---|---|---|
| Foundation → beta | Safety, consent, restore, event and moderation proof complete | Any blocking owner/policy TBD remains |
| Beta → RecSys v0 | Narrow-market eligible supply is dense enough | Acquisition cannot fix reciprocal supply |
| Heuristic → LLM rerank | Human/offline gain within cost/latency | Invalid/fallback rate or no incremental quality |
| v0 → learned ranker | Stable consented outcomes and safe shadow proof | Like-only gain or safety/retention regression |
| Direct outbox → Kafka | >100 events/s, >3 consumers, or lag/SLO trigger | One sink remains operationally simple |
| Modular monolith → services | Independent SLO/scale/release need is measured | Shared ownership/transactions still dominate |
