from __future__ import annotations

import time
import uuid
from importlib.metadata import version

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ai_dating.config import Settings, is_ready, load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.errors import register_error_handlers
from ai_dating.logging import configure_logging

_REQUEST_ID_MAX_LEN = 128
log = structlog.get_logger("ai_dating.access")


def app_version() -> str:
    return version("ai-dating")


def _request_id_from(request: Request) -> str:
    incoming = request.headers.get("x-request-id", "").strip()
    if (
        incoming
        and len(incoming) <= _REQUEST_ID_MAX_LEN
        and incoming.isascii()
        and incoming.isprintable()
    ):
        return incoming
    return str(uuid.uuid4())


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else request.url.path


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings)

    app = FastAPI(title="AI Dating", version=app_version())
    app.state.settings = settings
    app.state.engine = None
    if settings.database_url or settings.database_direct_url:
        app.state.engine = create_sync_engine(settings)
    register_error_handlers(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next) -> Response:
        request_id = _request_id_from(request)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            log.info(
                "request",
                route=_route_template(request),
                status=status,
                duration_ms=round((time.perf_counter() - start) * 1000, 1),
            )
            structlog.contextvars.unbind_contextvars("request_id")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
        allow_headers=[
            "X-Request-ID",
            "Authorization",
            "Idempotency-Key",
            "Content-Type",
        ],
        expose_headers=["X-Request-ID"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": app_version()}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        request_id = structlog.contextvars.get_contextvars().get("request_id", "")
        clickhouse_ok = None
        if settings.clickhouse_url:
            from ai_dating.events.clickhouse import ClickHouseSink

            sink = ClickHouseSink(settings)
            try:
                clickhouse_ok = sink.ping()
            finally:
                sink.close()
        if not is_ready(settings, clickhouse_ok=clickhouse_ok):
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "dependency_unavailable",
                        "message": "Service is not ready.",
                        "request_id": request_id,
                    }
                },
            )
        return JSONResponse({"status": "ok"})

    if settings.app_env == "local":
        from ai_dating.accounts.routes import router as accounts_router
        from ai_dating.matching.routes import router as matching_router
        from ai_dating.media.routes import local_router as media_local_router
        from ai_dating.media.routes import router as media_router
        from ai_dating.messaging.routes import router as messaging_router
        from ai_dating.metadata.routes import router as metadata_router
        from ai_dating.onboarding.routes import router as onboarding_router
        from ai_dating.privacy.routes import router as privacy_router
        from ai_dating.profiles.routes import router as profiles_router
        from ai_dating.recommendations.routes import router as recommendations_router
        from ai_dating.safety.routes import router as safety_router

        app.include_router(accounts_router)
        app.include_router(privacy_router)
        app.include_router(onboarding_router)
        app.include_router(profiles_router)
        app.include_router(media_router)
        if settings.object_storage_backend == "local":
            app.include_router(media_local_router)
        app.include_router(recommendations_router)
        app.include_router(matching_router)
        app.include_router(messaging_router)
        app.include_router(safety_router)
        app.include_router(metadata_router)

    return app
