"""Authenticate SSR visitor assertions; ordinary API callers retain socket/proxy identity."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import time
from typing import TYPE_CHECKING

from app.core.errors import ForbiddenError
from app.modules.auth.deps import client_ip, user_agent

if TYPE_CHECKING:
    from fastapi import Request

    from app.core.config import Settings


def platform_visitor(request: Request, settings: Settings) -> tuple[str | None, str | None]:
    payload = request.headers.get("x-platform-visitor")
    signature = request.headers.get("x-platform-signature")
    if payload is None and signature is None:
        return client_ip(request), user_agent(request)
    secret = settings.platform_ssr_secret
    if not payload or not signature or not secret or len(payload) > 16384:
        raise ForbiddenError
    expected = hmac.new(
        secret.get_secret_value().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature.encode(), expected.encode()):
        raise ForbiddenError
    try:
        value = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        ip = str(ipaddress.ip_address(value["ip"]))
        ua = value["ua"]
        cookie = hashlib.sha256(request.headers.get("cookie", "").encode()).hexdigest()
        if (
            not isinstance(ua, str)
            or not isinstance(value["at"], int)
            or abs(time.time() - value["at"]) > 30
            or request.method != "GET"
            or value["method"] != request.method
            or value["target"]
            != request.url.path + (f"?{request.url.query}" if request.url.query else "")
            or value["cookie"] != cookie
        ):
            raise ForbiddenError
    except (ValueError, KeyError, TypeError):
        raise ForbiddenError from None
    return ip, ua
