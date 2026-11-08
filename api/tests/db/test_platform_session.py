"""T17.1: the platform session. A platform admin reaches the admin routes only with the platform
cookie, after MFA, from an allowed network. A tenant session never opens them, a platform session
never works on the tenant routes, and every admin-area request is audited."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import NullPool

from app.db.ids import uuid7
from app.db.session import GlobalSession
from app.main import create_app
from app.modules.auth.sessions import SessionStore
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

API = "/api/v1"
TENANT_COOKIE = "brand_session"
PLATFORM_COOKIE = "brand_platform_session"


@asynccontextmanager
async def _rig(database: DatabaseUnderTest, allowlist: str = "") -> AsyncIterator[dict[str, Any]]:
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()
    company = uuid7()
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.begin() as c:
        await c.execute(text("truncate users, companies cascade"))
        await c.execute(
            text(
                "insert into companies (id, name, slug, plan, subscription_status) "
                "values (:i, 'Company a', 'a', 'annual', 'active')"
            ),
            {"i": company},
        )
    settings = build_settings(
        database_url=database.app_url, redis_url=TEST_REDIS_URL, admin_ip_allowlist=allowlist
    )
    app = create_app(settings)
    sessions = SessionStore(redis)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    def browser(cookies: dict[str, str]) -> httpx.AsyncClient:
        client = httpx.AsyncClient(transport=transport, base_url="http://test")
        for name, value in cookies.items():
            client.cookies.set(name, value)
        client.cookies.set("csrf", "t")
        client.headers["X-CSRF-Token"] = "t"
        return client

    async def admin(*, mfa_enabled: bool = True, mfa_passed: bool = True) -> httpx.AsyncClient:
        """A company admin who is also a platform admin, signed in on the tenant cookie only."""
        user = uuid7()
        async with owner.begin() as c:
            await c.execute(
                text(
                    "insert into users (id, email, first_name, last_name, password_hash, "
                    "email_verified_at, mfa_enabled) "
                    "values (:u, :e, 'Ann', 'Admin', 'x', now(), :m)"
                ),
                {"u": user, "e": f"admin-{user}@example.com", "m": mfa_enabled},
            )
            await c.execute(
                text(
                    "insert into memberships (user_id, company_id, role) values (:u, :c, 'company_admin')"
                ),
                {"u": user, "c": company},
            )
            await c.execute(
                text(
                    "insert into terms_acceptances (user_id, version) "
                    "select :u, version from terms_versions"
                ),
                {"u": user},
            )
            await c.execute(
                text("insert into platform_admins (user_id, level) values (:u, 'support')"),
                {"u": user},
            )
        engine: AsyncEngine = engine_for(database.app_url, poolclass=NullPool)
        async with GlobalSession(engine) as db:
            token, _ = await sessions.create(
                db,
                user_id=user,
                company_id=company,
                ip=None,
                user_agent=None,
                mfa_passed=mfa_passed,
            )
            await db.commit()
        await engine.dispose()
        client = browser({TENANT_COOKIE: token})
        client.user = user  # type: ignore[attr-defined]
        return client

    async with LifespanManager(app):
        try:
            yield {"admin": admin, "anonymous": lambda: browser({}), "owner": owner}
        finally:
            await owner.dispose()
            await redis.flushdb()
            await redis.aclose()


async def _audit(owner: AsyncEngine, user: uuid.UUID) -> list[tuple[str, str | None]]:
    async with owner.connect() as c:
        rows = await c.execute(
            text(
                "select action, summary from audit_events "
                "where actor_user_id = :u order by created_at"
            ),
            {"u": user},
        )
        return [(row.action, row.summary) for row in rows]


async def test_a_tenant_session_is_refused_on_the_admin_routes(database: DatabaseUnderTest) -> None:
    async with _rig(database) as rig:
        admin = await rig["admin"]()
        refused = await admin.get(f"{API}/platform/rules")
        assert refused.status_code == 403, refused.text
        assert refused.json()["error"]["code"] == "FORBIDDEN"
        anonymous = await rig["anonymous"]().get(f"{API}/platform/rules")
        assert anonymous.status_code == 401


async def test_a_platform_session_is_refused_on_the_tenant_routes(
    database: DatabaseUnderTest,
) -> None:
    async with _rig(database) as rig:
        admin = await rig["admin"]()
        assert (await admin.post(f"{API}/auth/platform-session")).status_code == 201
        token = admin.cookies.get(PLATFORM_COOKIE)
        assert token
        # The platform token presented on the tenant cookie is not a tenant session.
        as_tenant = rig["anonymous"]()
        as_tenant.cookies.set(TENANT_COOKIE, token)
        assert (await as_tenant.get(f"{API}/auth/me")).status_code == 401


async def test_no_authenticator_means_no_platform_session(database: DatabaseUnderTest) -> None:
    async with _rig(database) as rig:
        admin = await rig["admin"](mfa_enabled=False)
        refused = await admin.post(f"{API}/auth/platform-session")
        assert refused.status_code == 403, refused.text
        assert refused.json()["error"]["code"] == "MFA_ENROLMENT_REQUIRED"
        assert admin.cookies.get(PLATFORM_COOKIE) is None
        assert (await admin.get(f"{API}/platform/rules")).status_code == 403


async def test_a_session_that_has_not_passed_mfa_gets_no_platform_session(
    database: DatabaseUnderTest,
) -> None:
    async with _rig(database) as rig:
        admin = await rig["admin"](mfa_passed=False)
        refused = await admin.post(f"{API}/auth/platform-session")
        assert refused.status_code == 403, refused.text
        assert refused.json()["error"]["code"] == "MFA_REQUIRED"
        assert admin.cookies.get(PLATFORM_COOKIE) is None


async def test_the_platform_cookie_is_its_own_and_every_request_is_audited(
    database: DatabaseUnderTest,
) -> None:
    async with _rig(database) as rig:
        admin = await rig["admin"]()
        started = await admin.post(f"{API}/auth/platform-session")
        assert started.status_code == 201, started.text
        assert started.headers["set-cookie"].startswith(f"{PLATFORM_COOKIE}=")
        assert (await admin.get(f"{API}/platform/rules")).status_code == 200
        # The tenant session is untouched by the platform session.
        assert (await admin.get(f"{API}/auth/me")).status_code == 200
        actions = await _audit(rig["owner"], admin.user)
        assert ("platform.session.started", None) in actions
        assert ("platform.access", "GET /api/v1/platform/rules") in actions


async def test_ending_the_platform_session_keeps_the_tenant_session(
    database: DatabaseUnderTest,
) -> None:
    async with _rig(database) as rig:
        admin = await rig["admin"]()
        assert (await admin.post(f"{API}/auth/platform-session")).status_code == 201
        ended = await admin.delete(f"{API}/auth/platform-session")
        assert ended.status_code == 204, ended.text
        assert admin.cookies.get(PLATFORM_COOKIE) is None
        assert (await admin.get(f"{API}/platform/rules")).status_code == 403
        assert (await admin.get(f"{API}/auth/me")).status_code == 200
        actions = await _audit(rig["owner"], admin.user)
        assert ("platform.session.ended", None) in actions


async def test_the_admin_network_allowlist_refuses_a_platform_session(
    database: DatabaseUnderTest,
) -> None:
    # The test client's address is 127.0.0.1, so an allowlist naming only another network refuses it.
    async with _rig(database, allowlist="203.0.113.7") as rig:
        admin = await rig["admin"]()
        refused = await admin.post(f"{API}/auth/platform-session")
        assert refused.status_code == 403, refused.text
        assert refused.json()["error"]["code"] == "FORBIDDEN"
        assert admin.cookies.get(PLATFORM_COOKIE) is None
    async with _rig(database, allowlist="127.0.0.0/8") as rig:
        admin = await rig["admin"]()
        assert (await admin.post(f"{API}/auth/platform-session")).status_code == 201
        assert (await admin.get(f"{API}/platform/rules")).status_code == 200
