# AI Dating

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

Three processes plus an optional extraction worker. Postgres is optional for `/healthz`; outbox relay needs Postgres + ClickHouse. Fact extraction, embeddings, and photo processing use the local fake/filesystem unless `DSLAB_API_KEY`, `OPENROUTER_API_KEY`, Yandex AI Studio, or S3 credentials are set. Photos are auto-approved only when `APP_ENV=local`.

```bash
cd backend && uv run ai-dating          # http://127.0.0.1:8000
cd frontend && pnpm dev                 # http://localhost:5173
cd backend && uv run ai-dating-relay    # outbox -> ClickHouse
cd backend && uv run ai-dating-worker   # extract, embed, generate, photo jobs
```

ClickHouse (optional, Homebrew cask; no `brew services`):

```bash
brew install --cask clickhouse
mkdir -p ~/.local/share/ai-dating-clickhouse
(cd ~/.local/share/ai-dating-clickhouse && clickhouse server --daemon \
  --log-file="$PWD/clickhouse.log" --errorlog-file="$PWD/clickhouse.err" \
  --pid-file="$PWD/clickhouse.pid")
cd backend && uv run ai-dating-ch-init
```

Open the SPA. `/` calls `GET /healthz`. Register at `/register`, sign in at `/login`. Keep me signed in stores the opaque session in `localStorage`; otherwise it lives in `sessionStorage` until the tab closes. CORS allows `http://localhost:5173` and `http://127.0.0.1:5173` only. There is no Vite proxy. The SPA must not send `event_id`, `occurred_at`, actor, or analytics properties. Local-password auth refuses a non-loopback bind.

## Checks

```bash
cd backend && uv run pytest -q
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm tsc --noEmit && pnpm build
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
