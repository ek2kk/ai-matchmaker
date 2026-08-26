from __future__ import annotations

from typing import Any

import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def error_payload(
    code: str,
    message: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> dict:
    body: dict[str, Any] = {
        "error": {"code": code, "message": message, "request_id": request_id}
    }
    if details:
        body["error"]["details"] = details
    return body


def request_id_of() -> str:
    return str(structlog.contextvars.get_contextvars().get("request_id", ""))


def register_error_handlers(app) -> None:
    @app.exception_handler(AppError)
    def app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=error_payload(exc.code, exc.message, request_id_of(), exc.details),
        )

    @app.exception_handler(RequestValidationError)
    def validation_error(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "validation_error", "Invalid request.", request_id_of()
            ),
        )
