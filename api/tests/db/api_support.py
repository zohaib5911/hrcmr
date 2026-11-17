"""Shared set-up for tests that call the API as a signed-in person of a company."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.db.ids import uuid7
from app.db.session import GlobalSession
from app.integrations.anthropic import Anthropic
from tests.db.support import engine_for
from tests.support import csrf_ready

if TYPE_CHECKING:
    from app.modules.auth.sessions import SessionStore
    from tests.db.support import DatabaseUnderTest


async def two_companies(database: DatabaseUnderTest) -> tuple[uuid.UUID, uuid.UUID]:
    """Empties the people and companies, then makes companies "a" and "b", both on a paid plan (a
    free company is read-only, T16.2; tests of that set the plan themselves)."""
    a, b = uuid7(), uuid7()
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.begin() as c:
        await c.execute(text("truncate users, companies cascade"))
        for ident, slug in ((a, "a"), (b, "b")):
            await c.execute(
                text(
                    "insert into companies (id, name, slug, plan, subscription_status) "
                    "values (:i, :n, :s, 'annual', 'active')"
                ),
                {"i": ident, "n": f"Company {slug}", "s": slug},
            )
    await owner.dispose()
    return a, b


async def sign_in_as(
    database: DatabaseUnderTest,
    sessions: SessionStore,
    app: Any,
    role: str,
    company: uuid.UUID,
) -> httpx.AsyncClient:
    """A browser-like client signed in as a new person with ``role`` in ``company``."""
    user = uuid7()
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.begin() as c:
        await c.execute(
            text(
                "insert into users (id, email, first_name, last_name, password_hash, "
                "email_verified_at) values (:u, :e, 'Ann', :r, 'x', now())"
            ),
            {"u": user, "e": f"{role}-{user}@example.com", "r": role},
        )
        await c.execute(
            text("insert into memberships (user_id, company_id, role) values (:u, :c, :r)"),
            {"u": user, "c": company, "r": role},
        )
        await c.execute(
            text(
                "insert into terms_acceptances (user_id, version) "
                "select :u, version from terms_versions"
            ),
            {"u": user},
        )
    await owner.dispose()
    engine = engine_for(database.app_url, poolclass=NullPool)
    async with GlobalSession(engine) as db:
        token, _ = await sessions.create(
            db, user_id=user, company_id=company, ip=None, user_agent=None, mfa_passed=True
        )
        await db.commit()
    await engine.dispose()
    browser = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )
    browser.cookies.set("brand_session", token)
    csrf_ready(browser, app)
    return browser


def fake_claude(app: Any, *, reply: str = "", status: int = 200) -> list[str]:
    """Point the app at a fake Anthropic that answers ``reply``; returns each request body sent."""
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.content.decode("utf-8"))
        if status != 200:
            return httpx.Response(status, json={"type": "error"})
        return httpx.Response(
            200,
            json={
                "model": "claude-haiku-5-5",
                "content": [{"type": "text", "text": reply}],
                "usage": {"input_tokens": 12, "output_tokens": 34},
            },
        )

    app.state.anthropic = Anthropic(
        "test-key",
        model_main="claude-sonnet-5-5",
        model_fast="claude-haiku-5-5",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    return sent
