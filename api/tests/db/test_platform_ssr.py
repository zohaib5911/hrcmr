"""SSR identity protocol: internal API hop, allowlist and database audit."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import httpx
from sqlalchemy import text

from tests.db.support import DatabaseUnderTest
from tests.db.test_platform_session import API, _rig

SSR_SECRET = "ssssssssssssssssssssssssssssssss"
TARGET = f"{API}/platform/metrics"


def _ssr_headers(cookie: str, ip: str, *, age: int = 0) -> dict[str, str]:
    value = {
        "ip": ip,
        "ua": "Real admin browser",
        "at": int(time.time()) - age,
        "method": "GET",
        "target": TARGET,
        "cookie": hashlib.sha256(cookie.encode()).hexdigest(),
    }
    payload = base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    return {
        "cookie": cookie,
        "x-platform-visitor": payload,
        "x-platform-signature": hmac.new(
            SSR_SECRET.encode(), payload.encode(), hashlib.sha256
        ).hexdigest(),
    }


async def test_ssr_verified_visitor_allowlist_and_audit(database: DatabaseUnderTest) -> None:
    async with _rig(database, "127.0.0.1,203.0.113.7", platform_ssr_secret=SSR_SECRET) as rig:
        admin = await rig["admin"]()
        assert (await admin.post(f"{API}/auth/platform-session")).status_code == 201
        cookie = admin.cookies.get("brand_platform_session")
        headers = _ssr_headers(f"brand_platform_session={cookie}", "203.0.113.7")
        assert headers is not None
        # The web server itself is outside the allowlist. It gets no proxy trust.
        transport = httpx.ASGITransport(app=rig["app"], client=("10.9.0.2", 5000))
        async with httpx.AsyncClient(transport=transport, base_url="http://api.internal") as ssr:
            allowed = await ssr.get(TARGET, headers=headers)
            assert allowed.status_code == 200, allowed.text
            assert allowed.json()["companies_active"] == 1
            async with rig["owner"].connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            "select host(ip), user_agent from audit_events where actor_user_id=:u "
                            "and action='platform.access' order by created_at desc limit 1"
                        ),
                        {"u": admin.user},
                    )
                ).one()
                assert tuple(row) == ("203.0.113.7", "Real admin browser")
            denied_headers = _ssr_headers(f"brand_platform_session={cookie}", "198.51.100.9")
            assert denied_headers is not None
            assert (await ssr.get(TARGET, headers=denied_headers)).status_code == 403
            # Arbitrary client forwarding headers and a forged assertion cannot grant access.
            for forged in (
                {
                    "cookie": headers["cookie"],
                    "x-real-ip": "203.0.113.7",
                    "x-forwarded-for": "203.0.113.7",
                },
                {**headers, "x-platform-signature": "0" * 64},
                {**headers, "x-platform-signature": "invalid"},
                _ssr_headers(headers["cookie"], "203.0.113.7", age=60),
                {**headers, "cookie": headers["cookie"] + "; other=changed"},
            ):
                assert (await ssr.get(TARGET, headers=forged)).status_code == 403
            # An otherwise valid assertion cannot be replayed against a different URL.
            assert (await ssr.get(f"{API}/platform/companies", headers=headers)).status_code == 403
            async with rig["owner"].connect() as connection:
                assert (
                    await connection.execute(
                        text(
                            "select count(*) from audit_events where actor_user_id=:u and action='platform.access'"
                        ),
                        {"u": admin.user},
                    )
                ).scalar_one() == 1
