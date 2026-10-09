# Backlog MVP AI Matchmaker

> **Статус:** открытые задачи реализации.
> **Выполненное:** [архив завершённых задач](todos-completed.md).
> **Правило:** выполнять сверху вниз. Каждая задача должна завершаться одним сфокусированным и проверенным PR. Нерешённые legal, safety, SLO и cost вопросы блокируют closed beta, но не локальный работающий prototype.

> Решения из `todos-completed.md` — исторические. Задачи `0.2`–`0.5` явно заменяют их prototype-only ограничения для beta и не переписывают архив.

Команды после задачи 1 — в [README.md](README.md). CI (`TBD-INF03`) не подключён.

## [ ] 0.1. Закрыть gate перед closed beta

- Triage: `ready-for-human`

- Техническая retention/export/deletion policy утверждена: 7-day recovery/outbox, 13-month anonymized product events, raw model payload off (≤30 days только с отдельным approval); legal review до первого real-user invite утверждает legal basis и retention reports/audit/evidence для РФ.
- Founder — единственный owner moderation queue и incident response; backup owner отсутствует и обязателен до public launch. Severe incident: immediate kill switch, acknowledgement ≤30 min, containment ≤2 h.
- Подтвердить provider-managed backup capabilities и принять RPO ≤24 h / RTO ≤24 h.
- Telegram admission policy утверждена: verified 5-minute `initData`, 24-hour application session, one-time 32-byte hashed invite with 7-day expiry, 100 active-account cap и reciprocal-supply reserve ≥20. Пересмотр SMS/additional verification только при legal requirement, ≥3 confirmed ban-evasion incidents за 7 дней либо coordinated abuse у ≥10% admitted accounts.
- Утвердить extraction quality gate и DS Lab/auth budget **до** первого real-user invite.
- Выполнить security/privacy/restore drills; только затем разрешать реальные анкеты и приглашения.

## [ ] 0.2. Добавить Telegram auth и invite-only admission

- Triage: `needs-info`

### Что создаём?

Заменяем local-password boundary в beta на проверку Telegram Mini App `initData`, DB-backed application session и controlled waitlist admission для московской `dating` cohort 21–35.

### Готово, когда

- Local-password endpoints и fixed demo accounts физически недоступны вне local/demo environment.
- Один Telegram user ID создаёт не более одного active account; `initData` не старше 5 минут, session живёт 24 часа, а новый account требует одноразовый 32-byte invite с 7-day expiry, хранимый только как hash.
- Beta принимает только `dating`, DOB 21–35 и Moscow city; preference age range также 21–35. Возраст остаётся declaration с operator review/hide flow при сомнении.
- Waitlist выпускает cohort по reciprocal-eligibility graph, а не отдельным quotas по полу или возрасту; invite нельзя активировать без нужного supply reserve.

### Примечания для агента

- Зависит от: 0.1 (approved Telegram admission policy, budget and legal terms).
- Supersedes beta limitations of completed task 3; source: [authentication design](docs/authentication/design.md), [client brief](docs/client-brief.md).
- Не добавлять второй production login, password fallback или публичную регистрацию.

## [ ] 0.3. Привести onboarding и recommendation policy к beta contract

- Triage: `ready-for-agent`

### Что создаём?

Реализуем approved-photo beta activation, coarse-area/no-distance policy, deferred facts extraction, batch cadence и explicit exploratory fallback.

### Готово, когда

- Local `/profile/publish` и profile directory остаются только developer/demo tools; beta users видят кандидатов исключительно из persisted recommendation batches.
- AI outage допускает manual facts; retained text один раз переобрабатывается после recovery, создаёт pending suggestions и in-app notification без silent ranking change.
- Normal batch содержит ≤5 items, максимум два в день; slot 2 появляется лишь после terminal actions по slot 1. Default exploration отключён.
- `insufficient_supply` даёт честный waitlist state и user-requested, labelled exploratory batch только из fully eligible/no-repeat pool.
- Reasons генерируются только из public allowlist, проходят validator, и отсутствуют при validation/provider failure.

### Как проверить

Покрыть tests для 21–35 policy, directory/publish beta denial, slot-2 gating, exploratory hard filters/no-repeat, deferred extraction review и forbidden reason/location output.

### Примечания для агента

- Supersedes beta decisions of completed tasks 5, 8, 9 and 10.
- Не добавлять infinite feed, candidate recycle, distance approximation или background location.

## [ ] 0.4. Перевести messaging на post-moderation и anti-abuse limits

- Triage: `ready-for-agent`

### Что создаём?

Доставляем сообщения после synchronous policy/rate checks, затем post-moderate их и ограничиваем три сообщения до первого reply.

### Готово, когда

- Только active match members пишут; `unmatch`, `block` и `report` сразу закрывают conversation и скрывают её у обоих.
- До первого reply другой стороны sender может отправить не более трёх messages; existing rate limits остаются server-side.
- High-confidence text violation удаляет message и скрывает account по policy; uncertain content/report попадает в restricted human review.
- Event/log payloads не содержат body; history не возвращает removed/rejected messages получателю.

### Примечания для агента

- Supersedes pre-moderation contract completed task 11.
- Не добавлять realtime sockets, media messages или AI-authored messages.

## [ ] 0.5. Добавить beta operator controls и safe-mode release gates

- Triage: `ready-for-agent`

### Что создаём?

Минимальные MFA staff controls, audit и kill switches для остановки admissions, recommendations, messages, model calls и profile visibility по scope incident.

### Готово, когда

- Separate staff identity/MFA, least-privilege `moderator`/`admin` roles и append-only audit каждого restricted read/write.
- Appeal/report flow позволяет founder restore/hide account, не раскрывая model scores или reporter details; backup owner обязателен только до public launch.
- Safe mode fail-closes new admissions/recommendations/messages as configured; owner и recovery action аудируются.
- Staging drill доказывает provider outage, bad model, safety-disable и restore against RPO/RTO objective.

### Примечания для агента

- Depends on 0.1 for founder coverage/SLA; extends completed task 7 and deployment task 14.
- Не строить case-management platform или отдельный moderation service.

## [ ] 12. Экспортировать и удалять пользовательские данные end to end

- Triage: `needs-info`

### Что создаём?

Реализуем authenticated export и идемпотентные deletion workflows для Postgres, Auth, object storage, derived AI data и ClickHouse identifiers.

### Зачем?

Privacy controls неполны, если withdrawal и deletion фактически не распространяются по системам, а operators не могут доказать завершение.

### Готово, когда

- Export — async job с recent re-auth, короткоживущим protected download и без private data другого пользователя.
- Deletion немедленно скрывает account, поддерживает только утверждённое recovery window, затем стирает/rekeys данные в задокументированном порядке.
- Auth user удаляется последним; неуспешная очистка media/analytics/provider повторяется до успеха или alert до нарушения SLA.
- Recommendation snapshots, embeddings, prompts/sampled payloads и object derivatives следуют своим retention rules.
- Security/legal holds используют утверждённое основание `TBD-SEC01` и не могут повторно опубликовать удалённый profile.
- Каждый staff access, export, deletion, recovery и terminal failure проходит audit без логирования sensitive payload.

### Как проверить

```bash
cd backend && uv run pytest tests/privacy tests/deletion tests/exports -q
cd backend && uv run pytest -m integration tests/deletion -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
```

Прервать deletion после каждого external system, продолжить его и проверить, что удалённый profile не становится видимым, а job приходит к одному terminal result.

### Примечания для агента

- Зависит от: задач 3, 6, 9 и 11.
- Источник: [privacy retention/deletion](docs/architecture/privacy-safety.md#8-retention-export-and-deletion), [privacy API](docs/architecture/api.md#7-consent-and-privacy), [deployment recovery](docs/architecture/deployment.md).
- Реализовать утверждённую policy; не изобретать legal retention или application-level encryption.

### Вне scope

- Cross-region residency platform и generalized data-governance tooling.

## [ ] 13. Доказать корректность funnels, supply и baseline assignments

- Triage: `ready-for-agent`

### Что создаём?

Создаём ClickHouse raw/mart queries и минимальные dashboards для onboarding, eligible supply, recommendation outcomes, replies, safety и retention. Сохраняем baseline assignment metadata, но не включаем ranking exploration/variants в первой beta.

### Зачем?

Решения closed beta и будущая работа над ranking требуют metrics, которые можно пересчитать из canonical events, а не только из likes.

### Готово, когда

- Raw/mart queries дедуплицируют по `event_id` и выдерживают позднюю/неупорядоченную delivery.
- Определения onboarding completion, activation, eligible supply, coverage, impression→open, like/pass, match, first message/reply, retention и safety соответствуют `event-tracking.md`.
- Итоги dashboard сверяются с выборкой domain rows из Postgres и показывают event/outbox lag.
- Baseline assignment (если есть) стабилен по account/version и копируется в batches/events; ranking experiments остаются выключенными до отдельного data/safety decision.
- Ranking evaluation использует reply/conversation/retention с guardrails block/report/unmatch; улучшение только like rate не может продвинуть variant.
- Backfill/replay сохраняет event IDs, имеет dry-run counts, явный range/reason и staff audit.

### Как проверить

```bash
cd backend && uv run pytest tests/events tests/experiments tests/analytics -q
cd backend && uv run pytest -m integration tests/analytics -q
cd backend && uv run ruff check . && uv run ruff format --check .
```

Дважды replay один диапазон событий и проверить неизменность unique funnel counts; сверить один synthetic cohort closed beta с domain rows.

### Примечания для агента

- Зависит от: задачи 2 и задач 10–12.
- Источник: [funnels and metrics](docs/architecture/event-tracking.md#7-funnels-and-metrics), [recommendation feedback](docs/architecture/recommendation-system.md#8-feedback-loop-and-metrics), [client success metrics](docs/client-brief.md#6-success-and-guardrails).
- ClickHouse используется только для analytics. Не добавлять feature store, training platform или authorization на основе аналитики.

### Вне scope

- Learned ranker, realtime ML features и company-wide BI platform.

## [ ] 14. Развернуть восстанавливаемую closed beta

- Triage: `needs-info`

### Прогресс

- [x] Один non-root Docker image с locked backend dependencies запускает API, worker и relay; Docker Compose выбран как VM manifest.
- [x] One-shot Alembic command выполняется из этого image до запуска процессов; application startup не мигрирует схему.
- [x] Frontend production build проверен с явным `VITE_API_BASE_URL`.
- [ ] Provision staging resources, registry image push by commit SHA, frontend upload, migration/restore and incident proofs.

### Что создаём?

Разворачиваем один immutable backend artifact как API, worker и relay processes вместе с frontend, затем доказываем корректность migrations, monitoring, backup/restore и incident controls до приглашения ограниченной beta cohort.

### Зачем?

Feature-complete приложение нельзя запускать, пока operators не умеют обнаруживать failures, восстанавливать данные и останавливать небезопасную recommendation delivery.

### Готово, когда

- Staging и production имеют отдельные Auth, Postgres, storage, ClickHouse и secrets; production PII не копируется в staging.
- Один проверенный migration job выполняется до promotion; startup приложения никогда не запускает auto-migrate.
- Logs/metrics/traces и alerts покрывают API, DB, jobs, model cost/fallback, outbox lag, moderation queue, deletion и backup freshness без sensitive payloads.
- Drills restore, rollback/forward-fix, provider outage, bad model/prompt и safety disable проходят задокументированные gates.
- Acquisition closed beta начинается только после готовности eligible supply, reciprocal-graph cohort admission и назначенного Trust & Safety coverage.
- Kill switches для admissions, recommendations, messages, model calls и scoped profile visibility проверены в staging.
- Launch checklist фиксирует SLO evidence, известные assumptions, owner sign-off и rollback command/runbook.

### Как проверить

```bash
cd backend && uv run pytest -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
```

Выполнить утверждённые staging migration, restore, deletion и incident drills. Сначала проверить internal/demo accounts, затем ограниченную cohort; остановить rollout при любой safety leak.

### Примечания для агента

- Зависит от: всех активных beta tasks, включая 0.1–0.5 и 12–13.
- Источник: [deployment](docs/architecture/deployment.md), [roadmap Phase 0–2](docs/architecture/roadmap.md), [client success and guardrails](docs/client-brief.md#6-success-and-guardrails).
- Использовать утверждённый Yandex Cloud data plane и DS Lab API; не добавлять Kubernetes, multi-region, Supabase, Railway или microservices.

### Вне scope

- Public launch, paid growth, Kafka и learned ranking.

## Отложено до измеримого trigger

Это не активные implementation tasks:

- Kafka после устойчивых `>100 events/s`, появления более трёх независимых consumers или нарушения relay-lag SLO.
- Отдельные services только после измеримой потребности в независимых scale/SLO/release.
- Learned ranking только после накопления стабильных consented events, leakage/bias review, offline gain, shadow test и проверки rollback.
- Feature store/realtime ML только если learned model докажет, что online/offline consistency нельзя обеспечить versioned snapshots.
- Social enrichment, real-profile calibration или agents только после отдельного consent/privacy/safety design.
