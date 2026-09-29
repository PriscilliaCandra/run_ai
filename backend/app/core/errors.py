"""
Global exception handlers so the API never leaks raw validation internals,
stack traces, SQL errors, internal file paths, or provider error bodies to
the client. Full details are always logged server-side for debugging.

This fixes the consumer-facing issue identified in the audit: a raw FastAPI
422 payload (a stringified list of Pydantic error objects) was being shown
directly to end users on validation failure.
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _friendly_field_name(loc: tuple) -> str:
    # loc looks like ("body", "pb_5k") or ("query", "limit")
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return parts[-1] if parts else "input"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        logger.warning("Validation error on %s %s: %s", request.method, request.url.path, errors)

        field_errors = []
        for err in errors:
            field_errors.append({
                "field": _friendly_field_name(err.get("loc", ())),
                "message": err.get("msg", "This value is invalid."),
            })

        summary = "; ".join(f"{fe['field']}: {fe['message']}" for fe in field_errors) or "Please check your input and try again."

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": summary, "fields": field_errors},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred. Please try again."},
        )
