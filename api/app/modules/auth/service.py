"""Signing in (plan.md 4.2): the password check, lockout, two-step verification and step-up.

What it guarantees, and the tests that hold it to it (tests/test_auth_service.py):

* An unknown e-mail address, a wrong password and an account with no password yet all give the same
  answer and take about the same time, so the sign-in form cannot be used to find out who has an
  account.
* Five wrong passwords lock the address, and the lock grows each time (1 minute, 3, 9, 27, then an
  hour). The lock and the counters live in Redis, keyed by a hash of the address, so an address
  that does not exist locks exactly like one that does. A real account is also told, by e-mail.
* Signing in, passing the second step and switching company each issue a new session token.
* A code from the authenticator is accepted once: the same code cannot be replayed.
* Step-up (password or code, valid ten minutes) is recorded on the session.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from sqlalchemy import select

from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.rate_limit import (
    LOGIN_PER_ACCOUNT,
    LOGIN_PER_IP,
    RateLimiter,
    hashed,
)
from app.core.totp import (
    generate_recovery_codes,
    hash_recovery_code,
    normalise_recovery_code,
    verify_totp,
)
from app.modules.auth.passwords import (
    hash_password_async,
    needs_rehash,
    spend_verification_time_async,
    verify_password_async,
)
from app.modules.companies.models import Company
from app.modules.identity.models import Membership, User

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.session import GlobalSession
    from app.modules.auth.sessions import SessionData, SessionStore

logger = get_logger("app.auth")

LOCK_AFTER_FAILURES = 5
LOCK_BASE_SECONDS = 60
LOCK_MAX_SECONDS = 3600
_FAILS_TTL = 24 * 3600
_DEVICE_TTL = 90 * 24 * 3600
_TOTP_REPLAY_TTL = 120


class InvalidCredentialsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "INVALID_CREDENTIALS", "That email and password do not match.", status_code=401
        )


class RateLimitedError(AppError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(
            "RATE_LIMITED",
            "Too many attempts. Wait a little and try again.",
            status_code=429,
        )
        self.retry_after = max(retry_after, 1)


class InvalidMfaCodeError(AppError):
    def __init__(self) -> None:
        super().__init__("INVALID_MFA_CODE", "That code is not right. Try again.", status_code=401)


class AuthNotifier(Protocol):
    """Tells a person about something that happened to their account (``MailNotifier`` sends the
    e-mail). It must never raise: a failed notice cannot be allowed to fail a sign-in."""

    async def account_locked(
        self, user_id: uuid.UUID, email: str, first_name: str, retry_after: int
    ) -> None: ...

    async def new_device_login(
        self,
        user_id: uuid.UUID,
        email: str,
        first_name: str,
        ip: str | None,
        user_agent: str | None,
    ) -> None: ...


class SilentNotifier:
    async def account_locked(
        self, user_id: uuid.UUID, email: str, first_name: str, retry_after: int
    ) -> None:
        return None

    async def new_device_login(
        self,
        user_id: uuid.UUID,
        email: str,
        first_name: str,
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        return None


@dataclass(frozen=True)
class LoginOutcome:
    token: str
    session: SessionData
    #: The password was right but a code is still needed before the session is of any use.
    mfa_challenge: bool


def lock_seconds(failures: int) -> int:
    """How long an address is locked after this many failures in a row (0 below the threshold)."""
    if failures < LOCK_AFTER_FAILURES:
        return 0
    return int(min(LOCK_BASE_SECONDS * 3 ** (failures - LOCK_AFTER_FAILURES), LOCK_MAX_SECONDS))


def _device_id(ip: str | None, user_agent: str | None) -> str:
    # The /24 of an IPv4 address (or the first 48 bits of IPv6), so moving between nearby addresses
    # is not a "new device".
    parts = (ip or "").split(".")
    network = ".".join(parts[:3]) if len(parts) == 4 else (ip or "").rsplit(":", 5)[0]
    return hashlib.sha256(f"{network}|{user_agent or ''}".encode()).hexdigest()[:24]


class AuthService:
    def __init__(
        self,
        *,
        redis: Redis,
        sessions: SessionStore,
        recovery_key: bytes,
        notifier: AuthNotifier | None = None,
    ) -> None:
        self._redis = redis
        self._sessions = sessions
        self._limiter = RateLimiter(redis)
        self._recovery_key = recovery_key
        self._notifier = notifier or SilentNotifier()

    # --- sign-in -----------------------------------------------------------------------

    async def _check_limits(self, email: str, ip: str | None) -> None:
        for (name, limit, window), subject in (
            (LOGIN_PER_IP, ip or "unknown"),
            (LOGIN_PER_ACCOUNT, email),
        ):
            result = await self._limiter.hit(name, subject, limit=limit, window_seconds=window)
            if not result.allowed:
                raise RateLimitedError(result.retry_after)
        locked_for = await self._redis.ttl(f"login:lock:{hashed(email)}")
        if locked_for > 0:
            raise RateLimitedError(locked_for)

    async def _record_failure(self, email: str, user: User | None) -> None:
        key = hashed(email)
        failures = int(await self._redis.incr(f"login:fails:{key}"))
        await self._redis.expire(f"login:fails:{key}", _FAILS_TTL)
        seconds = lock_seconds(failures)
        if seconds:
            await self._redis.set(f"login:lock:{key}", failures, ex=seconds)
            if user is not None:
                user.failed_login_count = failures
                user.locked_until = datetime.now(UTC).replace(microsecond=0) + timedelta(
                    seconds=seconds
                )
                await self._notifier.account_locked(
                    user.id, str(user.email), user.first_name, seconds
                )

    async def failure_count(self, email: str) -> int:
        """Wrong passwords in a row for this address (whether or not it has an account)."""
        return int(await self._redis.get(f"login:fails:{hashed(email.strip().lower())}") or 0)

    async def clear_lockout(self, email: str) -> None:
        await self._clear_failures(email.strip().lower())

    async def _clear_failures(self, email: str) -> None:
        key = hashed(email)
        await self._redis.delete(f"login:fails:{key}", f"login:lock:{key}")

    async def login(
        self,
        db: GlobalSession,
        *,
        email: str,
        password: str,
        ip: str | None,
        user_agent: str | None,
    ) -> LoginOutcome:
        email = email.strip().lower()
        await self._check_limits(email, ip)

        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        usable = user is not None and user.is_active and user.password_hash is not None
        if usable and user is not None and user.password_hash is not None:
            valid = await verify_password_async(user.password_hash, password)
        else:
            await spend_verification_time_async()
            valid = False
        if not valid or user is None:
            await self._record_failure(email, user)
            raise InvalidCredentialsError

        await self._clear_failures(email)
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = datetime.now(UTC)
        if user.password_hash and needs_rehash(user.password_hash):
            user.password_hash = await hash_password_async(password)

        await self._alert_if_new_device(user, ip, user_agent)
        return await self.open_session(db, user, ip=ip, user_agent=user_agent)

    async def open_session(
        self, db: GlobalSession, user: User, *, ip: str | None, user_agent: str | None
    ) -> LoginOutcome:
        """Start a session for a person who has just proved who they are (password, e-mail link).

        With exactly one active company it becomes the active one; otherwise the person picks."""
        await db.act_as(user.id)
        rows = (
            (
                await db.execute(
                    select(Membership.company_id)
                    .join(Company, Company.id == Membership.company_id)
                    .where(
                        Membership.user_id == user.id,
                        Membership.status == "active",
                        Company.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )
        challenge = user.mfa_enabled
        token, data = await self._sessions.create(
            db,
            user_id=user.id,
            company_id=rows[0] if len(rows) == 1 else None,
            ip=ip,
            user_agent=user_agent,
            mfa_passed=not challenge,
        )
        return LoginOutcome(token=token, session=data, mfa_challenge=challenge)

    async def _alert_if_new_device(
        self, user: User, ip: str | None, user_agent: str | None
    ) -> None:
        key = f"devices:{user.id}"
        device = _device_id(ip, user_agent)
        known = int(await self._redis.exists(key))
        is_new = known and not await self._redis.sismember(key, device)
        await self._redis.sadd(key, device)
        await self._redis.expire(key, _DEVICE_TTL)
        if is_new:  # the very first sign-in has nothing to compare with, so it is not an alert
            await self._notifier.new_device_login(
                user.id, str(user.email), user.first_name, ip, user_agent
            )

    # --- second step -------------------------------------------------------------------

    async def _check_second_factor(self, user: User, code: str) -> bool:
        """True for an authenticator code (once only) or a recovery code (which is then used up)."""
        if user.mfa_secret:
            step = verify_totp(user.mfa_secret, code)
            if step is not None:
                fresh = await self._redis.set(
                    f"totp:used:{user.id}:{step}", 1, ex=_TOTP_REPLAY_TTL, nx=True
                )
                return bool(fresh)
        candidate = hash_recovery_code(code, self._recovery_key)
        for stored in user.recovery_codes_hash:
            if hmac.compare_digest(stored, candidate):
                user.recovery_codes_hash = [h for h in user.recovery_codes_hash if h != stored]
                return True
        return False

    async def _user(self, db: AsyncSession, data: SessionData) -> User:
        user = (
            await db.execute(
                select(User)
                .where(User.id == uuid.UUID(data.user_id))
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if user is None:
            raise InvalidCredentialsError
        return user

    async def complete_mfa(
        self,
        db: AsyncSession,
        *,
        token: str,
        data: SessionData,
        code: str,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[str, SessionData]:
        """Check the second step; if right, issue a new session token that has passed it."""
        user = await self._user(db, data)
        result = await self._limiter.hit("mfa-user", str(user.id), limit=5, window_seconds=300)
        if not result.allowed:
            raise RateLimitedError(result.retry_after)
        if not await self._check_second_factor(user, code):
            raise InvalidMfaCodeError
        return await self._sessions.rotate(
            db, token, data, mfa_passed=True, ip=ip, user_agent=user_agent
        )

    # --- step-up -----------------------------------------------------------------------

    async def step_up(
        self,
        db: AsyncSession,
        *,
        token: str,
        data: SessionData,
        password: str | None = None,
        code: str | None = None,
    ) -> SessionData:
        """Re-confirm the person with their password or a code. Valid for ten minutes."""
        user = await self._user(db, data)
        result = await self._limiter.hit("stepup-user", str(user.id), limit=5, window_seconds=300)
        if not result.allowed:
            raise RateLimitedError(result.retry_after)
        ok = False
        if password is not None and user.password_hash:
            ok = await verify_password_async(user.password_hash, password)
        elif code is not None:
            ok = await self._check_second_factor(user, code)
        if not ok:
            raise InvalidCredentialsError
        return await self._sessions.mark_step_up(token, data)

    # --- setting two-step verification up ----------------------------------------------

    async def confirm_mfa_enrolment(self, user: User, secret: str, code: str) -> list[str]:
        """Switch two-step verification on once the person proves their app has the secret.

        Returns the ten recovery codes, to be shown once; only their hashes are kept."""
        step = verify_totp(secret, code)
        if step is None:
            raise InvalidMfaCodeError
        # The code that proved the setup cannot also be used to sign in a moment later.
        await self._redis.set(f"totp:used:{user.id}:{step}", 1, ex=_TOTP_REPLAY_TTL, nx=True)
        codes = generate_recovery_codes()
        user.mfa_secret = secret
        user.mfa_enabled = True
        user.recovery_codes_hash = [hash_recovery_code(c, self._recovery_key) for c in codes]
        return codes

    def regenerate_recovery_codes(self, user: User) -> list[str]:
        """Replace all ten codes (the old ones stop working). Shown once, stored only as hashes."""
        codes = generate_recovery_codes()
        user.recovery_codes_hash = [hash_recovery_code(c, self._recovery_key) for c in codes]
        return codes

    @staticmethod
    def disable_mfa(user: User) -> None:
        user.mfa_enabled = False
        user.mfa_secret = None
        user.recovery_codes_hash = []

    def recovery_codes_left(self, user: User) -> int:
        return len(user.recovery_codes_hash)

    @staticmethod
    def looks_like_recovery_code(code: str) -> bool:
        return len(normalise_recovery_code(code)) == 10
