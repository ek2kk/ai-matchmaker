# Repository review

Дата: 2026-08-26  
Scope: весь tracked source tree (`backend/`, `frontend/`, migrations и product contracts), без lockfiles и generated output.

## Findings

### [P1] Не выдавать кандидата повторно после `impression` — `backend/src/ai_dating/recommendations/delivery.py:161`

`current_batch()` вызывает `eligible_candidates(..., skip_exposure=True)`, поэтому кандидат с уже созданной `recommendation_exposure` остаётся в ответе текущего batch. Это воспроизводится простым `GET current → POST impression → GET current`: тот же card снова возвращается клиенту. Нарушает `INV-4` и `AC-P04`; при повторном открытии страницы SPA вновь рендерит этот card. При delivery нужно исключать exposed pair и ставить refill, сохранив отдельную проверку с `skip_exposure=True` только для уже начатых feedback/open операций.

### [P1] Убрать публичный directory, обходящий reciprocal eligibility — `backend/src/ai_dating/profiles/public.py:82`

`GET /v1/profiles` возвращает до 50 любых discoverable profiles, а `GET /v1/profiles/{id}` раскрывает полный public profile. Оба пути проверяют только visibility/moderation/block, но не возраст, gender intent, distance, goal, AI-matching consent или факт recommendation exposure. Любой authenticated onboarding account может пагинировать весь supply; фронтенд прямо предоставляет этот infinite directory. Это противоречит `INV-1`, privacy contract («нет public internet profile») и MVP non-goal «no infinite swipe feed». Доступ к detail должен идти только через actor-owned, live-eligible recommendation item (либо endpoint и страницы directory следует удалить).

### [P1] Обновлять `last_active_at` при реальной активности — `backend/src/ai_dating/accounts/service.py:139`

`last_active_at` задаётся лишь при регистрации и нигде больше не обновляется. Через `ACTIVITY_DAYS = 30` даже пользователи, которые регулярно логинятся, читают batch и переписываются, перестают попадать в `eligible_sql`, а их activity score навсегда деградирует. Обновляйте timestamp на session authentication и, с bounded write-rate, на authenticated activity; добавьте integration test с пользователем старше cutoff, который недавно проявил активность.

### [P2] Реализовать или перестать enqueue-ить invalidation job после отзыва AI consent — `backend/src/ai_dating/privacy/service.py:215`

При withdrawal `ai_matching` создаётся `invalidate_derived_matching`, но этот job type отсутствует в allowlist `claim_jobs()` и в dispatcher worker. Он остаётся `queued` навсегда, поэтому embeddings, ready batches и сохранённые snapshots не удаляются/не инвалидируются, хотя API contract прямо обещает это при отзыве consent. Нужен handler с очищением derived matching data и тест, который запускает worker до terminal job state.

### [P2] Применить `allow_product_analytics` к outbox — `backend/src/ai_dating/events/enqueue.py:35`

`enqueue_event()` безусловно сохраняет product events, а privacy control по умолчанию `false`; изменение/withdrawal `product_analytics` также не влияет на этот путь. Например, registration уже помещает `onboarding_started` в outbox, хотя пользователь не дал optional analytics consent. Разведите mandatory security audit и optional product telemetry, затем проверяйте актуальный consent перед product-event insert (и определите отдельную очередь исторического удаления для withdrawal).

## Verification

- `backend`: `uv run ruff check .` и `uv run ruff format --check .` — passed.
- `frontend`: `pnpm lint`, `pnpm tsc --noEmit`, `pnpm build` — passed.
- `uv run pytest -q` был запущен дважды, но runner в этой среде завершал вывод после промежуточного прогресса (`34%`) без итоговой строки; результат полного suite нельзя считать подтверждённым по этому логу. Целевые Postgres integration tests нужно прогнать в настроенном DB environment.

## Residual risks

- Production-only flows (human moderation, export/deletion, staff access) ещё не реализованы полностью и документированы как closed-beta gates/TBD; это не учтено как defect текущего local prototype.
- `PONYTAIL_AUDIT.md` уже находился как untracked файл после начала аудита; его содержимое не менялось.
