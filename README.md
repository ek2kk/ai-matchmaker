# AI Matchmaker

Local prototype for a FastAPI API and a React SPA. Production cloud, auth, and domain features are not in this bootstrap.

## Prerequisites

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Node.js 22+ and [pnpm](https://pnpm.io/) 11

## Configuration

Copy the examples. Do not commit `.env` files that contain secrets.

```bash
cp backend/.env.example backend/.env
# frontend already has .env.development / .env.production with the public API URL
```

`backend/.env.example` uses placeholders only. Local API starts without a database. `staging` and `production` fail to start if required settings are missing. Database URLs must be PostgreSQL (`psycopg`); SQLite is rejected.

Frontend public URL: `VITE_API_BASE_URL` (default `http://localhost:8000`). It is validated in `frontend/src/lib/env.ts`; a production build refuses a missing or non-http(s) URL.

## Install

```bash
cd backend && uv sync --dev
cd frontend && pnpm install --frozen-lockfile
```

## Local run

Postgres can stay up between sessions. Each work session needs three terminals (API, worker, SPA). Relay and ClickHouse are optional.

DS Lab is the only remote AI provider for fact extraction, embeddings and reranking. Without `DSLAB_API_KEY`, local extraction and embeddings use deterministic fakes. Photo processing uses the local filesystem unless S3-compatible Object Storage credentials are set. Photos are auto-approved only when `APP_ENV=local`.

```bash
# 1. API — http://127.0.0.1:8000  (needs DATABASE_URL for anything beyond /healthz)
cd backend && uv run ai-matchmaker

# 2. Worker — extract, embed, generate, photo jobs
cd backend && uv run ai-matchmaker-worker

# 3. SPA — http://localhost:5173
cd frontend && pnpm dev
```

Optional outbox → ClickHouse:

```bash
cd backend && uv run ai-matchmaker-relay
```

ClickHouse (optional, Homebrew cask; no `brew services`):

```bash
brew install --cask clickhouse
mkdir -p ~/.local/share/ai-matchmaker-clickhouse
(cd ~/.local/share/ai-matchmaker-clickhouse && clickhouse server --daemon \
  --log-file="$PWD/clickhouse.log" --errorlog-file="$PWD/clickhouse.err" \
  --pid-file="$PWD/clickhouse.pid")
cd backend && uv run ai-matchmaker-ch-init
```

Open the SPA. `/` calls `GET /healthz`. Register at `/register`, sign in at `/login`. Keep me signed in stores the opaque session in `localStorage`; otherwise it lives in `sessionStorage` until the tab closes. CORS allows `http://localhost:5173` and `http://127.0.0.1:5173` only. There is no Vite proxy. The SPA must not send `event_id`, `occurred_at`, actor, or analytics properties. Local-password auth refuses a non-loopback bind.

## Stop

Ctrl+C in each terminal that is running `ai-matchmaker`, `ai-matchmaker-worker`, `pnpm dev`, or `ai-matchmaker-relay`. Leave Postgres running.

If you started the ClickHouse daemon above:

```bash
kill "$(cat ~/.local/share/ai-matchmaker-clickhouse/clickhouse.pid)"
```

## Checks

```bash
cd backend && uv run pytest -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
```

## Container artifact

The same backend image runs API, worker and relay. Migrations stay an explicit
operator action and are never run by application startup.

```bash
docker compose build
docker compose run --rm --no-deps api alembic upgrade head
docker compose up -d api worker relay
```

`backend/.env` is local-only. A deployed environment injects the same settings
from its secret store through `BACKEND_ENV_FILE`; do not bake secrets into the
image.

Build the separate static frontend artifact with its target API origin:

```bash
cd frontend && VITE_API_BASE_URL=https://api.<domain> pnpm build
```

Alembic (optional; needs `DATABASE_DIRECT_URL` pointing at Postgres):

```bash
cd backend && uv run alembic upgrade head
cd backend && uv run alembic current
```

API startup does not run migrations. Driver: `psycopg` (sync `postgresql+psycopg://` for Alembic, async `postgresql+psycopg_async://` for the app).

## Lockfiles

- `backend/uv.lock`
- `frontend/pnpm-lock.yaml`

CI is not configured. Provider choice remains `TBD-INF03`.
