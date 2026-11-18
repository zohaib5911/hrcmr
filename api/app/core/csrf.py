"""CSRF protection by signed double submit (plan.md 4.2, C6.1.6).

SameSite=Lax already keeps other sites from sending our cookies on a POST. This is the second lock:
every state-changing request must carry an ``X-CSRF-Token`` header equal to the non-HttpOnly
``csrf`` cookie. A page on another site can make the browser send the cookie, but it cannot read it
to copy it into a header.

The token is also signed and bound to the session cookies the browser holds:
``<random>.<HMAC-SHA256(session secret, random | session cookies)>``. A cookie planted from a
sibling subdomain (``Domain=.DOMAIN``) therefore does not pass, and a token minted for one session
is refused with another. A fresh token is issued on any response that changes a session cookie
(sign-in, two-step, company switch, sign-out), and whenever the browser's token does not match the
session it holds; a refused request carries one too, so a retry works.

Signature-verified server-to-server calls (the Stripe webhook) have no browser and no cookie, so
they are exempt by path prefix, and must verify their own signature instead.
"""

from __future__ import annotations

import hashlib
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


def _binding(sessions: tuple[str | None, ...]) -> str:
    """What a token is bound to: the session cookies the browser holds, or "anon" for none."""
    return "|".join(value or "" for value in sessions) if any(sessions) else "anon"


def _signature(secret: bytes, nonce: str, binding: str) -> str:
    return hmac.new(secret, f"{nonce}|{binding}".encode(), hashlib.sha256).hexdigest()


def new_csrf_token(secret: bytes, sessions: tuple[str | None, ...] = ()) -> str:
    """A token bound to these session cookie values (in the middleware's order)."""
    nonce = secrets.token_urlsafe(24)
    return f"{nonce}.{_signature(secret, nonce, _binding(sessions))}"


def csrf_token_valid(token: str, secret: bytes, sessions: tuple[str | None, ...]) -> bool:
    nonce, _, signature = token.partition(".")
    if not nonce or not signature:
        return False
    expected = _signature(secret, nonce, _binding(sessions))
    # Bytes, not text: compare_digest raises TypeError on non-ASCII text (a 500).
    return hmac.compare_digest(expected.encode(), signature.encode())


def _morsels(raw: str | None) -> SimpleCookie:
    """Parsed cookies; empty when the header cannot be read (it is then ignored, never trusted)."""
    jar: SimpleCookie = SimpleCookie()
    if raw:
        try:
            jar.load(raw)
        except Exception:
            return SimpleCookie()
    return jar


def _cookies(raw: str | None) -> dict[str, str]:
    return {name: morsel.value for name, morsel in _morsels(raw).items()}


def _set_cookies(message: Message) -> dict[str, str | None]:
    """The cookies this response sets, by name; ``None`` for one it deletes."""
    changed: dict[str, str | None] = {}
    for name, value in message.get("headers", []):
        if name.lower() != b"set-cookie":
            continue
        for key, morsel in _morsels(value.decode("latin-1")).items():
            expired = morsel["max-age"] == "0" or (
                morsel["expires"] != "" and "1970" in str(morsel["expires"])
            )
            changed[key] = None if expired or morsel.value == "" else morsel.value
    return changed


class CsrfMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        secret: str,
        session_cookies: tuple[str, ...],
        secure: bool,
        cookie_domain: str | None = None,
    ) -> None:
        self.app = app
        self._secret = secret.encode()
        self._sessions = session_cookies
        self._cookie = f"{CSRF_COOKIE}=%s; Path=/; SameSite=Lax" + ("; Secure" if secure else "")
        if cookie_domain:
            self._cookie += f"; Domain={cookie_domain}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        jar = _cookies(headers.get("cookie"))
        cookie = jar.get(CSRF_COOKIE)
        sessions = tuple(jar.get(name) for name in self._sessions)
        method, path = scope["method"], scope["path"]

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                # The session the browser will hold after this response.
                changed = _set_cookies(message)
                after = tuple(
                    changed.get(name, value)
                    for name, value in zip(self._sessions, sessions, strict=True)
                )
                if not cookie or not csrf_token_valid(cookie, self._secret, after):
                    MutableHeaders(scope=message).append(
                        "set-cookie", self._cookie % new_csrf_token(self._secret, after)
                    )
            await send(message)

        if method in UNSAFE_METHODS and not path.startswith(EXEMPT_PREFIXES):
            supplied = headers.get(CSRF_HEADER)
            if (
                not cookie
                or not supplied
                # Bytes, not text: compare_digest raises TypeError on non-ASCII text (a 500).
                or not hmac.compare_digest(cookie.encode(), supplied.encode())
                or not csrf_token_valid(cookie, self._secret, sessions)
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
                await response(scope, receive, send_with_cookie)
                return

        await self.app(scope, receive, send_with_cookie)
