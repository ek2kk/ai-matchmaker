FROM ghcr.io/astral-sh/uv:0.9.18-python3.13-bookworm-slim AS build

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/src ./src
RUN uv sync --locked --no-dev

FROM python:3.13-slim-bookworm AS runtime

RUN groupadd --system app && useradd --system --gid app --create-home app
WORKDIR /app
COPY --from=build --chown=app:app /app/.venv ./.venv
COPY --from=build --chown=app:app /app/alembic.ini ./
COPY --from=build --chown=app:app /app/alembic ./alembic
COPY --from=build --chown=app:app /app/src ./src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
CMD ["ai-matchmaker"]
