# Backend agent instructions

Read [../AGENTS.md](../AGENTS.md) and the relevant file under [../docs/architecture](../docs/architecture) first.

## Current state

Runnable FastAPI app: `uv sync --dev`, `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .`, `uv run ai-matchmaker`. Local auth: `POST /v1/auth/local/register`, `POST /v1/auth/local/sessions`, `DELETE /v1/auth/sessions/current` (loopback + `APP_ENV=local` only). Outbox relay: `uv run ai-matchmaker-relay`. Extraction worker: `uv run ai-matchmaker-worker`. Replay: `uv run ai-matchmaker-replay --event-id <uuid> [--dry-run]`. Config lives in `src/ai_dating/config.py`. Canonical events are JSON Schema under `src/ai_dating/events/schemas/`; `enqueue_event` writes `outbox_events` in the domain transaction. ClickHouse raw table is `clickhouse/raw_events.sql`. Postgres driver is `psycopg`. DS Lab is the only remote AI provider; without credentials local extraction and embeddings use deterministic fakes.

## Target boundaries

- One modular FastAPI codebase. Expected domain modules are `accounts`, `profiles`, `onboarding`, `recommendations`, `matching`, `messaging`, `safety`, `media`, `events`, `jobs`, `database` and `ai`; create only modules required by the current change.
- API, DB-backed worker and outbox relay are separate processes from the same artifact. Do not add Celery/Redis/Kafka or microservices before documented triggers.
- `src/ai_dating/config.py` is the only environment settings module. Never call `os.getenv`/`load_dotenv` in application modules; fail startup on missing required config.
- Request handlers establish actor from an active DB-backed application session. Scope resource queries by actor; never trust client actor/subject, rank, moderation, event or model fields.
- Domain transaction and `outbox_events` insert are atomic. External/model calls run after commit through idempotent jobs.

## Python and dependencies

- Async request/network paths; no blocking network I/O on the event loop.
- Pydantic validates HTTP/external boundaries. Trust typed internal callers; keep functions/modules small.
- Prefer stdlib. Add only declared stack dependencies or a library whose correct replacement is non-trivial; document why a small local function is insufficient.
- No broad `except Exception` just to log/re-raise, silent config/model fallbacks, global mutable service state or custom response envelope.

## Database

- SQLAlchemy models plus Alembic migrations are the schema path once installed. Never mutate production schema from a cloud dashboard.
- Review autogenerate. Extensions, RLS/grants, partial indexes, PostGIS/GiST and pgvector/HNSW require explicit reviewed operations.
- Use direct/session connection for migrations and a runtime pooled connection for the app. Database credentials never replace application authorization.
- Preserve `INV-1`..`INV-9` and the data invariants in [data-model.md](../docs/architecture/data-model.md), especially reciprocal filters, unique exposure, snapshot version guard, canonical match pair, block transaction and idempotent outbox/jobs.

## Verification

When tooling is bootstrapped, keep fast tests network/DB-free and mark credentialed integration tests explicitly. Required proof follows risk: auth/IDOR, reciprocal eligibility, stale delivery, concurrent likes, block/report, message membership, idempotency/outbox duplicate delivery, migration and AI fallback. Document actual commands only after their config exists.
