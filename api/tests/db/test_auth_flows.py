"""T2.3, the authentication tests from plan 4.7: lockout, session rotation, CSRF rejection, MFA
required by policy, step-up enforcement and invitation expiry, against a real database and Redis."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI, Response
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.core.csrf import CsrfMiddleware
from app.core.errors import AppError
from app.core.totp import generate_secret, totp
from app.db.session import GlobalSession
from app.modules.auth.accounts import TokenInvalidError, consume_email_token, issue_email_token
from app.modules.auth.invitations import (
    InvitationInvalidError,
    accept_invitation,
    create_invitation,
)
from app.modules.auth.passwords import hash_password
from app.modules.auth.policy import (
    MfaRequiredError,
    MfaState,
    mfa_state,
    require_mfa_satisfied,
)
from app.modules.auth.service import (
    AuthService,
    InvalidCredentialsError,
    InvalidMfaCodeError,
    LoginOutcome,
    RateLimitedError,
    lock_seconds,
)
from app.modules.auth.sessions import (
    ABSOLUTE_TIMEOUT,
    IDLE_TIMEOUT,
    SessionData,
    SessionStore,
    StepUpRequiredError,
    require_step_up,
)
from app.modules.auth.tokens import hash_token
from app.modules.identity.models import Session, User
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL

PASSWORD = "a long, unusual passphrase 42"
EMAIL = "person@example.com"
START = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


class Notes:
    def __init__(self) -> None:
        self.locked: list[str] = []
        self.new_devices: list[str] = []

    async def account_locked(
        self, user_id: uuid.UUID, email: str, first_name: str, retry_after: int
    ) -> None:
        self.locked.append(email)

    async def new_device_login(
        self,
        user_id: uuid.UUID,
        email: str,
        first_name: str,
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        self.new_devices.append(f"{ip}|{user_agent}")


@pytest.fixture(autouse=True)
def _keys() -> Iterator[None]:
    """The encrypted MFA secret needs a key ring, as it has in a running API."""
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    yield
    set_keyring(None)


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    client = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
async def engine(database: DatabaseUnderTest) -> AsyncIterator[AsyncEngine]:
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.begin() as connection:
        await connection.execute(text("truncate users cascade"))
        await connection.execute(
            text(
                "insert into users (email, first_name, last_name, password_hash, is_active) "
                "values (:e, 'P', 'Q', :h, true)"
            ),
            {"e": EMAIL, "h": hash_password(PASSWORD)},
        )
    await owner.dispose()
    app_engine = engine_for(database.app_url, poolclass=NullPool)
    yield app_engine
    await app_engine.dispose()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def notes() -> Notes:
    return Notes()


@pytest.fixture
def sessions(redis: Redis, clock: Clock) -> SessionStore:
    return SessionStore(redis, clock=clock)


@pytest.fixture
def auth(redis: Redis, sessions: SessionStore, notes: Notes) -> AuthService:
    return AuthService(redis=redis, sessions=sessions, recovery_key=os.urandom(32), notifier=notes)


async def _login(
    engine: AsyncEngine,
    auth: AuthService,
    *,
    email: str = EMAIL,
    password: str = PASSWORD,
    ip: str = "203.0.113.7",
    agent: str = "Firefox",
) -> LoginOutcome:
    async with GlobalSession(engine) as db:
        outcome = await auth.login(db, email=email, password=password, ip=ip, user_agent=agent)
        await db.commit()
        return outcome


# --- lockout -------------------------------------------------------------------------------------


def test_the_lock_grows_with_each_failure() -> None:
    assert [lock_seconds(n) for n in range(1, 11)] == [0, 0, 0, 0, 60, 180, 540, 1620, 3600, 3600]


async def test_five_wrong_passwords_lock_the_address_even_for_the_right_one(
    engine: AsyncEngine, auth: AuthService, notes: Notes
) -> None:
    for attempt in range(5):
        with pytest.raises(InvalidCredentialsError):
            await _login(engine, auth, password="wrong", ip=f"203.0.113.{attempt}")
    assert notes.locked == [EMAIL]  # the owner of the account is told

    with pytest.raises(RateLimitedError) as locked:
        await _login(engine, auth, ip="203.0.113.99")  # the correct password
    assert 0 < locked.value.retry_after <= 60


async def test_an_address_with_no_account_locks_and_answers_exactly_the_same_way(
    engine: AsyncEngine, auth: AuthService, notes: Notes
) -> None:
    unknown = "nobody@example.com"
    errors = []
    for attempt in range(5):
        with pytest.raises(InvalidCredentialsError) as caught:
            await _login(engine, auth, email=unknown, password="x", ip=f"198.51.100.{attempt}")
        errors.append((caught.value.code, caught.value.message, caught.value.status_code))
    with pytest.raises(InvalidCredentialsError) as known:
        await _login(engine, auth, password="wrong", ip="198.51.100.50")
    assert errors[0] == (known.value.code, known.value.message, known.value.status_code)
    with pytest.raises(RateLimitedError):  # locked, with no account behind it
        await _login(engine, auth, email=unknown, password="x", ip="198.51.100.60")
    assert notes.locked == []  # and nobody was e-mailed


async def test_a_good_sign_in_clears_the_count(engine: AsyncEngine, auth: AuthService) -> None:
    for attempt in range(3):
        with pytest.raises(InvalidCredentialsError):
            await _login(engine, auth, password="wrong", ip=f"203.0.113.{attempt}")
    assert (await _login(engine, auth, ip="203.0.113.40")).mfa_challenge is False
    for attempt in range(3):  # three more would be six in a row if the count had been kept
        with pytest.raises(InvalidCredentialsError):
            await _login(engine, auth, password="wrong", ip=f"203.0.113.{50 + attempt}")


async def test_too_many_failures_from_one_address_are_refused(
    engine: AsyncEngine, auth: AuthService
) -> None:
    emails = [f"user{n}@example.com" for n in range(20)]
    for email in emails:
        with pytest.raises(InvalidCredentialsError):
            await _login(engine, auth, email=email, password="x", ip="192.0.2.1")
    with pytest.raises(RateLimitedError):  # even the right password, from that address
        await _login(engine, auth, ip="192.0.2.1")
    assert (await _login(engine, auth, ip="192.0.2.2")).mfa_challenge is False


async def test_thirty_colleagues_behind_one_office_address_all_sign_in(
    database: DatabaseUnderTest, engine: AsyncEngine, auth: AuthService
) -> None:
    """Audit finding 2: right passwords never use up the per-address limit."""
    owner = engine_for(database.owner_url, poolclass=NullPool)
    digest = hash_password(PASSWORD)
    async with owner.begin() as connection:
        for n in range(30):
            await connection.execute(
                text(
                    "insert into users (email, first_name, last_name, password_hash, is_active) "
                    "values (:e, 'P', 'Q', :h, true)"
                ),
                {"e": f"colleague{n}@example.com", "h": digest},
            )
    await owner.dispose()
    for n in range(30):
        outcome = await _login(engine, auth, email=f"colleague{n}@example.com", ip="192.0.2.9")
        assert outcome.mfa_challenge is False


# --- sessions ------------------------------------------------------------------------------------


async def test_signing_in_rotating_and_signing_out_change_the_token_each_time(
    engine: AsyncEngine, auth: AuthService, sessions: SessionStore
) -> None:
    first = await _login(engine, auth)
    assert await sessions.get(first.token) is not None
    async with GlobalSession(engine) as db:
        token2, data2 = await sessions.rotate(db, first.token, first.session)
        await db.commit()
    assert token2 != first.token
    assert await sessions.get(first.token) is None  # the old one stops working at once
    assert (await sessions.get(token2)) is not None
    assert data2.expires_at == first.session.expires_at  # rotating does not extend the 14 days

    async with GlobalSession(engine) as db:
        await sessions.revoke(db, token2, data2)
        await db.commit()
        rows = (await db.execute(select(Session))).scalars().all()
    assert await sessions.get(token2) is None
    assert all(row.revoked_at is not None for row in rows)
    assert all(hash_token(first.token) != row.token_hash or row.revoked_at for row in rows)


async def test_revoked_session_cannot_be_refreshed_or_rotated(
    engine: AsyncEngine,
    auth: AuthService,
    sessions: SessionStore,
    redis: Redis,
    clock: Clock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signed_in = await _login(engine, auth, ip="203.0.113.50")
    reading = asyncio.Event()
    resume = asyncio.Event()
    get = redis.get

    async def pause(key: str) -> bytes | str | None:
        value = await get(key)
        reading.set()
        await resume.wait()
        return value

    monkeypatch.setattr(redis, "get", pause)
    async with asyncio.TaskGroup() as group:
        pending = group.create_task(sessions.get(signed_in.token))
        await reading.wait()
        async with GlobalSession(engine) as db:
            await sessions.revoke(db, signed_in.token)
            await db.commit()
        resume.set()
    assert pending.result() is None
    clock.advance(minutes=6)
    with pytest.raises(AppError, match="Sign in"):
        await sessions.mark_step_up(signed_in.token, signed_in.session)
    async with GlobalSession(engine) as db:
        with pytest.raises(AppError, match="Sign in"):
            await sessions.touch(db, signed_in.token, signed_in.session)
    async with GlobalSession(engine) as db:
        with pytest.raises(AppError, match="Sign in"):
            await sessions.rotate(db, signed_in.token, signed_in.session)
    assert await sessions.get(signed_in.token) is None


async def test_email_token_is_consumed_in_only_one_transaction(engine: AsyncEngine) -> None:
    async with GlobalSession(engine) as db:
        user_id = (await db.execute(select(User.id).where(User.email == EMAIL))).scalar_one()
        token = await issue_email_token(db, user_id, "reset", timedelta(minutes=5))
        await db.commit()

    async def redeem() -> bool:
        async with GlobalSession(engine) as db:
            try:
                await consume_email_token(db, token, "reset")
            except TokenInvalidError:
                return False
            await db.commit()
            return True

    assert sorted(await asyncio.gather(redeem(), redeem())) == [False, True]


async def test_the_database_keeps_only_a_hash_of_the_token(
    engine: AsyncEngine, auth: AuthService
) -> None:
    outcome = await _login(engine, auth)
    async with GlobalSession(engine) as db:
        stored = (await db.execute(select(Session.token_hash))).scalars().all()
    assert stored == [hash_token(outcome.token)]
    assert outcome.token not in stored


async def test_an_idle_session_ends_after_eight_hours_and_any_session_after_fourteen_days(
    engine: AsyncEngine, auth: AuthService, sessions: SessionStore, redis: Redis, clock: Clock
) -> None:
    outcome = await _login(engine, auth)
    ttl = await redis.ttl(f"sess:{hash_token(outcome.token)}")
    assert 0 < ttl <= IDLE_TIMEOUT.total_seconds()

    clock.advance(days=13, hours=20)  # active throughout: kept alive by use, but the end is fixed
    assert await sessions.get(outcome.token) is not None
    ttl = await redis.ttl(f"sess:{hash_token(outcome.token)}")
    assert ttl <= timedelta(hours=4).total_seconds() + 5  # only what is left of the 14 days

    clock.advance(days=1)
    assert await sessions.get(outcome.token) is None
    assert timedelta(days=14) == ABSOLUTE_TIMEOUT


async def test_signing_out_everywhere_ends_every_session(
    engine: AsyncEngine, auth: AuthService, sessions: SessionStore
) -> None:
    one = await _login(engine, auth, ip="203.0.113.1")
    two = await _login(engine, auth, ip="203.0.113.2")
    async with GlobalSession(engine) as db:
        count = await sessions.revoke_all(
            db, uuid.UUID(one.session.user_id), except_session_id=two.session.session_id
        )
        await db.commit()
    assert count == 1
    assert await sessions.get(one.token) is None
    assert await sessions.get(two.token) is not None


# --- two-step verification ------------------------------------------------------------------------


async def _enrol(engine: AsyncEngine, auth: AuthService) -> tuple[str, list[str]]:
    secret = generate_secret()
    async with GlobalSession(engine) as db:
        user = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one()
        codes = await auth.confirm_mfa_enrolment(user, secret, totp(secret, at=START.timestamp()))
        await db.commit()
    return secret, codes


@pytest.fixture(autouse=True)
def _freeze_totp(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.core.totp as totp_module

    real = totp_module.verify_totp
    monkeypatch.setattr(
        "app.modules.auth.service.verify_totp",
        lambda secret, code, **kw: real(secret, code, at=START.timestamp(), **kw),
    )


async def test_the_second_step_is_asked_for_and_a_code_works_once(
    engine: AsyncEngine, auth: AuthService, sessions: SessionStore
) -> None:
    secret, _ = await _enrol(engine, auth)
    outcome = await _login(engine, auth)
    assert outcome.mfa_challenge is True
    assert outcome.session.mfa_passed is False

    # The enrolment used this moment's code, so signing in needs the next one.
    code = totp(secret, at=START.timestamp() + 30)
    async with GlobalSession(engine) as db:
        with pytest.raises(InvalidMfaCodeError):
            await auth.complete_mfa(
                db,
                token=outcome.token,
                data=outcome.session,
                code="000000",
                ip=None,
                user_agent=None,
            )
        token, data = await auth.complete_mfa(
            db, token=outcome.token, data=outcome.session, code=code, ip=None, user_agent=None
        )
        await db.commit()
    assert data.mfa_passed is True
    assert token != outcome.token  # passing the second step issues a new token
    assert await sessions.get(outcome.token) is None

    second = await _login(engine, auth, ip="203.0.113.77")
    async with GlobalSession(engine) as db:
        with pytest.raises(InvalidMfaCodeError):  # the same code, seen again, is refused
            await auth.complete_mfa(
                db, token=second.token, data=second.session, code=code, ip=None, user_agent=None
            )


async def test_concurrent_recovery_code_use_is_accepted_once(
    engine: AsyncEngine, auth: AuthService
) -> None:
    _, codes = await _enrol(engine, auth)
    left = await _login(engine, auth, ip="203.0.113.10")
    right = await _login(engine, auth, ip="203.0.113.11")

    async def verify(outcome: LoginOutcome) -> bool:
        async with GlobalSession(engine) as db:
            await db.get(User, uuid.UUID(outcome.session.user_id))  # caller loads the user first
            try:
                await auth.complete_mfa(
                    db,
                    token=outcome.token,
                    data=outcome.session,
                    code=codes[0],
                    ip=None,
                    user_agent=None,
                )
            except InvalidMfaCodeError:
                return False
            await db.commit()
            return True

    assert sorted(await asyncio.gather(verify(left), verify(right))) == [False, True]


async def test_a_recovery_code_works_once(engine: AsyncEngine, auth: AuthService) -> None:
    _, codes = await _enrol(engine, auth)
    assert len(codes) == 10
    for attempt in range(2):
        outcome = await _login(engine, auth, ip=f"203.0.113.{10 + attempt}")
        async with GlobalSession(engine) as db:
            if attempt == 0:
                _, data = await auth.complete_mfa(
                    db,
                    token=outcome.token,
                    data=outcome.session,
                    code=codes[0],
                    ip=None,
                    user_agent=None,
                )
                assert data.mfa_passed
                await db.commit()
            else:
                with pytest.raises(InvalidMfaCodeError):
                    await auth.complete_mfa(
                        db,
                        token=outcome.token,
                        data=outcome.session,
                        code=codes[0],
                        ip=None,
                        user_agent=None,
                    )


@pytest.mark.parametrize(
    ("enrolled", "passed", "policy", "role", "platform_admin", "expected"),
    [
        (False, False, "optional", "company_admin", False, MfaState.NOT_REQUIRED),
        (False, False, "admins", "company_admin", False, MfaState.ENROL),
        (False, False, "admins", "employee", False, MfaState.NOT_REQUIRED),
        (False, False, "all", "employee", False, MfaState.ENROL),
        (False, False, "optional", None, True, MfaState.ENROL),  # platform admins: always
        (True, False, "optional", "employee", False, MfaState.CHALLENGE),  # set up: always asked
        (True, True, "all", "employee", False, MfaState.NOT_REQUIRED),
    ],
)
def test_mfa_is_required_by_company_policy_and_always_for_platform_admins(
    enrolled: bool,
    passed: bool,
    policy: str,
    role: str | None,
    platform_admin: bool,
    expected: MfaState,
) -> None:
    state = mfa_state(
        enrolled=enrolled, passed=passed, policy=policy, role=role, platform_admin=platform_admin
    )
    assert state is expected
    if expected is MfaState.NOT_REQUIRED:
        require_mfa_satisfied(state)
    else:
        with pytest.raises(MfaRequiredError):
            require_mfa_satisfied(state)


# --- step-up ----------------------------------------------------------------------------------------


async def test_step_up_is_required_then_lasts_ten_minutes(
    engine: AsyncEngine, auth: AuthService, clock: Clock
) -> None:
    outcome = await _login(engine, auth)
    with pytest.raises(StepUpRequiredError):
        require_step_up(outcome.session, now=clock())

    async with GlobalSession(engine) as db:
        with pytest.raises(InvalidCredentialsError):
            await auth.step_up(
                db, token=outcome.token, data=outcome.session, password="not my password"
            )
        data = await auth.step_up(db, token=outcome.token, data=outcome.session, password=PASSWORD)
    require_step_up(data, now=clock())  # fresh: allowed
    clock.advance(minutes=9)
    require_step_up(data, now=clock())
    clock.advance(minutes=2)
    with pytest.raises(StepUpRequiredError):
        require_step_up(data, now=clock())


async def test_rotating_the_session_drops_step_up(
    engine: AsyncEngine, auth: AuthService, sessions: SessionStore, clock: Clock
) -> None:
    outcome = await _login(engine, auth)
    async with GlobalSession(engine) as db:
        data = await auth.step_up(db, token=outcome.token, data=outcome.session, password=PASSWORD)
        _, rotated = await sessions.rotate(db, outcome.token, data)
    with pytest.raises(StepUpRequiredError):
        require_step_up(rotated, now=clock())


# --- sign-in alerts ---------------------------------------------------------------------------------


async def test_a_new_device_is_reported_but_the_first_sign_in_and_a_known_device_are_not(
    engine: AsyncEngine, auth: AuthService, notes: Notes
) -> None:
    await _login(engine, auth, ip="203.0.113.5", agent="Firefox")
    await _login(engine, auth, ip="203.0.113.9", agent="Firefox")  # same /24, same browser
    assert notes.new_devices == []
    await _login(engine, auth, ip="198.51.100.4", agent="Chrome")
    assert notes.new_devices == ["198.51.100.4|Chrome"]


# --- invitations ------------------------------------------------------------------------------------


async def test_an_invitation_works_once_and_expires_after_72_hours(engine: AsyncEngine) -> None:
    company = uuid.uuid4()
    owner_company = None
    async with GlobalSession(engine) as db:
        # a company row is needed for the foreign key; the app role may insert one
        await db.execute(
            text("insert into companies (id, name, slug) values (:i, 'C', 'c')"), {"i": company}
        )
        token, invitation = await create_invitation(
            db,
            company_id=company,
            email="new@example.com",
            role="employee",
            invited_by=None,
            now=START,
        )
        await db.commit()
    assert invitation.token_hash == hash_token(token)
    assert token not in invitation.token_hash
    assert invitation.expires_at == START + timedelta(hours=72)

    async with GlobalSession(engine) as db:
        accepted = await accept_invitation(db, token, now=START + timedelta(hours=71))
        await db.commit()
        assert accepted.accepted_at is not None
    async with GlobalSession(engine) as db:
        with pytest.raises(InvitationInvalidError):  # used up
            await accept_invitation(db, token, now=START + timedelta(hours=72))

    async with GlobalSession(engine) as db:
        late, _ = await create_invitation(
            db,
            company_id=company,
            email="late@example.com",
            role="employee",
            invited_by=owner_company,
            now=START,
        )
        await db.commit()
    async with GlobalSession(engine) as db:
        with pytest.raises(InvitationInvalidError):  # past 72 hours
            await accept_invitation(db, late, now=START + timedelta(hours=72, seconds=1))
        with pytest.raises(InvitationInvalidError):  # never existed
            await accept_invitation(db, "not-a-token", now=START)


# --- CSRF -------------------------------------------------------------------------------------------


CSRF_SECRET = "csrf-test-secret"


def _csrf_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CsrfMiddleware,
        secret=CSRF_SECRET,
        session_cookies=("brand_session", "brand_platform_session", "brand_support_session"),
        secure=False,
    )

    @app.get("/page")
    async def page() -> dict[str, str]:
        return {"ok": "yes"}

    @app.post("/sign-in")
    async def sign_in(response: Response) -> dict[str, str]:
        response.set_cookie("brand_session", "session-after-sign-in", httponly=True)
        return {"signed_in": "yes"}

    @app.post("/sign-out")
    async def sign_out(response: Response) -> dict[str, str]:
        response.delete_cookie("brand_session")
        return {"signed_out": "yes"}

    @app.post("/change")
    async def change() -> dict[str, str]:
        return {"changed": "yes"}

    @app.post("/api/v1/webhooks/stripe")
    async def webhook() -> dict[str, str]:
        return {"received": "yes"}

    return app


async def test_a_state_changing_request_needs_the_csrf_header_to_match_the_cookie() -> None:
    transport = httpx.ASGITransport(app=_csrf_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get("/page")
        cookie = first.cookies.get("csrf")
        assert cookie  # issued on the first response
        assert (
            "httponly" not in first.headers["set-cookie"].lower()
        )  # the page must be able to read it
        assert "samesite=lax" in first.headers["set-cookie"].lower()

        for headers in ({}, {"X-CSRF-Token": "wrong"}):
            refused = await client.post("/change", headers=headers)
            assert refused.status_code == 403
            assert refused.json()["error"]["code"] == "CSRF_INVALID"

        # a cookie sent from elsewhere with no matching header is also refused
        assert (await client.post("/change", headers={"X-CSRF-Token": ""})).status_code == 403

        allowed = await client.post("/change", headers={"X-CSRF-Token": cookie})
        assert allowed.status_code == 200
        assert (await client.get("/page")).status_code == 200  # reads never need it


def _sent(cookies: dict[str, str], token: str | None = None) -> dict[str, str]:
    """Exactly these cookies and this header, with no cookie jar in between."""
    headers = {"Cookie": "; ".join(f"{name}={value}" for name, value in cookies.items())}
    if token is not None:
        headers["X-CSRF-Token"] = token
    return headers


async def test_a_hand_made_csrf_pair_is_refused_and_the_refusal_carries_a_real_token() -> None:
    # C6.1.6: a cookie planted from a sibling subdomain (csrf=x + header x) no longer passes.
    transport = httpx.ASGITransport(app=_csrf_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        refused = await client.post("/change", headers=_sent({"csrf": "x"}, "x"))
        assert refused.status_code == 403
        assert refused.json()["error"]["code"] == "CSRF_INVALID"
        fresh = refused.cookies.get("csrf")
        assert fresh
        assert fresh != "x"
        retried = await client.post("/change", headers=_sent({"csrf": fresh}, fresh))
        assert retried.status_code == 200


async def test_a_csrf_token_belongs_to_one_session_and_is_renewed_when_the_session_changes() -> (
    None
):
    transport = httpx.ASGITransport(app=_csrf_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        anonymous = (await client.get("/page", headers=_sent({}))).cookies.get("csrf")
        assert anonymous

        # Signing in changes the session cookie, so the same response renews the token.
        signed_in = await client.post("/sign-in", headers=_sent({"csrf": anonymous}, anonymous))
        assert signed_in.status_code == 200
        session = signed_in.cookies.get("brand_session")
        renewed = signed_in.cookies.get("csrf")
        assert session == "session-after-sign-in"
        assert renewed
        assert renewed != anonymous
        mine = {"brand_session": session, "csrf": renewed}
        assert (await client.post("/change", headers=_sent(mine, renewed))).status_code == 200

        # The token minted before sign-in is refused with the new session cookie.
        stale = {"brand_session": session, "csrf": anonymous}
        assert (await client.post("/change", headers=_sent(stale, anonymous))).status_code == 403

        # A token minted for one session cookie is refused with another.
        theirs = {"brand_session": "someone-elses-session", "csrf": renewed}
        assert (await client.post("/change", headers=_sent(theirs, renewed))).status_code == 403

        # Signing out renews it again, for no session.
        out = await client.post("/sign-out", headers=_sent(mine, renewed))
        assert out.status_code == 200
        after = out.cookies.get("csrf")
        assert after
        assert after != renewed
        assert (
            await client.post("/change", headers=_sent({"csrf": after}, after))
        ).status_code == 200


async def test_a_post_with_no_cookie_at_all_is_refused_and_webhooks_are_exempt() -> None:
    transport = httpx.ASGITransport(app=_csrf_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (
            await client.post("/change", headers={"X-CSRF-Token": "anything"})
        ).status_code == 403
        assert (await client.post("/api/v1/webhooks/stripe")).status_code == 200


@pytest.mark.parametrize(
    "stored",
    [
        "not json",
        "[]",
        '{"user_id": "x"}',
        "missing-dates",
        "bad-date",
        "naive-date",
        "bad-step-up",
    ],
)
async def test_an_unreadable_session_record_signs_the_caller_out(
    engine: AsyncEngine, auth: AuthService, sessions: SessionStore, redis: Redis, stored: str
) -> None:
    """ISS-05: a record that cannot safely be read is a signed-out caller, not a 500."""
    outcome = await _login(engine, auth)
    key = f"sess:{hash_token(outcome.token)}"
    raw = await redis.get(key)
    assert raw is not None
    good = json.loads(raw)
    broken = {
        "missing-dates": json.dumps({k: v for k, v in good.items() if k != "expires_at"}),
        "bad-date": json.dumps(good | {"expires_at": "soon"}),
        "naive-date": json.dumps(good | {"expires_at": "2099-01-01T00:00:00"}),
        "bad-step-up": json.dumps(good | {"step_up_at": 5}),
    }.get(stored, stored)
    await redis.set(key, broken, keepttl=True)
    assert await sessions.get(outcome.token) is None
    assert await redis.exists(key) == 0  # invalidated

    await redis.set(key, broken)
    async with GlobalSession(engine) as db:
        with pytest.raises(AppError) as ended:
            await sessions.rotate(db, outcome.token, SessionData(**good))
    assert ended.value.status_code == 401


async def test_an_older_session_record_without_the_optional_fields_still_works(
    engine: AsyncEngine, auth: AuthService, sessions: SessionStore, redis: Redis
) -> None:
    outcome = await _login(engine, auth)
    key = f"sess:{hash_token(outcome.token)}"
    raw = await redis.get(key)
    assert raw is not None
    good = json.loads(raw)
    older = {k: v for k, v in good.items() if k not in ("db_seen_at", "platform", "support_id")}
    await redis.set(key, json.dumps(older | {"future_field": 1}), keepttl=True)
    data = await sessions.get(outcome.token)
    assert data is not None
    assert (data.session_id, data.db_seen_at, data.platform) == (good["session_id"], "", False)
    async with GlobalSession(engine) as db:
        touched = await sessions.touch(db, outcome.token, data)
        await db.commit()
    assert touched.db_seen_at != ""
