"""Typed error model + global exception handlers.

All API errors return a consistent envelope:
    { "error": { "code": "...", "message": "..." } }

Rules:
- Raise `AppError` for expected domain/infra failures.
- FastAPI validation errors and unhandled exceptions are converted
  to the same envelope (without leaking internals in production).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("krushi-seva")


class AppError(Exception):
    """Expected application error with a machine-readable code."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "APP_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def error_envelope(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(exc.code, exc.message),
    )


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Keep the message concise; details stay in logs.
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_envelope("VALIDATION_ERROR", "Invalid request payload."),
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_envelope("INTERNAL_ERROR", "Something went wrong. Please try again."),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all handlers. Called once in the app factory."""
    app.add_exception_handler(AppError, _handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_unexpected_error)
