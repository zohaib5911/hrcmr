"""T2.4: the /auth endpoints end to end (HTTP in, database and Redis behind), including that the
answers do not reveal whether an e-mail address has an account."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.core.totp import totp
from app.db.session import GlobalSession
from app.main import create_app
from app.modules.auth.invitations import create_invitation
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

PASSWORD = "a long, unusual passphrase 42"
NEW_PASSWORD = "another long, unusual passphrase 77"
CSRF = "a-test-csrf-token"
# The audit trail cannot be emptied between tests (that is the point of it), so ask only about the
# companies this test created.
AUDIT_ACTIONS = "select action from audit_events where company_id in (select id from companies)"


@dataclass
class Mailbox:
    sent: list[tuple[str, str, dict[str, str]]] = field(default_factory=list)

    async def send_template(self, *, to: str, template: str, data: dict[str, str]) -> None:
        self.sent.append((to, template, data))

    def of(self, template: str, to: str | None = None) -> list[dict[str, str]]:
        return [d for t, name, d in self.sent if name == template and (to is None or t == to)]

    def token(self, template: str, to: str) -> str:
        return self.of(template, to)[-1]["link"].split("token=", 1)[1]


@dataclass
class World:
    client: httpx.AsyncClient
    mail: Mailbox
    db: DatabaseUnderTest
    redis: Redis

    async def sql(self, statement: str, **params: Any) -> list[Any]:
        engine = engine_for(self.db.owner_url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                result = await connection.execute(text(statement), params)
                return list(result.all()) if result.returns_rows else []
        finally:
            await engine.dispose()

    def new_browser(self) -> httpx.AsyncClient:
        transport = self.client._transport
        browser = httpx.AsyncClient(transport=transport, base_url="http://test")
        browser.cookies.set("csrf", CSRF)
        browser.headers["X-CSRF-Token"] = CSRF
        return browser


@pytest.fixture
async def world(database: DatabaseUnderTest) -> AsyncIterator[World]:
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.begin() as connection:
        await connection.execute(text("truncate users, companies cascade"))
    await owner.dispose()

    mail = Mailbox()
    settings = build_settings(database_url=database.app_url, redis_url=TEST_REDIS_URL)
    app = create_app(settings, mailer=mail)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("csrf", CSRF)
            client.headers["X-CSRF-Token"] = CSRF
            yield World(client, mail, database, redis)
    await redis.flushdb()
    await redis.aclose()
    set_keyring(None)


def signup_body(email: str = "ada@example.com", **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "company_name": "Ada's Bakery",
        "bank_holiday_region": "england-and-wales",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": email,
        "password": PASSWORD,
        "accept_terms": True,
    }
    body.update(overrides)
    return body


async def signed_up(world: World, email: str = "ada@example.com") -> httpx.Response:
    assert (
        await world.client.post("/api/v1/auth/signup", json=signup_body(email))
    ).status_code == 202
    token = world.mail.token("verify_email", email)
    return await world.client.post("/api/v1/auth/verify-email", json={"token": token})


def without_request_id(response: httpx.Response) -> Any:
    body = response.json()
    body.get("error", {}).pop("request_id", None)
    return body


# --- signing up --------------------------------------------------------------------------------------


async def test_sign_up_creates_a_free_company_and_admin_then_the_link_signs_them_in(
    world: World,
) -> None:
    response = await world.client.post("/api/v1/auth/signup", json=signup_body())
    assert response.status_code == 202
    assert response.json() == {"status": "check_your_inbox"}
    assert "set-cookie" not in {k.lower() for k in response.headers}  # not signed in yet

    company = (
        await world.sql("select plan, status, mfa_policy, bank_holiday_region from companies")
    )[0]
    assert tuple(company) == ("free", "active", "optional", "england-and-wales")
    user = (await world.sql("select password_hash, email_verified_at from users"))[0]
    assert user[0].startswith("$argon2id$")
    assert PASSWORD not in user[0]
    assert user[1] is None
    assert (await world.sql("select role from memberships"))[0][0] == "company_admin"
    assert (await world.sql("select count(*) from leave_types"))[0][0] == 12
    assert (await world.sql("select count(*) from terms_acceptances"))[0][0] == 1
    assert [r[0] for r in await world.sql(AUDIT_ACTIONS)] == ["company.created", "auth.signup"]

    verified = await world.client.post(
        "/api/v1/auth/verify-email",
        json={"token": world.mail.token("verify_email", "ada@example.com")},
    )
    assert verified.status_code == 200
    body = verified.json()
    assert body["mfa_required"] is False
    me = body["me"]
    assert me["user"]["email_verified"] is True
    assert me["role"] == "company_admin"
    assert me["active_company_id"] == me["companies"][0]["company_id"]
    assert me["mfa"] == "not_required"
    assert me["terms_acceptance_required"] is False
    cookie = verified.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie

    assert (await world.client.get("/api/v1/auth/me")).json()["user"]["first_name"] == "Ada"

    again = await world.client.post(
        "/api/v1/auth/verify-email",
        json={"token": world.mail.token("verify_email", "ada@example.com")},
    )
    assert again.status_code == 410  # a link works once
    assert again.json()["error"]["code"] == "TOKEN_INVALID"


async def test_signing_up_with_an_address_that_has_an_account_looks_exactly_the_same(
    world: World,
) -> None:
    first = await world.client.post("/api/v1/auth/signup", json=signup_body())
    second = await world.client.post(
        "/api/v1/auth/signup", json=signup_body(company_name="Another")
    )
    assert (second.status_code, second.json()) == (first.status_code, first.json())
    assert (await world.sql("select count(*) from companies"))[0][0] == 1
    assert (await world.sql("select count(*) from users"))[0][0] == 1
    # The person who owns the address is told, instead.
    assert len(world.mail.of("account_exists", "ada@example.com")) == 1
    assert len(world.mail.of("verify_email", "ada@example.com")) == 1


async def test_sign_up_refuses_a_weak_password_missing_terms_and_too_many_attempts(
    world: World,
) -> None:
    for password in ("short", "passwordpassword"):
        weak = await world.client.post("/api/v1/auth/signup", json=signup_body(password=password))
        assert weak.status_code == 422
        assert weak.json()["error"]["code"] == "WEAK_PASSWORD"
        assert weak.json()["error"]["field"] == "password"
    no_terms = await world.client.post("/api/v1/auth/signup", json=signup_body(accept_terms=False))
    assert no_terms.json()["error"]["code"] == "TERMS_REQUIRED"
    assert (await world.sql("select count(*) from users"))[0][0] == 0

    for n in range(3):  # the three refusals above used 3 of the 5 hourly attempts
        await world.client.post("/api/v1/auth/signup", json=signup_body(f"p{n}@example.com"))
    blocked = await world.client.post("/api/v1/auth/signup", json=signup_body("late@example.com"))
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"


# --- signing in and out -------------------------------------------------------------------------------


async def test_a_wrong_password_and_an_unknown_address_get_the_same_answer(world: World) -> None:
    await signed_up(world)
    browser = world.new_browser()
    wrong = await browser.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": "not the password"}
    )
    unknown = await browser.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "not the password"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert without_request_id(wrong) == without_request_id(unknown)


async def test_signing_in_and_out(world: World) -> None:
    await signed_up(world)
    browser = world.new_browser()
    assert (await browser.get("/api/v1/auth/me")).status_code == 401

    login = await browser.post(
        "/api/v1/auth/login", json={"email": "Ada@Example.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    assert login.json()["me"]["role"] == "company_admin"
    assert (await browser.get("/api/v1/auth/me")).status_code == 200

    assert (await browser.post("/api/v1/auth/logout")).status_code == 204
    assert (await browser.get("/api/v1/auth/me")).status_code == 401


async def test_a_post_without_the_csrf_header_is_refused(world: World) -> None:
    transport = world.client._transport
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as bare:
        response = await bare.post(
            "/api/v1/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_INVALID"


async def test_too_many_wrong_passwords_lock_sign_in(world: World) -> None:
    await signed_up(world)
    browser = world.new_browser()
    for _ in range(5):
        await browser.post(
            "/api/v1/auth/login", json={"email": "ada@example.com", "password": "wrong password!!"}
        )
    locked = await browser.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
    )
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "RATE_LIMITED"


# --- passwords -------------------------------------------------------------------------------------


async def test_forgot_password_is_neutral_and_the_link_resets_and_signs_everyone_out(
    world: World,
) -> None:
    await signed_up(world)
    other = world.new_browser()
    await other.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": PASSWORD})
    assert (await other.get("/api/v1/auth/me")).status_code == 200

    known = await world.client.post(
        "/api/v1/auth/forgot-password", json={"email": "ada@example.com"}
    )
    unknown = await world.client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    assert (
        (known.status_code, known.json())
        == (unknown.status_code, unknown.json())
        == (202, {"status": "check_your_inbox"})
    )
    assert len(world.mail.of("reset_password")) == 1  # only the real address got a link
    token = world.mail.token("reset_password", "ada@example.com")

    weak = await world.client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "short"}
    )
    assert weak.status_code == 422
    assert (
        await world.client.post(
            "/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
        )
    ).status_code == 204

    assert (await other.get("/api/v1/auth/me")).status_code == 401  # every session ended
    fresh = world.new_browser()
    assert (
        await fresh.post(
            "/api/v1/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
        )
    ).status_code == 401
    assert (
        await fresh.post(
            "/api/v1/auth/login", json={"email": "ada@example.com", "password": NEW_PASSWORD}
        )
    ).status_code == 200
    reuse = await world.client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD + "x"}
    )
    assert reuse.status_code == 410


async def test_changing_a_password_needs_the_current_one_and_ends_other_sessions(
    world: World,
) -> None:
    await signed_up(world)
    other = world.new_browser()
    await other.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": PASSWORD})

    refused = await world.client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "not it at all!", "new_password": NEW_PASSWORD},
    )
    assert refused.status_code == 401
    ok = await world.client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert ok.status_code == 200
    assert (await world.client.get("/api/v1/auth/me")).status_code == 200  # this browser stays in
    assert (await other.get("/api/v1/auth/me")).status_code == 401
    assert len(world.mail.of("password_changed")) == 1
    actions = [r[0] for r in await world.sql(AUDIT_ACTIONS + " order by created_at")]
    assert actions[-1] == "auth.password.changed"


# --- two-step verification ---------------------------------------------------------------------------


async def test_two_step_verification_setup_challenge_step_up_and_turning_it_off(
    world: World,
) -> None:
    await signed_up(world)
    setup = (await world.client.post("/api/v1/auth/mfa/setup")).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    secret = setup["secret"]

    wrong = await world.client.post("/api/v1/auth/mfa/verify", json={"code": "000000"})
    assert wrong.status_code == 401
    done = await world.client.post("/api/v1/auth/mfa/verify", json={"code": totp(secret)})
    assert done.status_code == 200
    codes = done.json()["recovery_codes"]
    assert len(codes) == 10
    stored = (await world.sql("select mfa_secret, recovery_codes_hash from users"))[0]
    assert secret not in stored[0]  # encrypted at rest
    assert not set(codes) & set(stored[1])  # recovery codes are hashed

    browser = world.new_browser()
    login = await browser.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
    )
    assert login.json()["mfa_required"] is True
    assert login.json()["me"] is None
    assert (await browser.get("/api/v1/auth/me")).json()["mfa"] == "challenge"
    blocked = await browser.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "MFA_REQUIRED"

    # The code for the next 30-second step is accepted (one step of clock drift is allowed).
    challenge = await browser.post(
        "/api/v1/auth/mfa/challenge", json={"code": totp(secret, at=time.time() + 30)}
    )
    assert challenge.status_code == 200
    assert challenge.json()["mfa"] == "not_required"

    refused = await browser.post("/api/v1/auth/mfa/disable")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "STEP_UP_REQUIRED"
    assert (
        await browser.post("/api/v1/auth/step-up", json={"password": "wrong password!"})
    ).status_code == 401
    stepped = await browser.post("/api/v1/auth/step-up", json={"password": PASSWORD})
    assert stepped.json()["step_up_active"] is True
    assert (await browser.post("/api/v1/auth/mfa/disable")).status_code == 204
    assert (await world.sql("select mfa_enabled, mfa_secret from users"))[0][0] is False
    actions = [r[0] for r in await world.sql(AUDIT_ACTIONS + " order by created_at")]
    assert actions[-4:] == [
        "auth.login.succeeded",
        "auth.step_up.failed",
        "auth.step_up.succeeded",
        "auth.mfa.disabled",
    ]


async def test_a_company_that_requires_two_step_cannot_have_it_switched_off(world: World) -> None:
    await signed_up(world)
    await world.sql("update companies set mfa_policy = 'admins'")
    me = (await world.client.get("/api/v1/auth/me")).json()
    assert me["mfa"] == "enrol"  # the policy asks the admin to set it up
    secret = (await world.client.post("/api/v1/auth/mfa/setup")).json()["secret"]
    await world.client.post("/api/v1/auth/mfa/verify", json={"code": totp(secret)})
    await world.client.post("/api/v1/auth/step-up", json={"password": PASSWORD})
    refused = await world.client.post("/api/v1/auth/mfa/disable")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "FORBIDDEN"


# --- invitations, terms and companies -------------------------------------------------------------------


async def _invite(world: World, email: str, role: str = "employee") -> str:
    company = (await world.sql("select id from companies order by created_at limit 1"))[0][0]
    engine = engine_for(world.db.app_url, poolclass=NullPool)
    try:
        async with GlobalSession(engine) as db:
            token, _ = await create_invitation(
                db, company_id=company, email=email, role=role, invited_by=None
            )
            await db.commit()
    finally:
        await engine.dispose()
    return token


async def test_a_new_person_accepts_an_invitation_and_chooses_their_own_password(
    world: World,
) -> None:
    await signed_up(world)
    token = await _invite(world, "sam@example.com", "hr_admin")

    details = (await world.client.get(f"/api/v1/auth/invitations/{token}")).json()
    assert details["company_name"] == "Ada's Bakery"
    assert details["role"] == "hr_admin"
    assert details["has_account"] is False

    browser = world.new_browser()
    accepted = await browser.post(
        f"/api/v1/auth/invitations/{token}/accept",
        json={
            "first_name": "Sam",
            "last_name": "Jones",
            "password": NEW_PASSWORD,
            "accept_terms": True,
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["me"]["role"] == "hr_admin"
    assert (await browser.get("/api/v1/auth/me")).json()["user"]["email_verified"] is True

    reuse = await world.client.post(
        f"/api/v1/auth/invitations/{token}/accept",
        json={"first_name": "X", "last_name": "Y", "password": NEW_PASSWORD, "accept_terms": True},
    )
    assert reuse.status_code == 410
    assert reuse.json()["error"]["code"] == "INVITATION_INVALID"
    assert (await world.client.get("/api/v1/auth/invitations/not-a-token")).status_code == 410
    assert "invitation.accepted" in [
        r[0] for r in await world.sql("select action from audit_events")
    ]


async def test_someone_who_already_has_an_account_is_added_but_not_signed_in(world: World) -> None:
    await signed_up(world, "ada@example.com")
    await world.client.post("/api/v1/auth/logout")
    other = world.new_browser()
    await other.post("/api/v1/auth/signup", json=signup_body("bo@example.com", company_name="Bo's"))
    await other.post(
        "/api/v1/auth/verify-email",
        json={"token": world.mail.token("verify_email", "bo@example.com")},
    )
    token = await _invite(world, "bo@example.com")  # an invitation to Ada's company

    anonymous = world.new_browser()
    accepted = await anonymous.post(
        f"/api/v1/auth/invitations/{token}/accept",
        json={"first_name": "Bo", "last_name": "B", "accept_terms": True},
    )
    assert accepted.status_code == 200
    assert accepted.json() == {
        "mfa_required": False,
        "company_selection_required": False,
        "me": None,
    }
    assert (await anonymous.get("/api/v1/auth/me")).status_code == 401  # a link alone is no login
    me = (await other.get("/api/v1/auth/me")).json()
    assert len(me["companies"]) == 2

    switched = await other.post(
        "/api/v1/auth/switch-company", json={"company_id": me["companies"][0]["company_id"]}
    )
    assert switched.status_code == 200
    assert switched.json()["active_company_id"] == me["companies"][0]["company_id"]
    user_id = switched.json()["user"]["id"]
    switched_events = await world.sql(
        "select company_id from audit_events where action='auth.company.switched' and actor_user_id=:u",
        u=uuid.UUID(user_id),
    )
    assert [str(r[0]) for r in switched_events] == [me["companies"][0]["company_id"]]
    stranger = await other.post(
        "/api/v1/auth/switch-company", json={"company_id": str(uuid.uuid4())}
    )
    assert stranger.status_code == 404


async def test_new_terms_must_be_accepted(world: World) -> None:
    await signed_up(world)
    await world.sql(
        "insert into terms_versions (version, published_at, url) "
        "values ('2027-01', now() + interval '1 second', '/legal/terms')"
    )
    me = (await world.client.get("/api/v1/auth/me")).json()
    assert (me["terms_acceptance_required"], me["terms_version"]) == (True, "2027-01")
    stale = await world.client.post("/api/v1/auth/accept-terms", json={"version": "2026-11-draft"})
    assert stale.status_code == 409
    assert (
        await world.client.post("/api/v1/auth/accept-terms", json={"version": "2027-01"})
    ).status_code == 204
    assert (await world.client.get("/api/v1/auth/me")).json()["terms_acceptance_required"] is False


# --- the documented contract ------------------------------------------------------------------------------


async def test_every_auth_endpoint_is_documented_with_its_response_schema(world: World) -> None:
    spec = (await world.client.get("/api/v1/openapi.json")).json()
    expected = {
        ("post", "/auth/signup", "202"),
        ("post", "/auth/verify-email", "200"),
        ("post", "/auth/resend-verification", "202"),
        ("post", "/auth/login", "200"),
        ("post", "/auth/logout", "204"),
        ("get", "/auth/me", "200"),
        ("post", "/auth/forgot-password", "202"),
        ("post", "/auth/reset-password", "204"),
        ("post", "/auth/change-password", "200"),
        ("post", "/auth/mfa/setup", "200"),
        ("post", "/auth/mfa/verify", "200"),
        ("post", "/auth/mfa/challenge", "200"),
        ("post", "/auth/mfa/disable", "204"),
        ("post", "/auth/mfa/recovery-codes", "200"),
        ("post", "/auth/step-up", "200"),
        ("post", "/auth/accept-terms", "204"),
        ("get", "/auth/invitations/{token}", "200"),
        ("post", "/auth/invitations/{token}/accept", "200"),
        ("post", "/auth/switch-company", "200"),
    }
    for method, path, status in expected:
        operation = spec["paths"][path][method]
        assert status in operation["responses"], (method, path)
        if status != "204":
            schema = operation["responses"][status]["content"]["application/json"]["schema"]
            assert schema, (method, path)


async def test_authentication_events_have_context_and_no_credentials(world: World) -> None:
    await signed_up(world)
    browser = world.new_browser()
    browser.headers["X-Request-ID"] = "security-audit-test"
    browser.headers["User-Agent"] = "audit-test-browser"
    await browser.post(
        "/api/v1/auth/login", json={"email": "unknown@example.com", "password": PASSWORD}
    )
    await browser.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "wrong"})
    await browser.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
    )
    await browser.post("/api/v1/auth/step-up", json={"password": "wrong"})
    await browser.post("/api/v1/auth/step-up", json={"password": PASSWORD})
    secret = (await browser.post("/api/v1/auth/mfa/setup")).json()["secret"]
    codes = (await browser.post("/api/v1/auth/mfa/verify", json={"code": totp(secret)})).json()[
        "recovery_codes"
    ]
    await browser.post("/api/v1/auth/step-up", json={"code": codes[0]})
    regenerated = await browser.post("/api/v1/auth/mfa/recovery-codes")
    assert regenerated.status_code == 200
    await browser.post("/api/v1/auth/logout")
    events = await world.sql(
        "select action, actor_user_id, company_id, ip, user_agent, request_id, before, after from audit_events where request_id='security-audit-test' order by created_at, id"
    )
    actions = [r[0] for r in events]
    assert actions == [
        "auth.login.failed",
        "auth.login.failed",
        "auth.login.succeeded",
        "auth.step_up.failed",
        "auth.step_up.succeeded",
        "auth.mfa.enabled",
        "auth.recovery_code.used",
        "auth.step_up.succeeded",
        "auth.recovery_codes.regenerated",
        "auth.logout",
    ]
    assert all(r[1] is None and r[2] is None for r in events[:2])
    assert all(r[1] is not None and r[2] is not None for r in events[2:])
    assert all(str(r[3]) == "127.0.0.1" and r[4] == "audit-test-browser" for r in events)
    serialized = str(events)
    for sensitive in [
        PASSWORD,
        secret,
        *codes,
        *regenerated.json()["recovery_codes"],
        "unknown@example.com",
    ]:
        assert sensitive not in serialized


async def test_reset_audit_commits_with_password_and_invalid_links_add_no_event(
    world: World,
) -> None:
    await signed_up(world)
    await world.client.post("/api/v1/auth/forgot-password", json={"email": "ada@example.com"})
    token = world.mail.token("reset_password", "ada@example.com")
    for candidate, expected in [("bad", 410), (token, 204), (token, 410)]:
        response = await world.client.post(
            "/api/v1/auth/reset-password", json={"token": candidate, "new_password": NEW_PASSWORD}
        )
        assert response.status_code == expected
    user = (await world.sql("select id from users"))[0][0]
    events = await world.sql(
        "select company_id, actor_user_id, after from audit_events where action='auth.password.reset' and actor_user_id=:u",
        u=user,
    )
    assert [tuple(row) for row in events] == [(None, user, None)]


async def test_failed_reset_transaction_keeps_password_and_reset_link(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.auth import accounts

    await signed_up(world)
    await world.client.post("/api/v1/auth/forgot-password", json={"email": "ada@example.com"})
    token = world.mail.token("reset_password", "ada@example.com")
    before = (await world.sql("select password_hash from users"))[0][0]

    async def unavailable(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("audit unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(accounts, "security_event", unavailable)
        failed = await world.client.post(
            "/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
        )
        assert failed.status_code == 500
    assert (await world.sql("select password_hash from users"))[0][0] == before
    assert (await world.sql("select used_at from email_tokens where purpose='reset'"))[0][0] is None
    assert (
        await world.client.post(
            "/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
        )
    ).status_code == 204


async def test_invitation_reclaims_an_unverified_account(world: World) -> None:
    await signed_up(world)
    stranger = world.new_browser()
    assert (
        await stranger.post(
            "/api/v1/auth/signup", json=signup_body("sam@example.com", company_name="Stranger")
        )
    ).status_code == 201
    token = await _invite(world, "sam@example.com")
    browser = world.new_browser()
    details = (await browser.get(f"/api/v1/auth/invitations/{token}")).json()
    assert details["has_account"] is False
    body = {"first_name": "Sam", "last_name": "Jones", "accept_terms": True}
    missing = await browser.post(f"/api/v1/auth/invitations/{token}/accept", json=body)
    assert missing.status_code == 422
    accepted = await browser.post(
        f"/api/v1/auth/invitations/{token}/accept", json={**body, "password": NEW_PASSWORD}
    )
    assert accepted.status_code == 200
    assert (await stranger.get("/api/v1/auth/me")).status_code == 401
    login = world.new_browser()
    old = await login.post(
        "/api/v1/auth/login", json={"email": "sam@example.com", "password": PASSWORD}
    )
    assert old.status_code == 401
    new = await login.post(
        "/api/v1/auth/login", json={"email": "sam@example.com", "password": NEW_PASSWORD}
    )
    assert new.status_code == 200
