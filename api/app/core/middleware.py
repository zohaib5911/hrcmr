"""Request-id and access-log middleware (pure ASGI, so it is safe with streaming responses)."""

from __future__ import annotations

import re
import time
import uuid
from typing import TYPE_CHECKING

import structlog
from starlette.datastructures import Headers, MutableHeaders

from app.core.logging import get_logger

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
# Only accept a caller-supplied id if it is short and boring; anything else could be used to
# forge or inject log lines.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{8,64}")
_QUIET_PATHS = ("/health", "/ready")

logger = get_logger("app.http")


class RequestContextMiddleware:
    """Assign a request id, echo it in ``X-Request-ID``, and log one line per request.

    The log line records the method, path (never the query string), status and duration.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = Headers(scope=scope).get(REQUEST_ID_HEADER)
        request_id = (
            supplied if supplied and _VALID_REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        )
        scope.setdefault("state", {})["request_id"] = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        status = 500  # what the server will answer if the app raises before responding
        started = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            path: str = scope["path"]
            quiet = status < 400 and path.endswith(_QUIET_PATHS)
            log = logger.debug if quiet else logger.error if status >= 500 else logger.info
            log(
                "http_request",
                method=scope["method"],
                path=path,
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            structlog.contextvars.clear_contextvars()
