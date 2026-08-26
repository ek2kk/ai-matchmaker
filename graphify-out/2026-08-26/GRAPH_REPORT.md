# Graph Report - ai-dating  (2026-08-26)

## Corpus Check
- 295 files · ~97,170 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2137 nodes · 5249 edges · 167 communities (164 shown, 3 thin omitted)
- Extraction: 72% EXTRACTED · 28% INFERRED · 0% AMBIGUOUS · INFERRED: 1450 edges (avg confidence: 0.79)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Settings
- TODO по реализации MVP AI Dating
- [x] 1. Подготовить запускаемые backend и frontend
- [ ] 2. Доставлять canonical events через transactional outbox
- Data model
- devDependencies
- compilerOptions
- Passwordless authentication
- AI Dating MVP: architecture overview
- StatusPage.tsx
- package.json
- Recommendation system v0
- AI and ML boundary
- Deployment and operations
- Event tracking
- Privacy and safety
- API contracts
- Onboarding
- Frontend — agent notes
- Roadmap
- AI Dating MVP: client brief
- AI Dating
- [ ] 12. Экспортировать и удалять пользовательские данные end to end
- [ ] 13. Доказать корректность funnels, supply и experiment assignments
- [ ] 14. Развернуть восстанавливаемую closed beta
- [ ] 3. Реализовать passwordless auth и сохранять consented account state
- [ ] 4. Реализовать structured onboarding и desired-partner preferences
- [ ] 6. Загружать, модерировать и активировать media профиля
- [x] 0. Зафиксировать решения для работающего prototype
- Base
- vite-env.d.ts
- ai-dating
- ClickHouseSink
- null
- Settings
- load_settings
- properties
- config.py
- [ ] 11. Обмениваться moderated messages внутри active matches
- [ ] 5. Добавить review AI-extracted facts и synthetic calibration
- [ ] 7. Обеспечить block, report и moderation actions
- [ ] 8. Генерировать reciprocal heuristic recommendation batches
- [ ] 9. Добавить bounded LLM reranking и воспроизводимые item snapshots
- block.v1.json
- calibration_completed.v1.json
- experiment_assignments
- enum
- fact_reviewed.v1.json
- impression.v1.json
- like.v1.json
- match.v1.json
- message.v1.json
- onboarding_completed.v1.json
- onboarding_started.v1.json
- onboarding_step_completed.v1.json
- open.v1.json
- pass_reason.v1.json
- pass.v1.json
- profile_activated.v1.json
- recommendation_generation_queued.v1.json
- reply.v1.json
- report.v1.json
- unmatch.v1.json
- event_id
- occurred_at
- owner
- recommendation_batch_id
- recommendation_item_id
- schema_version
- TODO по реализации MVP AI Dating
- Base
- accounts/routes.py
- Settings
- producer
- AGENTS.md
- test_consents.py
- Roadmap
- Backend agent instructions
- AI Dating
- _direct_url
- producer
- run_extraction
- test_register.py
- get_actor
- claim_idempotency
- load_settings
- get_actor
- append_consent
- media/routes.py
- test_consents.py
- maybe_activate
- Profile
- AppError
- test_filters.py
- request_fingerprint
- validate_event
- StatusPage.tsx
- accounts/routes.py
- eval.py
- test_register.py
- Account
- build_projection
- issue_session
- deps.py
- privacy/routes.py
- test_consents.py
- claim_idempotency
- Vector
- [x] 8. Генерировать reciprocal heuristic recommendation batches
- [x] 9. Добавить bounded LLM reranking и воспроизводимые item snapshots
- .session_ttl_positive
- profiles/schemas.py
- lock_pair
- producer
- safety/__init__.py
- claim_jobs
- event_name
- owner

## God Nodes (most connected - your core abstractions)
1. `AppError` - 91 edges
2. `Account` - 87 edges
3. `Settings` - 85 edges
4. `load_settings()` - 75 edges
5. `Profile` - 64 edges
6. `key()` - 55 edges
7. `account()` - 53 edges
8. `auth_of()` - 50 edges
9. `get_actor()` - 46 edges
10. `create_sync_engine()` - 40 edges

## Surprising Connections (you probably didn't know these)
- `test_cors_from_env()` --calls--> `load_settings()`  [INFERRED]
  backend/tests/test_config.py → backend/src/ai_dating/config.py
- `test_fake_sink_success_and_retry()` --calls--> `FakeSink`  [INFERRED]
  backend/tests/events/test_clickhouse_sink.py → backend/src/ai_dating/events/fake_sink.py
- `_rerank_or_fallback()` --calls--> `rerank_projection()`  [INFERRED]
  backend/src/ai_dating/jobs/generate_batch.py → backend/src/ai_dating/recommendations/snapshots.py
- `_item_view()` --calls--> `delivery_profile_from_snapshot()`  [INFERRED]
  backend/src/ai_dating/recommendations/delivery.py → backend/src/ai_dating/recommendations/snapshots.py
- `_direct_url()` --calls--> `load_settings()`  [INFERRED]
  backend/alembic/env.py → backend/src/ai_dating/config.py

## Import Cycles
- None detected.

## Communities (167 total, 3 thin omitted)

### Community 0 - "Settings"
Cohesion: 0.08
Nodes (13): local_key_from_download_token(), local_key_from_upload_token(), LocalStore, ObjectStore, Path, S3Store, StoredObject, _b64() (+5 more)

### Community 1 - "TODO по реализации MVP AI Dating"
Cohesion: 0.29
Nodes (7): [x] 10. Доставлять batches, записывать feedback и создавать один match, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 2 - "[x] 1. Подготовить запускаемые backend и frontend"
Cohesion: 0.05
Nodes (44): 1.1. Превратить Python stub в минимальный FastAPI application, 1.2. Добавить единый config, readiness и безопасное логирование, 1.3. Подготовить SQLAlchemy и Alembic без product schema, 1.4. Bootstrap React/Vite SPA и минимальный app shell, 1.5. Соединить SPA с health API, 1.6. Зафиксировать developer workflow и завершить bootstrap, [x] 1. Подготовить запускаемые backend и frontend, Вне scope (+36 more)

### Community 3 - "[ ] 2. Доставлять canonical events через transactional outbox"
Cohesion: 0.05
Nodes (44): 2.1. Зафиксировать event contract и fixtures, 2.2. Сохранить event вместе с domain transaction, 2.3. Поднять raw-table contract ClickHouse и sink adapter, 2.4. Реализовать lease-based outbox relay, 2.5. Добавить retry, isolation и controlled replay, 2.6. Наблюдать outbox и сохранить frontend boundary, [x] 2. Доставлять canonical events через transactional outbox, Вне scope (+36 more)

### Community 4 - "Data model"
Cohesion: 0.05
Nodes (40): 10. Migration and verification rules, 1. Ownership and data classes, 2. Entity relationship diagram, 3. Core identity and profile tables, 4. Onboarding and calibration state, 5. Consent, safety and privacy tables, 6. Recommendation and interaction tables, 7. Reliability support tables (+32 more)

### Community 6 - "devDependencies"
Cohesion: 0.04
Nodes (45): eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, dependencies, react, react-dom, react-router-dom (+37 more)

### Community 7 - "compilerOptions"
Cohesion: 0.08
Nodes (24): compilerOptions, allowImportingTsExtensions, baseUrl, isolatedModules, jsx, lib, module, moduleDetection (+16 more)

### Community 8 - "Passwordless authentication"
Cohesion: 0.11
Nodes (19): 10. Test approach, 11. Risks and tradeoffs, 12. Open questions, 13. Out of scope, 1. Executive summary, 2. Context and scope, 3. System context, 4. Proposed design (+11 more)

### Community 9 - "AI Dating MVP: architecture overview"
Cohesion: 0.11
Nodes (18): 10. Operational targets, 11. Assumptions and open questions, 12. Decision and next step, 1. Abstract, 2. Goals and non-goals, 3. Documentation plan, 4. System context, 5. Critical request lifecycle (+10 more)

### Community 10 - "StatusPage.tsx"
Cohesion: 0.12
Nodes (30): CalibrationStep(), Props, DiscoverabilityStep(), Props, EligibilityStep(), Props, FormErrorSummary(), Props (+22 more)

### Community 11 - "package.json"
Cohesion: 0.12
Nodes (17): required, actor_account_id, conversation_id, event_id, event_name, experiment_assignments, match_id, occurred_at (+9 more)

### Community 12 - "Recommendation system v0"
Cohesion: 0.13
Nodes (15): 1. End-to-end flow, 2.1 Eligibility and hard filters, 2.2 Embedding retrieval, 2.3 Reciprocal heuristic, 2.4 Diversity, freshness and exploration, 2.5 Bounded LLM reranker, 2. Stage contracts, 3. Generation sequence and concurrency (+7 more)

### Community 13 - "AI and ML boundary"
Cohesion: 0.13
Nodes (15): 1. MVP model uses, 2. Data minimization, 3. Extraction contract and guardrails, 4. Embedding contract, 5. Reranking contract, 6. Versioning and observability, 7. Evaluation and launch gates, 8. Human review and recovery (+7 more)

### Community 14 - "Deployment and operations"
Cohesion: 0.15
Nodes (13): 10. Failure modes, 11. Rollout and launch gates, 12. MVP versus next stage, 1. Minimal deployment topology, 2. Environments, 3. Configuration and secrets, 4. Database and migrations, 5. Object storage (+5 more)

### Community 15 - "Event tracking"
Cohesion: 0.15
Nodes (13): 1. Canonical envelope, 2. Required events, 3. JSON contract examples, 4. Versioning and compatibility, 5. Delivery, retries and idempotency, 6. Product events versus security audit, 7. Funnels and metrics, 8. Backfill and replay (+5 more)

### Community 16 - "Privacy and safety"
Cohesion: 0.17
Nodes (12): 10. Audit and proof, 11. Later boundaries, 1. Principles, 2. Consent and privacy controls, 3. Location, age and sensitive attributes, 4. Visibility and authorization, 5. Block, report and moderation, 6. Abuse controls (+4 more)

### Community 17 - "API contracts"
Cohesion: 0.18
Nodes (11): 1. Common rules, 2. Authentication, 3. Onboarding, profile and preferences, 4. Photo lifecycle, 5. Recommendation batches and feedback, 6. Matches, conversations and messages, 7. Block and report, 8. Consent and privacy (+3 more)

### Community 18 - "Onboarding"
Cohesion: 0.20
Nodes (10): 1. Flow, 2. Completion and activation gates, 3. Progressive completion, 4. Free text to reviewed facts, 5. Embedding source projection, 6. Calibration, 7. Drafts, retries and concurrency, 8. Product events and funnel (+2 more)

### Community 19 - "Frontend — agent notes"
Cohesion: 0.20
Nodes (10): Anti-patterns (rejected), Backend integration, Code style (frontend-specific), Configuration, Dependency policy, Frontend — agent notes, Layout, Package manager (+2 more)

### Community 20 - "Roadmap"
Cohesion: 0.16
Nodes (14): AsyncEngine, _direct_url(), run_migrations_offline(), run_migrations_online(), as_async_url(), as_sync_url(), create_migration_engine(), create_runtime_engine() (+6 more)

### Community 21 - "AI Dating MVP: client brief"
Cohesion: 0.22
Nodes (9): 1. Product outcome, 2. Целевые пользователи, 3. Critical journeys, 4. MVP scope, 5. Product rules, 6. Success and guardrails, 7. Acceptance criteria, 8. Decision register (+1 more)

### Community 22 - "AI Dating"
Cohesion: 0.09
Nodes (71): Account, Base, request_id_of(), ConversationMember, commit_like(), _ensure_match(), _event(), _hidden() (+63 more)

### Community 23 - "[ ] 12. Экспортировать и удалять пользовательские данные end to end"
Cohesion: 0.29
Nodes (7): [ ] 12. Экспортировать и удалять пользовательские данные end to end, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 24 - "[ ] 13. Доказать корректность funnels, supply и experiment assignments"
Cohesion: 0.29
Nodes (7): [ ] 13. Доказать корректность funnels, supply и experiment assignments, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 25 - "[ ] 14. Развернуть восстанавливаемую closed beta"
Cohesion: 0.29
Nodes (7): [ ] 14. Развернуть восстанавливаемую closed beta, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 26 - "[ ] 3. Реализовать passwordless auth и сохранять consented account state"
Cohesion: 0.29
Nodes (7): [x] 3. Реализовать local login/password auth и сохранять consented account state, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 27 - "[ ] 4. Реализовать structured onboarding и desired-partner preferences"
Cohesion: 0.29
Nodes (7): [x] 4. Реализовать structured onboarding и desired-partner preferences, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 28 - "[ ] 6. Загружать, модерировать и активировать media профиля"
Cohesion: 0.29
Nodes (7): [x] 6. Загружать, модерировать и активировать media профиля, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 29 - "[x] 0. Зафиксировать решения для работающего prototype"
Cohesion: 0.29
Nodes (7): [x] 0. Зафиксировать решения для работающего prototype, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 31 - "Base"
Cohesion: 0.07
Nodes (48): Session, UUID, SecurityAuditLog, write_audit(), enqueue_event(), Session, UUID, FakeSink (+40 more)

### Community 40 - "ClickHouseSink"
Cohesion: 0.16
Nodes (7): main(), ClickHouseSink, _occurred_at(), _row(), test_clickhouse_duplicate_event_id_inserts(), test_clickhouse_timeout_is_retryable(), test_fake_sink_success_and_retry()

### Community 41 - "null"
Cohesion: 0.13
Nodes (20): format, type, format, type, format, type, actor_account_id, conversation_id (+12 more)

### Community 42 - "Settings"
Cohesion: 0.40
Nodes (4): additionalProperties, $id, $schema, type

### Community 43 - "load_settings"
Cohesion: 0.31
Nodes (17): ClaimedJob, _active_fact(), _backoff(), _mark(), _maybe_facts_step(), _now(), _observe(), process_extract_job() (+9 more)

### Community 44 - "properties"
Cohesion: 0.17
Nodes (12): pattern, type, minLength, type, properties, event_name, producer, properties (+4 more)

### Community 45 - "config.py"
Cohesion: 0.23
Nodes (20): complete(), get_onboarding(), _now(), patch_preferences(), patch_profile(), post_calibration_choice(), post_calibration_complete(), post_calibration_session() (+12 more)

### Community 46 - "[ ] 11. Обмениваться moderated messages внутри active matches"
Cohesion: 0.29
Nodes (7): [x] 11. Обмениваться moderated messages внутри active matches, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 47 - "[ ] 5. Добавить review AI-extracted facts и synthetic calibration"
Cohesion: 0.29
Nodes (7): [x] 5. Добавить review AI-extracted facts и synthetic calibration, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 48 - "[ ] 7. Обеспечить block, report и moderation actions"
Cohesion: 0.29
Nodes (7): [x] 7. Обеспечить block, report и moderation actions, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 49 - "[ ] 8. Генерировать reciprocal heuristic recommendation batches"
Cohesion: 0.11
Nodes (36): claim_jobs(), _now(), datetime, Session, enqueue_job(), datetime, Session, UUID (+28 more)

### Community 50 - "[ ] 9. Добавить bounded LLM reranking и воспроизводимые item snapshots"
Cohesion: 0.14
Nodes (32): pair_with_match(), Session, TestClient, UUID, send(), Session, TestClient, test_block_hides_messages() (+24 more)

### Community 51 - "block.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 52 - "calibration_completed.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 53 - "experiment_assignments"
Cohesion: 0.50
Nodes (4): type, additionalProperties, type, experiment_assignments

### Community 54 - "enum"
Cohesion: 0.50
Nodes (4): enum, privacy_classification, product_pseudonymous, security_restricted

### Community 55 - "fact_reviewed.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 56 - "impression.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 57 - "like.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 58 - "match.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 59 - "message.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 60 - "onboarding_completed.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 61 - "onboarding_started.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 62 - "onboarding_step_completed.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 63 - "open.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 64 - "pass_reason.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 65 - "pass.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 66 - "profile_activated.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 67 - "recommendation_generation_queued.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 68 - "reply.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 69 - "report.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 70 - "unmatch.v1.json"
Cohesion: 0.50
Nodes (3): allOf, $id, $schema

### Community 73 - "event_id"
Cohesion: 0.07
Nodes (57): CredentialsIn, login(), logout(), BaseModel, datetime, Request, Response, Session (+49 more)

### Community 74 - "occurred_at"
Cohesion: 0.67
Nodes (3): format, type, occurred_at

### Community 75 - "owner"
Cohesion: 0.67
Nodes (3): format, type, event_id

### Community 76 - "recommendation_batch_id"
Cohesion: 0.14
Nodes (32): AppError, error_payload(), Any, Exception, _create_preferences(), patch_onboarding_preferences(), accepted_genders(), city_code() (+24 more)

### Community 77 - "recommendation_item_id"
Cohesion: 0.05
Nodes (105): load_settings(), create_sync_engine(), drain_extraction(), drain_jobs(), _grant(), TestClient, test_choice_does_not_emit_interaction_events(), test_complete_requires_all_pairs_and_consent() (+97 more)

### Community 79 - "schema_version"
Cohesion: 0.27
Nodes (23): PhotoUploadIntent, ProfilePhoto, _active_photos(), approved_photo_refs(), approved_photo_urls(), approved_photos(), complete_upload(), create_upload_intent() (+15 more)

### Community 80 - "TODO по реализации MVP AI Dating"
Cohesion: 0.67
Nodes (3): [ ] 0.1. Закрыть gate перед closed beta, TODO по реализации MVP AI Dating, Отложено до измеримого trigger

### Community 85 - "Base"
Cohesion: 0.07
Nodes (54): extract_with_fake(), canonical_value(), _confidence(), event_source_type(), ExtractionRejected, fact_category(), fact_purpose(), _item_code() (+46 more)

### Community 86 - "accounts/routes.py"
Cohesion: 0.24
Nodes (17): _fact_keys(), _features(), activity_freshness(), _adjusted(), cosine_similarity(), cosine_to_unit(), distance_decay(), diversify() (+9 more)

### Community 88 - "Settings"
Cohesion: 0.12
Nodes (21): embedding_model_version(), is_loopback(), is_ready(), require_startup(), Settings, test_dslab_key_selects_gte_base_without_separate_embedding_key(), test_explicit_embedding_credentials_win_over_dslab(), test_fake_embedding_matches_dim_and_is_normalized() (+13 more)

### Community 89 - "producer"
Cohesion: 0.08
Nodes (24): CalibrationSession, CursorList, DemoCard, ExtractionStatus, FactsListResponse, HealthStatus, MatchListItem, MatchSummary (+16 more)

### Community 90 - "AGENTS.md"
Cohesion: 0.33
Nodes (6): Agent instructions, Boundaries, Changes, Commands, Definition of done, Repository state

### Community 91 - "test_consents.py"
Cohesion: 0.16
Nodes (19): embed_text(), embedding_credentials(), extract_chat_completion(), extraction_model_version(), _payload_from_content(), ProviderError, ProviderResult, Exception (+11 more)

### Community 92 - "Roadmap"
Cohesion: 0.22
Nodes (9): Decision gates summary, Explicitly not built in MVP, Phase 0: foundation, Phase 1: closed beta and cold start, Phase 2: recommendation v0 and messaging, Phase 3: measurement and calibration, Phase 4: learned ranking, Phase 5: optional enrichment and agents (+1 more)

### Community 93 - "Backend agent instructions"
Cohesion: 0.29
Nodes (6): Backend agent instructions, Current state, Database, Python and dependencies, Target boundaries, Verification

### Community 95 - "AI Dating"
Cohesion: 0.29
Nodes (7): AI Dating, Checks, Configuration, Install, Local run, Lockfiles, Prerequisites

### Community 97 - "_direct_url"
Cohesion: 0.23
Nodes (23): _complete_event(), complete_onboarding(), complete_view(), _gates(), _latest_granted(), _now(), onboarding_state(), patch_onboarding_profile() (+15 more)

### Community 113 - "producer"
Cohesion: 0.23
Nodes (14): _backoff(), cleanup_media_job(), _mark(), _now(), process_photo_job(), datetime, Session, timedelta (+6 more)

### Community 114 - "run_extraction"
Cohesion: 0.16
Nodes (12): SignedInBar(), absoluteUrl(), PhotoManager(), ProfilePhoto, PublicProfile, env, ErrorBody, isVersionConflict() (+4 more)

### Community 115 - "test_register.py"
Cohesion: 0.37
Nodes (14): _embed_profile(), _existing_login(), _has_embeddings(), _insert_person(), main(), _now(), _profiles_for_logins(), datetime (+6 more)

### Community 116 - "get_actor"
Cohesion: 0.29
Nodes (17): get_actor(), get_facts(), get_other_profile(), get_profile(), list_profiles(), patch_profile(), post_fact(), post_fact_review() (+9 more)

### Community 118 - "claim_idempotency"
Cohesion: 0.19
Nodes (8): configure_logging(), _handle_stop(), main(), main(), _handle_stop(), main(), test_openai_compatible_provider_returns_schema_shaped_json(), test_fake_extraction_does_not_log_raw_text()

### Community 119 - "load_settings"
Cohesion: 0.18
Nodes (39): _action_state(), batch_is_current(), candidate_eligible(), current_batch(), current_batch_response(), _iso(), _item_view(), _latest_ready() (+31 more)

### Community 120 - "get_actor"
Cohesion: 0.18
Nodes (14): claim(), FactsReviewStep(), Props, CodeLabel, FactKeyMeta, ProfileFact, PromptMeta, FactList() (+6 more)

### Community 121 - "append_consent"
Cohesion: 0.33
Nodes (17): calibration_done(), _choice_payload(), _choices(), clear_calibration(), _complete_event(), complete_session(), create_session(), _public_pairs() (+9 more)

### Community 122 - "media/routes.py"
Cohesion: 0.31
Nodes (15): delete_photo_route(), get_object(), get_photos(), patch_photo_route(), post_complete(), post_upload_intent(), put_upload(), Request (+7 more)

### Community 123 - "test_consents.py"
Cohesion: 0.05
Nodes (62): app_version(), create_app(), Request, _request_id_from(), _route_template(), main(), Like, canonical_pair() (+54 more)

### Community 124 - "maybe_activate"
Cohesion: 0.49
Nodes (9): _backoff(), _mark(), _now(), _observe(), process_embed_job(), datetime, Session, timedelta (+1 more)

### Community 128 - "Profile"
Cohesion: 0.20
Nodes (14): AiOperation, parse_rerank_payload(), pin_exploration(), UUID, ValueError, reason_for(), RerankRejected, RerankResult (+6 more)

### Community 129 - "AppError"
Cohesion: 0.26
Nodes (17): _backoff(), _mark(), _now(), _persist(), process_generate_job(), _profile_snapshot(), datetime, Session (+9 more)

### Community 130 - "test_filters.py"
Cohesion: 0.38
Nodes (16): db(), _ids(), _pair(), Session, test_activity_visibility_moderation_privacy(), test_age_must_match_both_ways(), test_distance_uses_tighter_reciprocal_limit(), test_either_direction_block_excludes_pair() (+8 more)

### Community 131 - "request_fingerprint"
Cohesion: 0.26
Nodes (11): delete_block(), get_blocks(), post_block(), post_report(), Request, Response, Session, UUID (+3 more)

### Community 132 - "validate_event"
Cohesion: 0.23
Nodes (12): EventValidationError, _load(), ValueError, _registry(), schema_filename(), validate_event(), test_all_required_events_accept_valid_payload(), test_onboarding_step_allows_null_versions() (+4 more)

### Community 133 - "StatusPage.tsx"
Cohesion: 0.13
Nodes (24): App(), api, ConversationSummary, MessageView, PublicProfileCard, remember(), ApiError, getAccountId() (+16 more)

### Community 134 - "accounts/routes.py"
Cohesion: 0.24
Nodes (14): ActorSnapshot, current_embeddings(), EligibilityError, eligible_candidates(), eligible_sql(), load_actor(), _now(), datetime (+6 more)

### Community 135 - "eval.py"
Cohesion: 0.33
Nodes (10): cohen_kappa(), dataset_hash(), evaluate(), main(), manifest_for(), reviewer_choice(), synthetic_pools(), wilson_lower() (+2 more)

### Community 136 - "test_register.py"
Cohesion: 0.20
Nodes (25): PrivacyControls, Profile, _cursor_id(), get_public_profile(), list_public_profiles(), public_card(), public_profile(), Session (+17 more)

### Community 137 - "Account"
Cohesion: 0.21
Nodes (9): get_db(), Request, Session, require_idempotency_key(), register_error_handlers(), get_onboarding_metadata(), Request, Session (+1 more)

### Community 138 - "build_projection"
Cohesion: 0.30
Nodes (12): get_conversations(), get_messages(), get_one_message(), post_message(), post_read(), Request, Response, Session (+4 more)

### Community 139 - "issue_session"
Cohesion: 0.31
Nodes (13): combine(), RankFeatures, score_all(), score_one(), _id(), UUID, test_cosine_to_unit_maps_minus_one_to_one(), test_diversity_penalizes_shared_fact_theme() (+5 more)

### Community 140 - "deps.py"
Cohesion: 0.26
Nodes (14): request_fingerprint(), get_current_batch(), post_feedback(), post_impression(), post_open(), post_refresh(), Request, Session (+6 more)

### Community 141 - "privacy/routes.py"
Cohesion: 0.24
Nodes (19): Consent, ConsentIn, get_privacy(), patch_privacy_route(), post_consent(), PrivacyPatchIn, BaseModel, Request (+11 more)

### Community 142 - "test_consents.py"
Cohesion: 0.42
Nodes (9): _answer_lines(), build_projection(), _desired_lines(), _fact_lines(), ProfileAnswer, ProfileFact, _self_lines(), test_desired_projection_uses_preferences_and_partner_side() (+1 more)

### Community 143 - "claim_idempotency"
Cohesion: 0.31
Nodes (9): delivery_profile_from_snapshot(), erase_candidate_snapshots(), item_profile_snapshot(), public_scalar_snapshot(), Session, UUID, render_reason(), rerank_projection() (+1 more)

### Community 144 - "Vector"
Cohesion: 0.52
Nodes (6): db(), _pool(), Session, test_erase_nulls_snapshot_content(), test_malformed_payload_falls_back(), test_provider_failure_keeps_heuristic_order()

### Community 145 - "[x] 8. Генерировать reciprocal heuristic recommendation batches"
Cohesion: 0.29
Nodes (7): [x] 8. Генерировать reciprocal heuristic recommendation batches, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 146 - "[x] 9. Добавить bounded LLM reranking и воспроизводимые item snapshots"
Cohesion: 0.29
Nodes (7): [x] 9. Добавить bounded LLM reranking и воспроизводимые item snapshots, Вне scope, Готово, когда, Зачем?, Как проверить, Примечания для агента, Что создаём?

### Community 147 - ".session_ttl_positive"
Cohesion: 0.40
Nodes (3): load_manifest(), manifest_allows(), Self

### Community 148 - "profiles/schemas.py"
Cohesion: 0.57
Nodes (6): _mark(), _now(), process_moderate_message_job(), datetime, Session, UUID

### Community 149 - "lock_pair"
Cohesion: 0.22
Nodes (14): approved_photo_count(), hide_without_photos(), maybe_activate(), _now(), datetime, Session, embedding_status(), enqueue_embeddings() (+6 more)

### Community 153 - "producer"
Cohesion: 0.24
Nodes (12): IdempotencyKey, claim_idempotency(), _lookup(), Session, UUID, Return (row, replay). replay True means identical prior request., get_matches(), post_unmatch() (+4 more)

### Community 158 - "claim_jobs"
Cohesion: 0.29
Nodes (7): RecommendationBatchView, RecommendationItemView, Card(), labelOf(), PASS_REASONS, RecommendationsPage(), REPORT_REASONS

### Community 160 - "event_name"
Cohesion: 0.67
Nodes (3): request_id, minLength, type

### Community 163 - "owner"
Cohesion: 0.67
Nodes (3): minLength, type, owner

## Knowledge Gaps
- **520 isolated node(s):** `ai-dating`, `$schema`, `$id`, `allOf`, `$schema` (+515 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Settings` to `Profile`, `AppError`, `Settings`, `claim_idempotency`, `.session_ttl_positive`, `Roadmap`, `profiles/schemas.py`, `AI Dating`, `lock_pair`, `ClickHouseSink`, `load_settings`, `[ ] 9. Добавить bounded LLM reranking и воспроизводимые item snapshots`, `event_id`, `recommendation_item_id`, `schema_version`, `test_consents.py`, `producer`, `claim_idempotency`, `test_consents.py`, `maybe_activate`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `Account` connect `AI Dating` to `Profile`, `AppError`, `accounts/routes.py`, `test_register.py`, `privacy/routes.py`, `claim_idempotency`, `lock_pair`, `load_settings`, `[ ] 8. Генерировать reciprocal heuristic recommendation batches`, `event_id`, `recommendation_batch_id`, `recommendation_item_id`, `schema_version`, `Base`, `_direct_url`, `producer`, `test_register.py`, `get_actor`, `load_settings`, `append_consent`, `test_consents.py`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `load_settings()` connect `recommendation_item_id` to `test_filters.py`, `accounts/routes.py`, `eval.py`, `ClickHouseSink`, `test_register.py`, `event_id`, `Vector`, `[ ] 8. Генерировать reciprocal heuristic recommendation batches`, `[ ] 9. Добавить bounded LLM reranking и воспроизводимые item snapshots`, `test_register.py`, `Roadmap`, `lock_pair`, `claim_idempotency`, `load_settings`, `Settings`, `test_consents.py`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Are the 88 inferred relationships involving `AppError` (e.g. with `create_account()` and `_invalid()`) actually correct?**
  _`AppError` has 88 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `Account` (e.g. with `Base` and `authenticate()`) actually correct?**
  _`Account` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 35 inferred relationships involving `Settings` (e.g. with `CredentialsIn` and `ProviderError`) actually correct?**
  _`Settings` has 35 INFERRED edges - model-reasoned connections that need verification._
- **Are the 73 inferred relationships involving `load_settings()` (e.g. with `_direct_url()` and `main()`) actually correct?**
  _`load_settings()` has 73 INFERRED edges - model-reasoned connections that need verification._