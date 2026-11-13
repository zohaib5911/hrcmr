"""One error shape for the whole API (plan.md T0.4 and section 11):

    {"error": {"code": "NOT_FOUND", "message": "...", "field": "email", "request_id": "..."}}

``field`` appears only when the error is about a single input. Messages are written for people:
they say what happened, and never contain a stack trace, SQL, or the value that was submitted.
"""

from __future__ import annotations

import traceback
from http import HTTPStatus
from typing import TYPE_CHECKING

import sentry_sdk
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.core.middleware import REQUEST_ID_HEADER

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import FastAPI, Request

logger = get_logger("app.errors")

_STATUS_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    402: "PLAN_REQUIRED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    503: "SERVICE_UNAVAILABLE",
}
_INTERNAL_MESSAGE = (
    "Something went wrong on our side. "
    "If it keeps happening, contact support and quote the request id."
)
_LOCATION_PREFIXES = {"body", "query", "path", "header", "cookie"}


class ErrorBody(BaseModel):
    code: str
    message: str
    field: str | None = None
    request_id: str


class ErrorEnvelope(BaseModel):
    """Documented in OpenAPI so the generated TypeScript client knows the error shape."""

    error: ErrorBody


class AppError(Exception):
    """Raise from services and routers; the handler turns it into the envelope."""

    def __init__(
        self, code: str, message: str, *, status_code: int = 400, field: str | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field = field


class NotFoundError(AppError):
    """Also used for another company's records, so their existence is never revealed."""

    def __init__(self, message: str = "We could not find that.") -> None:
        super().__init__("NOT_FOUND", message, status_code=404)


class ForbiddenError(AppError):
    def __init__(self, message: str = "You do not have permission to do that.") -> None:
        super().__init__("FORBIDDEN", message, status_code=403)


class ConflictError(AppError):
    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__("CONFLICT", message, status_code=409, field=field)


class PlanRequiredError(AppError):
    def __init__(self, message: str = "Subscribe to a paid plan to make changes.") -> None:
        super().__init__("PLAN_REQUIRED", message, status_code=402)


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    error: dict[str, str] = {"code": code, "message": message}
    if field:
        error["field"] = field
    error["request_id"] = request_id
    return JSONResponse(
        {"error": error},
        status_code=status_code,
        headers={**(headers or {}), REQUEST_ID_HEADER: request_id},
    )


async def _app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101  (narrowing for the type checker)
    return error_response(
        request, status_code=exc.status_code, code=exc.code, message=exc.message, field=exc.field
    )


async def _http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    code = _STATUS_CODES.get(exc.status_code, f"HTTP_{exc.status_code}")
    try:
        phrase = HTTPStatus(exc.status_code).phrase
    except ValueError:
        phrase = "Error"
    message = exc.detail if isinstance(exc.detail, str) and exc.detail else phrase
    return error_response(
        request,
        status_code=exc.status_code,
        code=code,
        message=message,
        headers=exc.headers,
    )


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    problems = exc.errors()
    first = problems[0]
    location = [str(part) for part in first["loc"]]
    if location and location[0] in _LOCATION_PREFIXES:
        location = location[1:]
    message = str(first["msg"]).removeprefix("Value error, ")
    if len(problems) > 1:
        message += f" ({len(problems) - 1} more problem{'s' if len(problems) > 2 else ''} to fix.)"
    # The submitted value (`input`) is deliberately never echoed back or logged.
    return error_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        message=message,
        field=".".join(location) or None,
    )


async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    sentry_sdk.capture_exception(exc)
    logger.error(
        "unhandled_exception",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        kind=type(exc).__name__,
        frames=[
            {"function": frame.name, "lineno": frame.lineno}
            for frame in traceback.extract_tb(exc.__traceback__)
        ],
    )
    return error_response(
        request, status_code=500, code="INTERNAL_ERROR", message=_INTERNAL_MESSAGE
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(StarletteHTTPException, _http_exception)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)
