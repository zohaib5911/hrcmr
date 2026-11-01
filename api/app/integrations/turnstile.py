"""Cloudflare Turnstile: proves a form was filled in by a person (plan.md 4.2 and 8.1).

The widget in the browser gives a one-time token; this checks it with Cloudflare, server side, using
the secret key (never sent to the browser). If Cloudflare cannot be reached, the answer is "no":
failing open would let a bot through whenever the check is down.

Locally and in tests there is no secret key, and the check is skipped. Deployed environments cannot
start without one (``turnstile_secret_key`` is in the required list in ``app/core/config.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.core.logging import get_logger

if TYPE_CHECKING:
    from pydantic import SecretStr

logger = get_logger("app.turnstile")

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TIMEOUT_SECONDS = 4.0


class Turnstile:
    def __init__(self, secret: SecretStr | None, client: httpx.AsyncClient | None = None) -> None:
        self._secret = secret
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._secret is not None

    async def verify(self, token: str | None, remote_ip: str | None = None) -> bool:
        if self._secret is None:
            return True
        if not token:
            return False
        form = {"secret": self._secret.get_secret_value(), "response": token}
        if remote_ip:
            form["remoteip"] = remote_ip
        client = self._client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
        try:
            response = await client.post(VERIFY_URL, data=form, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            return bool(response.json().get("success"))
        except (httpx.HTTPError, ValueError):
            logger.warning("turnstile_unavailable")
            return False
        finally:
            if self._client is None:
                await client.aclose()
