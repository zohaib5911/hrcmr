"""CSRF protection by double submit (plan.md 4.2).

SameSite=Lax already keeps other sites from sending our cookies on a POST. This is the second lock:
every state-changing request must carry an ``X-CSRF-Token`` header equal to the non-HttpOnly
``csrf`` cookie. A page on another site can make the browser send the cookie, but it cannot read it
to copy it into a header. The cookie is issued on the first response a browser gets from us.

Signature-verified server-to-server calls (the Stripe webhook) have no browser and no cookie, so
they are exempt by path prefix, and must verify their own signature instead.
"""

from __future__ import annotations

import hmac
import secrets
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSRF_COOKIE = "csrf"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
EXEMPT_PREFIXES = ("/api/v1/webhooks/",)
_MESSAGE = "Your session could not be verified. Reload the page and try again."


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _cookie_value(headers: Headers, name: str) -> str | None:
    raw = headers.get("cookie")
    if not raw:
        return None
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(raw)
    except Exception:
        return None
    morsel = jar.get(name)
    return morsel.value if morsel else None


class CsrfMiddleware:
    def __init__(self, app: ASGIApp, *, secure: bool, cookie_domain: str | None = None) -> None:
        self.app = app
        self._cookie = f"{CSRF_COOKIE}=%s; Path=/; SameSite=Lax" + ("; Secure" if secure else "")
        if cookie_domain:
            self._cookie += f"; Domain={cookie_domain}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        cookie = _cookie_value(headers, CSRF_COOKIE)
        method, path = scope["method"], scope["path"]

        if method in UNSAFE_METHODS and not path.startswith(EXEMPT_PREFIXES):
            supplied = headers.get(CSRF_HEADER)
            # Bytes, not text: compare_digest raises TypeError on non-ASCII text (a 500).
            if (
                not cookie
                or not supplied
                or not hmac.compare_digest(cookie.encode(), supplied.encode())
            ):
                response = JSONResponse(
                    {
                        "error": {
                            "code": "CSRF_INVALID",
                            "message": _MESSAGE,
                            "request_id": str(scope.get("state", {}).get("request_id", "unknown")),
                        }
                    },
                    status_code=403,
                )
                await response(scope, receive, send)
                return

        issue = cookie is None

        async def send_with_cookie(message: Message) -> None:
            if issue and message["type"] == "http.response.start":
                MutableHeaders(scope=message).append("set-cookie", self._cookie % new_csrf_token())
            await send(message)

        await self.app(scope, receive, send_with_cookie)
