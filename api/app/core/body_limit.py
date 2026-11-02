"""A ceiling on how much of a request body the server will read (plan.md 4.5, 4.6).

Without one, a client can send gigabytes to any endpoint and the server will spool them to disk
before the endpoint even looks. Most endpoints take small JSON, so the default is 1 MB; the upload
endpoint is the one place that takes a file, with the plan's 25 MB plus a little for the form around
it. A request that announces too much in ``Content-Length`` is refused at once; one that does not
(chunked) is cut off as soon as it has sent too much.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from starlette.datastructures import Headers

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_LIMIT = 1024 * 1024
UPLOAD_LIMIT = 26 * 1024 * 1024  # a 25 MB file and its form fields
LOGO_LIMIT = 3 * 1024 * 1024  # a 2 MB picture and its form fields


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, *, limits: dict[str, int] | None = None) -> None:
        self.app = app
        self.limits = limits or {}

    def _limit_for(self, path: str) -> int:
        for prefix, limit in self.limits.items():
            if path.startswith(prefix):
                return limit
        return DEFAULT_LIMIT

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return
        limit = self._limit_for(scope["path"])
        declared = Headers(scope=scope).get("content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            await self._refuse(scope, send)
            return

        received = 0
        refused = False

        async def counting_receive() -> Message:
            nonlocal received, refused
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    refused = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        started = False

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if refused and message["type"] == "http.response.start" and not started:
                started = True
                await self._refuse(scope, send)
                return
            if refused and started:
                return  # the app's own answer to the cut-off body is dropped
            await send(message)

        await self.app(scope, counting_receive, guarded_send)

    @staticmethod
    async def _refuse(scope: Scope, send: Send) -> None:
        body = json.dumps(
            {
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": "That is too large to send. Try a smaller file.",
                    "request_id": str(scope.get("state", {}).get("request_id", "unknown")),
                }
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
