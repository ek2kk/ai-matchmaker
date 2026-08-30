# Выполненные задачи MVP AI Dating

> **Статус:** архив выполненных задач; не является рабочим backlog.
> **Открытые задачи:** [todos.md](todos.md).
> **Источники:** [client brief](docs/client-brief.md), [обзор архитектуры](docs/architecture/overview.md), [roadmap](docs/architecture/roadmap.md).

## [x] 0. Зафиксировать решения для работающего prototype

### Что создаём?

Фиксируем минимальные решения, достаточные для локального prototype. Production/legal/safety decisions переносятся в отдельный gate перед closed beta.

### Зачем?

Prototype должен проверять продуктовый flow, не выдавая себя за production. Поэтому не вводим юридические, operations и cost обязательства без владельца и измерений.

### Готово, когда

- Зафиксированы решения: Москва, 21–35, отдельные `dating|friendship`, heterosexual `man|woman`, goals `serious_relationship|friends_with_benefits|unsure`.
- Зафиксированы DOB declaration, coarse Moscow location и отсутствие continuous GPS; более сильная age assurance остаётся launch-risk review.
- Founder является владельцем продукта, платформы, CI/CD, Trust & Safety и incident response.
- Зафиксированы Yandex Cloud data plane, Yandex AI Studio для generation и `EmbeddingsGigaR` для retrieval embeddings (`vector(2560)`).
- Зафиксирован prototype auth: local `login + password` с DB-backed sessions; production phone/SMS и Yandex ID реализуются отдельной задачей и не требуются для bootstrap.
- Нерешённые `TBD-SEC01/04`, SLA, RPO/RTO, `TBD-ML01/02`, `TBD-AUTH02` и production SMS provider перенесены в gate перед closed beta.

### Как проверить

```bash
rg -n "blocking|TBD-P01|TBD-P02|TBD-P04|TBD-SEC01|TBD-OPS01" docs AGENTS.md
rg -n "PostGIS|pgvector|ClickHouse|RPO|RTO|cost" docs/architecture
```

Founder утверждает prototype scope. Legal/security и operations gates должны быть закрыты до приглашения реальных пользователей.

### Примечания для агента

- Зависит от: ничего.
- Источник: [решения client brief](docs/client-brief.md#8-decisions-needed-before-implementation), [assumptions overview](docs/architecture/overview.md#11-assumptions-and-open-questions).
- Не включать реальных пользователей, реальные SMS или production PII, пока не закрыт closed-beta gate.

### Вне scope

- Код приложения, provisioning инфраструктуры и миграция между vendors.

## [x] 1. Подготовить запускаемые backend и frontend

### Что создаём?

Создаём минимальные запускаемые FastAPI service и React/Vite SPA с валидируемой конфигурацией, lockfiles зависимостей и повторяемыми проверками. Разработчик сможет локально запустить обе части и увидеть, как SPA вызывает backend health/readiness endpoints.

### Зачем?

Сейчас в репозитории есть только Python stub и нет frontend. Всем следующим задачам нужен единый command и configuration baseline.

### Готово, когда

- Backend использует заявленный Python stack, `src/ai_dating/config.py`, FastAPI app lifecycle, `/healthz` и учитывающий dependencies `/readyz`.
- Alembic и SQLAlchemy инициализированы без продуктовых таблиц, кроме migration bookkeeping.
- Frontend использует Vite, strict TypeScript, React Router и соглашения Tailwind/shadcn, а также `src/lib/env.ts` и API client на native `fetch`.
- Закоммичены и задокументированы `uv.lock`, `pnpm-lock.yaml`, `.env.example` и реальные команды dev/test/lint/type/build.
- Unit checks не требуют сети или credentials; отсутствие обязательной production-конфигурации останавливает запуск.
- Локальные команды являются единственным source of truth; CI подключается отдельной задачей после выбора provider (`TBD-INF03`).

### Как проверить

```bash
cd backend && uv sync --dev
cd backend && uv run pytest -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm install --frozen-lockfile
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
curl -fsS http://localhost:8000/healthz
```

Локально запустить SPA и проверить, что один typed API call отображает состояние backend без раскрытия secrets.

### Примечания для агента

- Зависит от: задачи 0.
- Источник: [deployment](docs/architecture/deployment.md), корневой и вложенные `AGENTS.md`.
- Использовать только зависимости утверждённого stack. Не добавлять Docker, monorepo tooling, state libraries или test frameworks сверх соглашений репозитория.

### Вне scope

- Authentication, domain tables, cloud deployment и business UI.

### Детальные итерации задачи 1

> **Результат задачи:** один локально запускаемый контур `React SPA → FastAPI`. Он не требует реальной БД, SMS, cloud credentials или Docker. Каждый подпункт — отдельный маленький PR; после 1.5 можно начинать task 2 или task 3.

#### 1.1. Превратить Python stub в минимальный FastAPI application

##### Что создаём?

Добавляем запускаемое FastAPI application с `GET /healthz`. Endpoint показывает только версию приложения и состояние процесса, без credentials или внутренней конфигурации.

##### Готово, когда

- `ai_dating:main` запускает ASGI server через один документированный command.
- `GET /healthz` всегда возвращает `200` и минимальный JSON status.
- Есть application factory и test для success response; импорт модуля не делает network/DB calls.
- Runtime/dev зависимости, `uv.lock`, Ruff и pytest зафиксированы в `pyproject.toml`.

##### Как проверить

```bash
cd backend && uv sync --dev
cd backend && uv run pytest tests/test_health.py -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd backend && uv run ai-dating
curl -fsS http://localhost:8000/healthz
```

##### Примечания для агента

- Зависит от: задачи 0.
- Использовать FastAPI, Uvicorn, pytest и Ruff; не добавлять ORM, migration или HTTP client в этом PR.
- `healthz` — liveness, а не permission или readiness check.

##### Вне scope

- Database, auth, CORS, domain routes и worker process.

#### 1.2. Добавить единый config, readiness и безопасное логирование

##### Что создаём?

Добавляем `backend/src/ai_dating/config.py`, environment profiles и request correlation. Local development запускается без secrets; production profile отказывается стартовать при отсутствии обязательных settings.

##### Готово, когда

- Только `config.py` читает environment; остальные modules получают typed settings через application lifecycle.
- `GET /readyz` возвращает `503`, если обязательная для выбранного environment dependency не настроена; local без БД остаётся пригодным для `/healthz`.
- CORS allowlist конфигурируется, а не задаётся `*`; development origin documented.
- Structured logs содержат `request_id`, route, status, duration и не содержат headers, env values или request bodies.

##### Как проверить

```bash
cd backend && uv run pytest tests/test_config.py tests/test_readiness.py -q
cd backend && uv run ruff check . && uv run ruff format --check .
```

В local profile проверить `healthz`; в production-like environment без обязательного URL/secret проверить fail-fast startup или `503 readyz` согласно выбранному lifecycle contract.

##### Примечания для агента

- Зависит от: 1.1.
- Source of truth: корневой `AGENTS.md` и [deployment](docs/architecture/deployment.md#3-configuration-and-secrets).
- Не добавлять `.env` с секретами; только `.env.example` с placeholders.

##### Вне scope

- Реальная интеграция Postgres, ClickHouse или secret store.

#### 1.3. Подготовить SQLAlchemy и Alembic без product schema

##### Что создаём?

Добавляем database package и Alembic wiring, чтобы следующие задачи создавали схему только через reviewed migrations. Продуктовых таблиц, подключения при import и auto-migrate при startup ещё нет.

##### Готово, когда

- Runtime использует отдельный pooled database URL, а Alembic — direct URL из typed config.
- Alembic environment загружает config без `os.getenv` в migration files.
- `alembic upgrade head` создаёт только migration bookkeeping; API startup не запускает migrations.
- Отсутствующий/некорректный database URL даёт понятную config error, а не fallback на SQLite.

##### Как проверить

```bash
cd backend && uv run pytest tests/database -q
cd backend && uv run alembic upgrade head
cd backend && uv run alembic current
cd backend && uv run ruff check . && uv run ruff format --check .
```

##### Примечания для агента

- Зависит от: 1.2.
- Использовать SQLAlchemy, Alembic и один поддерживаемый PostgreSQL driver; точный driver фиксируется в lockfile и README.
- `pgvector`, PostGIS, RLS, grants и domain migrations начинаются в соответствующих задачах, не здесь.

##### Вне scope

- Таблицы accounts/outbox, cloud database provisioning и repository pattern.

#### 1.4. Bootstrap React/Vite SPA и минимальный app shell

##### Что создаём?

Инициализируем строго типизированный React/Vite application с React Router, Tailwind и одним экраном статуса. Это настоящий frontend baseline, а не дизайн будущего dating UI.

##### Готово, когда

- В `frontend/` есть `package.json`, `pnpm-lock.yaml`, Vite/React/TypeScript config и `.npmrc` с `minimum-release-age=10080`.
- `src/lib/env.ts` — единственное место чтения `VITE_*`; components не читают `import.meta.env` напрямую.
- `src/App.tsx` содержит router и страницу `/`; styling использует Tailwind, без CSS modules и state library.
- `pnpm lint`, `pnpm tsc --noEmit` и `pnpm build` проходят без сети после install.

##### Как проверить

```bash
cd frontend && pnpm install --frozen-lockfile
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
cd frontend && pnpm dev
```

Открыть local SPA и убедиться, что `/` рендерится при прямом refresh.

##### Примечания для агента

- Зависит от: задачи 0; можно делать параллельно с 1.1–1.3.
- Использовать `pnpm` и native browser APIs. shadcn/ui не инициализировать, пока не появился первый нужный primitive.
- Frontend tests не добавлять: правило [frontend/AGENTS.md](frontend/AGENTS.md#testing).

##### Вне scope

- Auth UI, API calls, backend proxy, state/query library и production deployment.

#### 1.5. Соединить SPA с health API

##### Что создаём?

Добавляем thin native-`fetch` client и страницу статуса, которая запрашивает `GET /healthz`, показывает loading/success/network/HTTP error и позволяет повторить запрос. Это первый проверяемый browser-to-backend путь.

##### Готово, когда

- `VITE_API_BASE_URL` валидируется в `src/lib/env.ts`; production build отказывается от отсутствующего/некорректного URL.
- `src/lib/http.ts` централизует base URL, timeout, JSON parsing и typed `ApiError`; components не вызывают `fetch` напрямую.
- Страница не показывает stack trace, response body или configuration details при failure.
- Backend CORS разрешает только local development origin, заданный в config; request получает `request_id`.

##### Как проверить

```bash
cd backend && uv run pytest tests/test_health.py tests/test_cors.py -q
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
```

Запустить оба process, открыть SPA в browser и проверить success, выключенный backend и неверный API URL. Во всех error cases secrets и raw error body не отображаются.

##### Примечания для агента

- Зависит от: 1.2 и 1.4.
- Не добавлять proxy в Vite: SPA должна проверять реальный CORS/API boundary.
- `Idempotency-Key`, session credentials и domain methods появляются с task 3, не в health client.

##### Вне scope

- Login, persistence, retries beyond user-triggered retry и telemetry SDK.

#### 1.6. Зафиксировать developer workflow и завершить bootstrap

##### Что создаём?

Дополняем README и `AGENTS.md` только фактически существующими commands, layout и local run sequence. Результат должен позволить начать task 2 или task 3 без повторного bootstrap.

##### Готово, когда

- README описывает prerequisites, `.env.example`, install, two-process local run и все реально созданные check commands.
- Root и nested `AGENTS.md` не содержат ложных commands или зависимостей; generated files/lockfiles перечислены корректно.
- Один чистый clone проходит install, backend checks, frontend checks и browser health path по README.
- `TBD-INF03` явно остаётся отдельным выбором CI provider; CI config не создаётся в этом PR.

##### Как проверить

```bash
cd backend && uv sync --dev && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm install --frozen-lockfile && pnpm lint && pnpm tsc --noEmit && pnpm build
```

Повторить local startup, пользуясь только README, в чистом working directory.

##### Примечания для агента

- Зависит от: 1.1–1.5.
- Не выбирать GitHub Actions, GitLab CI или другую CI system без решения по `TBD-INF03`.

##### Вне scope

- Remote deployment, preview environments и production secrets.

## [x] 2. Доставлять canonical events через transactional outbox

### Что создаём?

Добавляем общий event contract, миграцию `outbox_events` и relay process, который доставляет валидные события в ClickHouse с семантикой at-least-once. Повторная доставка должна давать одно аналитическое событие по `event_id`.

### Зачем?

Каждой следующей domain write нужен один безопасный event path. Единая реализация предотвращает dual-write и несовместимые event payloads между функциями.

### Готово, когда

- Versioned schemas валидируют canonical envelope и все события из `event-tracking.md`.
- Короткая DB transaction захватывает lease; HTTP-вызовы ClickHouse никогда не выполняются внутри DB transaction.
- Падение после записи в sink, но до подтверждения в DB повторно доставляет тот же `event_id`; аналитика дедуплицирует его.
- Poison rows изолируются, не блокируют корректные строки и не теряются молча.
- Relay публикует metrics глубины, lease expiry, retry, delivery latency и outbox lag без логирования payload.
- Direct outbox-to-ClickHouse — единственный event path; Kafka отсутствует.

### Как проверить

```bash
cd backend && uv run pytest tests/events -q
cd backend && uv run pytest -m integration tests/events -q
cd backend && uv run ruff check . && uv run ruff format --check .
```

Остановить relay после успешной записи в sink, но до подтверждения в DB; перезапустить и проверить одно логическое событие ClickHouse для исходного `event_id`.

### Примечания для агента

- Зависит от: задачи 1.
- Источник: [event tracking](docs/architecture/event-tracking.md), [outbox в data model](docs/architecture/data-model.md#7-reliability-support-tables), ADR-02 в [overview](docs/architecture/overview.md#adr-02-postgres-outbox-direct-clickhouse-no-kafka-in-early-mvp).
- Использовать существующую async HTTP dependency утверждённого backend stack; не добавлять queue framework.

### Вне scope

- Product dashboards, Kafka, CDC и внешний schema registry.

### Детальные итерации задачи 2

> **Граница:** это backend-first задача. SPA не создаёт canonical event, не получает `event_id` и не пишет в ClickHouse. До задач 3–4 frontend меняется только при необходимости поддержать безопасный `Idempotency-Key` в общем API client; отдельный analytics SDK и debug UI не нужны.

#### 2.1. Зафиксировать event contract и fixtures

### Что создаём?

Добавляем versioned JSON Schema и валидные/невалидные fixtures для canonical envelope и каждого события, уже описанного в архитектуре. Будущие domain-модули смогут импортировать один contract, а не собирать payload вручную.

### Готово, когда

- В backend source control есть по одной JSON Schema на `event_name`/`schema_version=1`, включая lifecycle events onboarding.
- Общий envelope требует server-generated `event_id`, `occurred_at`, actor/subject и запрещает неизвестные поля.
- Fixtures доказывают запрет raw PII: DOB, coordinates, free text, message body, photo URL, report detail и prompt не проходят validation.
- Контракт `report`/`block` допускает только allowlisted reason categories и отделён от restricted audit payload.

### Как проверить

```bash
cd backend && uv run pytest tests/events/contracts -q
cd backend && uv run ruff check . && uv run ruff format --check .
```

### Примечания для агента

- Зависит от: задачи 1.
- Источник: [event envelope](docs/architecture/event-tracking.md#1-canonical-envelope), [events](docs/architecture/event-tracking.md#2-required-events).
- Новый обязательный field или смена semantics создаёт новую `schema_version`; не менять старый fixture задним числом.

### Вне scope

- Внешний schema registry, frontend analytics SDK и отправка реальных domain events.

#### 2.2. Сохранить event вместе с domain transaction

### Что создаём?

Добавляем Alembic migration для `outbox_events` и маленький backend helper, который валидирует event и вставляет его в ту же transaction, что и domain change. На этом шаге helper тестируется на минимальной transaction, без новых пользовательских endpoint.

### Готово, когда

- Миграция создаёт поля, partial claim index и constraints из [data model](docs/architecture/data-model.md#outbox_events).
- При commit transaction domain row и outbox row появляются вместе; при rollback не появляется ни один из них.
- `event_id` создаёт server, а `occurred_at` берётся из момента domain transition, а не из запроса клиента.
- Повторный вызов с тем же logical event не создаёт второй event; API-level idempotency остаётся обязанностью будущего endpoint.

### Как проверить

```bash
cd backend && uv run alembic upgrade head
cd backend && uv run pytest tests/events/test_outbox_write.py -q
cd backend && uv run ruff check . && uv run ruff format --check .
```

### Примечания для агента

- Зависит от: 2.1.
- Payload хранится как validated JSON, но logs содержат только `event_id`, name, version и error code.
- Не добавлять repository/factory hierarchy: достаточно одной transaction-aware функции/сервиса.

### Вне scope

- Auth, account bootstrap и ручной endpoint для генерации тестовых событий.

#### 2.3. Поднять raw-table contract ClickHouse и sink adapter

### Что создаём?

Описываем и создаём минимальную raw events table в ClickHouse, а также adapter, который вставляет ограниченный batch уже валидных payloads. Adapter ничего не знает о Postgres lease и не подтверждает delivery сам.

### Готово, когда

- Таблица использует `ReplacingMergeTree(ingested_at)` и порядок `(event_name, occurred_date, event_id)`.
- Вставка одного `event_id` повторно сохраняет возможность аналитической дедупликации независимо от фонового merge.
- Adapter ограничивает batch size/timeout и возвращает typed success, retryable или deterministic rejection без raw response logging.
- Unit tests используют fake sink; credentialed ClickHouse test запускается только при явной integration-конфигурации.

### Как проверить

```bash
cd backend && uv run pytest tests/events/test_clickhouse_sink.py -q
cd backend && uv run pytest -m integration tests/events/test_clickhouse_sink.py -q
```

### Примечания для агента

- Зависит от: 2.1; реальная ClickHouse config из задачи 1.
- Клиентская дедупликация не считается корректностью: будущие queries/marts используют `event_id`.

### Вне scope

- Marts, dashboards, Kafka и подключение production ClickHouse.

#### 2.4. Реализовать lease-based outbox relay

### Что создаём?

Реализуем отдельный process command, который кратко арендует готовые outbox rows, отправляет их в sink без открытой DB transaction и подтверждает delivery после успешного ответа sink.

### Готово, когда

- Конкурентные relay processes не отправляют одну активную lease одновременно; expired lease безопасно подхватывается другим process.
- Crash после sink insert и до `delivered_at` повторяет тот же `event_id`, а не создаёт новый.
- `delivered_at` ставится только после sink acknowledgement; порядок delivery между событиями не обещается.
- Graceful shutdown прекращает новые claims и отпускает/завершает текущую bounded работу.

### Как проверить

```bash
cd backend && uv run pytest tests/events/test_relay_claim.py tests/events/test_relay_delivery.py -q
cd backend && uv run pytest -m integration tests/events/test_relay_delivery.py -q
```

Вручную остановить relay между insert в test sink и ACK в Postgres, затем перезапустить: sink видит повтор того же `event_id`, а query после дедупликации — одно событие.

### Примечания для агента

- Зависит от: 2.2, 2.3.
- Использовать `FOR UPDATE SKIP LOCKED`, `lease_owner`, `lease_until`, `available_at`; не добавлять Redis, Celery или Kafka.

### Вне scope

- Background jobs для AI/media и scheduler как отдельная платформа.

#### 2.5. Добавить retry, isolation и controlled replay

### Что создаём?

Добавляем bounded retry с jitter, изоляцию плохой строки и owner-only replay command для явного диапазона/списка `event_id`. Ошибка одной schema или sink row не должна останавливать корректные events.

### Готово, когда

- Retry backoff растёт от 10 seconds до 15 minutes; после 24 hours row остаётся retryable и создаёт alert condition.
- Relay делит упавший batch, доставляет валидные rows и сохраняет для плохой строки только allowlisted `last_error_code`.
- Replay поддерживает dry-run и не меняет `event_id`; запуск записывает owner/reason в restricted audit.
- Delivered rows не удаляются раньше семидневного verified-delivery window.

### Как проверить

```bash
cd backend && uv run pytest tests/events/test_retries.py tests/events/test_replay.py -q
cd backend && uv run ruff check . && uv run ruff format --check .
```

В fake sink сделать один event deterministic-invalid: соседние events доставляются, invalid row остаётся видимым для диагностики и не исчезает.

### Примечания для агента

- Зависит от: 2.4.
- `replay` не является публичным API и не должен быть реализован через прямую правку DB.

### Вне scope

- Автоматический backfill domain history, удаление данных или staff UI.

#### 2.6. Наблюдать outbox и сохранить frontend boundary

### Что создаём?

Добавляем безопасные metrics/logs для relay и фиксируем правило для будущего frontend API client: browser code не формирует canonical analytics payload и не получает служебные event fields.

### Готово, когда

- Metrics покрывают pending depth, oldest age, lease expiry, attempts, delivery latency, delivered/failed count и lag.
- Logs/traces коррелируют `event_id` и `request_id`, не содержат event payload или PII.
- Backend readiness показывает критическую недоступность обязательного sink только в environment, где ClickHouse включён; local fake sink не требует credentials.
- Документированная boundary для задач 3+ запрещает SPA передавать actor, `event_id`, `occurred_at` и event properties; `Idempotency-Key` добавится вместе с первым state-changing endpoint.

### Как проверить

```bash
cd backend && uv run pytest tests/events/test_observability.py -q
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
```

### Примечания для агента

- Зависит от: 2.4, 2.5 и task 1 frontend bootstrap.
- Не создавать dashboard или internal event inspector: metrics достаточно до появления реальных domain actions.

### Вне scope

- Пользовательские экраны analytics, product funnels и server-to-client event stream.

## [x] 3. Реализовать local login/password auth и сохранять consented account state

### Что создаём?

Реализуем local `login + password`, revocable DB-backed sessions, идемпотентный account bootstrap, consent receipts и privacy controls. Этот flow создаёт несколько test accounts для prototype и намеренно отказывается запускаться вне local loopback.

### Зачем?

Identity и consent — trust boundary для каждого профиля, model call и safety action.

### Готово, когда

- `POST /v1/auth/local/register` и `POST /v1/auth/local/sessions` принимают только normalised `login + password`; unknown и invalid login возвращают одинаковый `401 invalid_credentials` при sign-in.
- Password хранится только как Argon2id hash; plaintext не попадает в DB, logs, events, responses или model calls.
- Session token хранится только как hash; logout/block/deletion и expiry немедленно запрещают дальнейшие authenticated calls.
- `local_password` configuration отказывается запускаться вне `APP_ENV=local` или при non-loopback binding; production phone/SMS/Yandex endpoints отсутствуют.
- Registration bootstrap идемпотентен, создаёт `status=onboarding` и не принимает account ID от клиента.
- История consent append-only, а текущие решения по purpose вычисляются однозначно.
- Отзыв согласия на AI matching скрывает профиль из discovery и ставит в очередь удаление/инвалидацию derived data.
- Cross-account resource IDs возвращают не раскрывающие наличие ресурса `404/403` согласно API contract.
- Изменения account/consent записывают canonical outbox и restricted audit records в той же transaction.

### Как проверить

```bash
cd backend && uv run pytest tests/accounts tests/auth tests/privacy -q
cd backend && uv run pytest -m integration tests/accounts -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
```

Вручную создать два local accounts, войти каждым, проверить invalid/unknown login, logout/expiry и то, что session второго пользователя не может читать или менять состояние первого.

### Примечания для агента

- Зависит от: задач 1–2.
- Источник: [authentication design](docs/authentication/design.md), [общие правила API и account endpoints](docs/architecture/api.md#1-common-rules), [privacy](docs/architecture/privacy-safety.md), [identity model](docs/architecture/data-model.md#3-core-identity-and-profile-tables).
- Password, session token и future provider credentials никогда не попадают в logs, events или model calls. Database role не заменяет actor-scoped authorization.

### Вне scope

- Phone/SMS, Yandex ID, invitations, password reset/change, MFA, публичные профили и staff admin UI.

## [x] 4. Реализовать structured onboarding и desired-partner preferences

### Что создаём?

Добавляем 3–5-минутный structured onboarding с раздельными self profile и desired partner preferences. Пользователь сможет сохранять и продолжать drafts, разрешать version conflicts и завершать все user-controlled gates.

### Зачем?

Это создаёт минимальные достоверные inputs для reciprocal matching без ожидания optional AI enrichment.

### Готово, когда

- Миграции profile и preferences реализуют ranges, controlled codes, visibility и version constraints из data model.
- Owner-only API и SPA собирают DOB gate, self fields, желаемые gender/age/distance/goals, prompt answer и выбор discoverability.
- Drafts остаются скрытыми; `expected_version` предотвращает потерю concurrent edits.
- Строки и события завершения шагов создаются один раз на flow/step и не содержат raw profile text.
- `onboarding_completed` отделён от async `profile_activated`; pending moderation возвращает `202 profile_activation_pending`, а не `422`.
- Form controls доступны с клавиатуры, имеют labels и показывают server validation не только цветом.

### Как проверить

```bash
cd backend && uv run pytest tests/onboarding tests/profiles -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
```

В двух browser sessions отредактировать один draft и проверить, что stale save получает `409`; затем завершить onboarding при pending moderation.

### Примечания для агента

- Зависит от: задачи 3.
- Источник: [onboarding](docs/architecture/onboarding.md), [profile API](docs/architecture/api.md#2-onboarding-profile-and-preferences), [data model](docs/architecture/data-model.md).
- Compatibility использует explicit accepted-gender intent в обе стороны; orientation labels не преобразуются в preferences через inference.

### Вне scope

- Photos, AI extraction, calibration, candidate retrieval и recommendations.

## [x] 5. Добавить review AI-extracted facts и synthetic calibration

### Что создаём?

Преобразуем free text пользователя в pending normalized facts, которые он должен принять, исправить или отклонить. Добавляем calibration предпочтений только на явно обозначенных synthetic profiles.

### Зачем?

Приложение получит полезные soft signals, не считая model output истиной и не выдавая demo profiles за реальных людей.

### Готово, когда

- DB-backed extraction jobs используют minimized input, schema-constrained output, точные версии prompt/model/source и bounded retries.
- Pending/rejected facts не влияют на matching; правки пользователя supersede extracted facts с сохранением provenance.
- Тесты запрещённого sensitive inference закрываются fail-closed, а raw prompts/responses не попадают в logs.
- Calibration sessions/choices ссылаются на demo IDs, а не на реальные account/profile IDs, и не создают реальные impression/like/pass events.
- Пользователь может пропустить и очистить calibration; canonical lifecycle events остаются идемпотентными.
- При сбое provider доступен manual structured onboarding.

### Как проверить

```bash
cd backend && uv run pytest tests/ai tests/profile_facts tests/calibration -q
cd backend && uv run pytest -m integration tests/ai -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
```

Вставить инструкции в profile text и проверить, что extractor возвращает только разрешённые typed facts; убедиться, что synthetic calibration choice не может создать реальное взаимодействие.

### Примечания для агента

- Зависит от: задачи 4.
- Источник: [AI/ML](docs/architecture/ai-ml.md), [onboarding facts и calibration](docs/architecture/onboarding.md#4-free-text-to-reviewed-facts), [calibration API](docs/architecture/api.md#2-onboarding-profile-and-preferences).
- Не добавлять agent framework, prompt-management service или real-profile calibration.

### Вне scope

- Embeddings, recommendation ranking и model training.

## [x] 6. Загружать, модерировать и активировать media профиля

### Что создаём?

Реализуем private photo upload intents, безопасные derivatives, moderation states и profile activation. Пользователь становится discoverable только после завершения onboarding и прохождения всех server-controlled gates.

### Зачем?

Ни один непроверенный object или pending/rejected image не должен стать видимым другому пользователю.

### Готово, когда

- Signed upload intents связывают owner, MIME, size и hash; completion проверяет сохранённый object до создания metadata.
- Image decode/re-encode удаляет metadata, создаёт bounded derivatives и следует решению по malware/moderation из задачи 0.
- Original keys остаются private; candidate payloads используют только свежие signed URLs для approved derivative IDs.
- Операции reorder/delete сохраняют constraints активных positions и скрывают профили, опустившиеся ниже photo gate.
- Сбой moderation оставляет новые media в pending; approval атомарно обновляет profile version/activation и один раз ставит generation в очередь.
- Object cleanup идемпотентен и наблюдаем.

### Как проверить

```bash
cd backend && uv run pytest tests/media tests/moderation tests/profile_activation -q
cd backend && uv run pytest -m integration tests/media -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
```

Попробовать uploads с неверным owner, hash, превышенным size и metadata; ни один из них не должен создать eligible photo.

### Примечания для агента

- Зависит от: задач 4–5.
- Источник: [photo API](docs/architecture/api.md#3-photo-lifecycle), [privacy and safety](docs/architecture/privacy-safety.md), [photo model](docs/architecture/data-model.md#profile_photos).
- Не хранить media bytes в Postgres. Не добавлять public bucket или CDN-specific abstraction.

### Вне scope

- Video, identity verification и imports из social media.

## [x] 7. Обеспечить block, report и moderation actions

### Что создаём?

Добавляем немедленный symmetric block, приём reports и минимальную restricted moderation queue. Block должен скрывать пользователей друг от друга в discovery и существующих relationships даже при недоступности analytics или model providers.

### Зачем?

Safety actions обязательны до запуска recommendations или messaging.

### Готово, когда

- Таблицы и API block/report обеспечивают actor-scoped ссылки на profile или relationship и idempotency.
- Одна transaction захватывает canonical pair lock, создаёт block, завершает match/conversation, инвалидирует ready items и записывает audit/outbox records.
- Report автоматически обеспечивает block behavior и не раскрывает субъекту identity/details автора жалобы.
- Restricted staff access требует утверждённую identity/MFA model, причину доступа к case и append-only audit доступа/решений.
- Rate limits не могут помешать пользователю заблокировать другого; сбой provider/analytics не ослабляет enforcement.
- Cross-account, reverse-direction и race tests доказывают `INV-1`, `INV-6` и не раскрывающие наличие ресурса responses.

### Как проверить

```bash
cd backend && uv run pytest tests/safety tests/moderation -q
cd backend && uv run pytest -m integration tests/safety -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
```

Запустить block одновременно с reciprocal like и проверить, что не осталось active match или видимого profile.

### Примечания для агента

- Зависит от: задач 3 и 6.
- Источник: [privacy and safety](docs/architecture/privacy-safety.md#5-block-report-and-moderation), [block/report API](docs/architecture/api.md#6-block-and-report), [data invariants](docs/architecture/data-model.md#9-transactional-invariants-and-query-patterns).
- Safety queue — restricted product module, а не новый microservice.
- Staff case-view/resolve HTTP не поставляется, пока отдельно не утверждена staff identity/MFA. Reports создают restricted pending cases и symmetric block.

### Вне scope

- Платформа automated enforcement appeals, интеграция с внешней case-management system и social enrichment.

## [x] 8. Генерировать reciprocal heuristic recommendation batches

### Что создаём?

Создаём первый полезный recommendation worker: reciprocal eligibility, exact/pgvector retrieval, прозрачный heuristic scoring, diversity, один exploration slot и сохранённые batches максимум из пяти кандидатов.

### Зачем?

Это даёт продуктовую ценность без learned ranker и без зависимости от доступности LLM.

### Готово, когда

- Gender intent, age, distance, goals, activity, visibility, moderation, blocks и prior exposure обоих пользователей применяются как hard filters до scoring.
- Индексы PostGIS и pgvector соответствуют утверждённым возможностям платформы; exact-search samples измеряют eligible recall.
- При отсутствии embeddings score renormalizes по доступным non-semantic features, а hard filters по-прежнему fail closed.
- DB-backed jobs используют leases, versioned dedup keys и отбрасывают результат при source-version drift.
- Diversity/exploration детерминирован по batch ID и никогда не ослабляет safety или no-repeat.
- Generation укладывается в latency budget на staging-scale данных либо фиксируется блокирующее измерение.

### Как проверить

```bash
cd backend && uv run pytest tests/recommendations/eligibility tests/recommendations/ranking -q
cd backend && uv run pytest -m integration tests/recommendations -q
cd backend && uv run ruff check . && uv run ruff format --check .
```

Запустить reciprocal filter matrix и сравнить sampled HNSW results с exact cosine search, приложив результаты `EXPLAIN (ANALYZE, BUFFERS)`.

### Примечания для агента

- Зависит от: задач 5–7.
- Источник: [recommendation flow](docs/architecture/recommendation-system.md), ADR-03/04 в [overview](docs/architecture/overview.md), [data model](docs/architecture/data-model.md#6-recommendation-and-interaction-tables).
- Строки batch в Postgres служат cache. Не добавлять Redis, Celery, Kafka, vector database или learned ranking.

### Вне scope

- LLM reranking, user feedback и messaging.

## [x] 9. Добавить bounded LLM reranking и воспроизводимые item snapshots

### Что создаём?

Rerank только верхних eligible candidates из heuristic pool через bounded-вызов Yandex AI Studio, валидируем результат и сохраняем точный snapshot public profile/reason, использованный при delivery.

### Зачем?

Модель может улучшить порядок и explanations, но сбой provider или небезопасный output не должны блокировать безопасный heuristic batch.

### Готово, когда

- В versioned schema-constrained request попадает не более 20 minimized eligible candidates в пределах token/time/cost caps.
- Unknown/duplicate IDs, запрещённые reasons, invalid JSON, timeout или rate limit отбрасывают весь model result и устанавливают `fallback_mode=no_llm`.
- Items сохраняют component scores, версии model/prompt/feature, `public_profile_snapshot`, photo IDs/versions и прошедший policy check reason snapshot.
- Delivery требует точного совпадения текущей версии profile; deletion удаляет snapshot content, сохраняя разрешённый audit actions/versions.
- Offline human evaluation проходит `TBD-ML01/02`; иначе результат документируется и сохраняется heuristic-only behavior без мёртвого кода.
- Model latency, tokens, cost, validation rejection и fallback rate наблюдаемы без raw payload logs.

### Как проверить

```bash
cd backend && uv run pytest tests/recommendations/reranking tests/ai -q
cd backend && uv run pytest -m integration tests/recommendations/reranking -q
cd backend && uv run ruff check . && uv run ruff format --check .
```

Принудительно вызвать каждый задокументированный provider failure и проверить, что те же eligible heuristic candidates остаются доступными для delivery без утечки private fields.

### Примечания для агента

- Зависит от: задачи 8.
- Источник: [bounded reranker](docs/architecture/recommendation-system.md#25-bounded-llm-reranker), [AI boundary](docs/architecture/ai-ml.md), `INV-2/3/7/9` в [overview](docs/architecture/overview.md#8-invariants).
- LLM только переупорядочивает переданные IDs. Не добавлять tools, autonomous loops или model-driven eligibility.
- Human pairwise gate `rerank-human-pairwise-v1` записан в `docs/ml/rerank-eval-manifest.json` как `decision: fail` (synthetic dry-run). Runtime rerank остаётся выключенным. `TBD-ML01` остаётся extraction gate. Full account deletion остаётся задачей 12; `erase_candidate_snapshots` — primitive для неё.

### Вне scope

- Learned ranking, feature store и generated user messages.

## [x] 10. Доставлять batches, записывать feedback и создавать один match

### Что создаём?

Показываем текущий небольшой batch, записываем идемпотентные actions impression/open/like/pass и создаём ровно один match/conversation из reciprocal likes.

### Зачем?

Это превращает сгенерированных кандидатов в воспроизводимое пользовательское взаимодействие и первый реальный outcome signal.

### Готово, когда

- Перед сериализацией сохранённого snapshot delivery повторно проверяет текущие consent, eligibility, block, moderation и точную версию candidate profile.
- Impression создаёт одну постоянную exposure-пару owner/candidate; повторные requests не создают второе событие.
- Один item принимает только одно terminal decision like/pass; optional pass reason входит в allowlist.
- Like и block используют один canonical pair lock; concurrent reciprocal likes создают ровно один match и conversation.
- Client не может передать actor/subject, candidate ID, scores, timestamps, model versions или event payloads.
- SPA содержит bounded batch UI без infinite pagination и доступные actions open/like/pass/block/report.

### Как проверить

```bash
cd backend && uv run pytest tests/recommendations/delivery tests/matching -q
cd backend && uv run pytest -m integration tests/matching -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
```

Запустить два reciprocal likes одновременно, продублировать каждое action, изменить/заблокировать кандидата до delivery и проверить сохранение `INV-1`–`INV-9`.

### Примечания для агента

- Зависит от: задач 7–9.
- Источник: [recommendation API](docs/architecture/api.md#4-recommendation-batches-and-feedback), [matching model](docs/architecture/data-model.md#6-recommendation-and-interaction-tables), [event contracts](docs/architecture/event-tracking.md#2-required-events).
- В MVP нет swipe feed, popularity cache или rematch/recycle policy.

### Вне scope

- Messages, boosts, payments и candidate recycling.

## [x] 11. Обмениваться moderated messages внутри active matches

### Что создаём?

Позволяем двум участникам active match отправлять, читать и постранично получать moderated messages. Текст в состоянии held или rejected остаётся невидимым получателю.

### Зачем?

Reply и sustained conversation — более сильные signals качества продукта, чем likes сами по себе.

### Готово, когда

- Только участники active conversation могут отправлять/читать сообщения; block/unmatch немедленно закрывает доступ.
- Новые messages по умолчанию имеют `held`; moderation безопасно переводит их в `allowed` или `rejected`.
- Allowed history использует cursor `(allowed_at,message_id)`, поэтому async moderation не может вставить сообщение позади client cursor.
- `(sender_account_id,client_message_id)` заставляет retries возвращать одно сообщение.
- Events `message` и `reply` содержат IDs/latency, но не body text; reply использует предыдущее allowed message другого участника.
- Rate limits, UX состояния held и generic unavailable states соответствуют privacy/safety contracts.

### Как проверить

```bash
cd backend && uv run pytest tests/messaging tests/moderation -q
cd backend && uv run pytest -m integration tests/messaging -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
```

Удержать старое сообщение, разрешить более новое, затем разрешить старое и проверить, что cursor pagination возвращает каждое ровно один раз в порядке `allowed_at`.

### Примечания для агента

- Зависит от: задач 7 и 10.
- Источник: [messaging API](docs/architecture/api.md#5-matches-conversations-and-messages), [message model](docs/architecture/data-model.md#conversations-conversation_members-messages), [message events](docs/architecture/event-tracking.md#2-required-events).
- Не заявлять end-to-end encryption; не добавлять realtime sockets, voice/video или AI-authored messages.

### Вне scope

- Read receipts сверх задокументированного pointer, push notifications и media messages.
