"""Server-side sessions (plan.md 4.2).

The browser holds a random 256-bit token in an HttpOnly cookie. The server keeps only its SHA-256
hash: in Redis, which every request reads and which expires an idle session by itself, and in
Postgres, which keeps the record for the audit trail (who signed in, from where, when it ended).

* Idle timeout 8 hours (sliding), absolute timeout 14 days.
* The token changes whenever the person's standing changes: signing in, passing MFA, switching
  company. The old token stops working at once, so a token stolen or planted before is useless.
* Step-up: a recent password or authenticator check, valid for 10 minutes, recorded on the session.

A session is found, changed and ended only through this class, with a ``GlobalSession`` (the
``sessions`` table is read before any company is known).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.core.errors import AppError
from app.modules.auth.tokens import hash_token, new_token
from app.modules.identity.models import Session, User

if TYPE_CHECKING:
    from collections.abc import Callable

    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

IDLE_TIMEOUT = timedelta(hours=8)
ABSOLUTE_TIMEOUT = timedelta(days=14)
STEP_UP_WINDOW = timedelta(minutes=10)
_DB_TOUCH_EVERY = timedelta(minutes=5)
_KEY = "sess:"
# Modify only the current value, never recreate a key removed by revocation and never overwrite
# a concurrent privilege update with an old request's snapshot. Preserve the existing expiry.
_PATCH = """
local raw = redis.call('GET', KEYS[1])
if not raw then return false end
local data = cjson.decode(raw)
data[ARGV[1]] = cjson.decode(ARGV[2])
local changed = cjson.encode(data)
redis.call('SET', KEYS[1], changed, 'XX', 'KEEPTTL')
return changed
"""


def _ended() -> AppError:
    return AppError("UNAUTHENTICATED", "Sign in to continue.", status_code=401)


def utcnow() -> datetime:
    return datetime.now(UTC)


def _instant(value: object) -> datetime | None:
    """A stored timestamp, or None when it is not an ISO date-time with a time zone."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _is_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class SessionData:
    session_id: str
    user_id: str
    company_id: str | None
    created_at: str
    expires_at: str  # the absolute limit
    mfa_passed_at: str | None = None
    step_up_at: str | None = None
    db_seen_at: str = ""
    # A platform session (T17.1) is issued only by POST /auth/platform-session, to a platform
    # admin who has passed MFA. Only the platform cookie carries it, and only the platform routes
    # accept it.
    platform: bool = False
    # A support-mode session (T17.3) names its ``impersonation_sessions`` row. Only the support
    # cookie carries it; the row says whether it is still live and whether writes are on.
    support_id: str | None = None

    @classmethod
    def parse(cls, raw: str | bytes) -> SessionData | None:
        """The stored session, or None when it cannot safely be read (ISS-05). Older records
        without the optional fields still read; unknown fields are ignored."""
        try:
            stored = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(stored, dict):
            return None
        if not (_is_uuid(stored.get("session_id")) and _is_uuid(stored.get("user_id"))):
            return None
        company = stored.get("company_id")
        if company is not None and not _is_uuid(company):
            return None
        if _instant(stored.get("created_at")) is None or _instant(stored.get("expires_at")) is None:
            return None
        for name in ("mfa_passed_at", "step_up_at"):
            value = stored.get(name)
            if value is not None and _instant(value) is None:
                return None
        seen = stored.get("db_seen_at", "")
        if seen and _instant(seen) is None:
            return None
        platform = stored.get("platform", False)
        support = stored.get("support_id")
        if not isinstance(platform, bool) or not (support is None or isinstance(support, str)):
            return None
        return cls(
            session_id=stored["session_id"],
            user_id=stored["user_id"],
            company_id=company,
            created_at=stored["created_at"],
            expires_at=stored["expires_at"],
            mfa_passed_at=stored.get("mfa_passed_at"),
            step_up_at=stored.get("step_up_at"),
            db_seen_at=seen or "",
            platform=platform,
            support_id=support,
        )

    def _when(self, value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None

    @property
    def absolute_expiry(self) -> datetime:
        return datetime.fromisoformat(self.expires_at)

    @property
    def mfa_passed(self) -> bool:
        return self.mfa_passed_at is not None

    def has_recent_step_up(self, now: datetime) -> bool:
        at = self._when(self.step_up_at)
        return at is not None and now - at <= STEP_UP_WINDOW


class StepUpRequiredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "STEP_UP_REQUIRED",
            "For your security, confirm your password or authenticator code to do this.",
            status_code=403,
        )


def require_step_up(data: SessionData, *, now: datetime | None = None) -> None:
    """Raise unless the person re-confirmed who they are in the last 10 minutes."""
    if not data.has_recent_step_up(now or utcnow()):
        raise StepUpRequiredError


class SessionStore:
    def __init__(self, redis: Redis, *, clock: Callable[[], datetime] = utcnow) -> None:
        self._redis = redis
        self._now = clock

    # --- helpers ------------------------------------------------------------------------------

    def _ttl(self, data: SessionData) -> int:
        remaining = (data.absolute_expiry - self._now()).total_seconds()
        return max(int(min(IDLE_TIMEOUT.total_seconds(), remaining)), 0)

    async def _save(self, token: str, data: SessionData) -> None:
        """Initial creation only. Refresh and privilege changes must not call this."""
        ttl = self._ttl(data)
        if ttl <= 0 or not await self._redis.set(
            _KEY + hash_token(token), json.dumps(asdict(data)), ex=ttl, nx=True
        ):
            raise _ended()

    async def _patch(self, token: str, field: str, value: str | None) -> SessionData:
        raw = await self._redis.eval(_PATCH, 1, _KEY + hash_token(token), field, json.dumps(value))
        data = SessionData.parse(raw) if raw else None
        if data is None:
            if raw:
                await self._redis.delete(_KEY + hash_token(token))
            raise _ended()
        return data

    @staticmethod
    async def _lock_user(db: AsyncSession, user_id: uuid.UUID) -> None:
        # Creation/rotation cannot insert a session outside a concurrent revoke-all sweep.
        await db.execute(select(User.id).where(User.id == user_id).with_for_update())

    # --- lifecycle ----------------------------------------------------------------------------

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        company_id: uuid.UUID | None,
        ip: str | None,
        user_agent: str | None,
        mfa_passed: bool,
        absolute_expiry: datetime | None = None,
        platform: bool = False,
        support_id: uuid.UUID | None = None,
        parent_token: str | None = None,
    ) -> tuple[str, SessionData]:
        """Start a session. Returns the token to put in the cookie, and what is known about it."""
        await self._lock_user(db, user_id)
        if parent_token is not None and await self.get(parent_token) is None:
            raise _ended()
        now = self._now()
        expires = absolute_expiry or now + ABSOLUTE_TIMEOUT
        token = new_token()
        row = Session(
            token_hash=hash_token(token),
            user_id=user_id,
            company_id=company_id,
            ip=ip,
            user_agent=(user_agent or "")[:400] or None,
            last_seen_at=now,
            expires_at=expires,
            mfa_passed_at=now if mfa_passed else None,
        )
        db.add(row)
        await db.flush()
        data = SessionData(
            session_id=str(row.id),
            user_id=str(user_id),
            company_id=str(company_id) if company_id else None,
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
            mfa_passed_at=now.isoformat() if mfa_passed else None,
            db_seen_at=now.isoformat(),
            platform=platform,
            support_id=str(support_id) if support_id else None,
        )
        await self._save(token, data)
        return token, data

    async def get(self, token: str | None) -> SessionData | None:
        """The session for a cookie, or None. Each successful look pushes the idle timeout back."""
        if not token:
            return None
        raw = await self._redis.get(_KEY + hash_token(token))
        if raw is None:
            return None
        data = SessionData.parse(raw)
        if data is None or data.absolute_expiry <= self._now():
            await self._redis.delete(_KEY + hash_token(token))
            return None
        # EXPIRE can only extend an existing key: a concurrent revoke remains final.
        ttl = self._ttl(data)
        if ttl <= 0 or not await self._redis.expire(_KEY + hash_token(token), ttl):
            return None
        return data

    async def touch(self, db: AsyncSession, token: str, data: SessionData) -> SessionData:
        """Record on the database row that the session is still in use, at most every 5 minutes."""
        now = self._now()
        seen = _instant(data.db_seen_at)  # an older record may not have it yet
        if seen is not None and now - seen < _DB_TOUCH_EVERY:
            return data
        await db.execute(
            update(Session).where(Session.id == uuid.UUID(data.session_id)).values(last_seen_at=now)
        )
        return await self._patch(token, "db_seen_at", now.isoformat())

    async def mark_step_up(self, token: str, data: SessionData) -> SessionData:
        return await self._patch(token, "step_up_at", self._now().isoformat())

    async def rotate(
        self,
        db: AsyncSession,
        token: str,
        data: SessionData,
        *,
        mfa_passed: bool | None = None,
        change_company: bool = False,
        company_id: uuid.UUID | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, SessionData]:
        """Replace the token (same person, same absolute deadline) and end the old one.

        The company stays as it was unless ``change_company`` is set, when ``company_id`` (which may
        be None) replaces it. Step-up does not carry over: a change of standing must be confirmed
        again.
        """
        await self._lock_user(db, uuid.UUID(data.user_id))
        # Only one rotation may consume a live token. A revoked/previously rotated token cannot
        # mint a new session from an already authenticated request's stale data.
        raw = await self._redis.getdel(_KEY + hash_token(token))
        if raw is None:
            raise _ended()
        current = SessionData.parse(raw)
        if current is None or current.absolute_expiry <= self._now():
            raise _ended()
        data = current
        await self.revoke(db, token, data)
        if change_company:
            new_company = company_id
        else:
            new_company = uuid.UUID(data.company_id) if data.company_id else None
        return await self.create(
            db,
            user_id=uuid.UUID(data.user_id),
            company_id=new_company,
            ip=ip,
            user_agent=user_agent,
            mfa_passed=data.mfa_passed if mfa_passed is None else mfa_passed,
            absolute_expiry=data.absolute_expiry,
            platform=data.platform,
        )

    async def revoke(self, db: AsyncSession, token: str, data: SessionData | None = None) -> None:
        await self._redis.delete(_KEY + hash_token(token))
        await db.execute(
            update(Session)
            .where(Session.token_hash == hash_token(token), Session.revoked_at.is_(None))
            .values(revoked_at=self._now())
        )

    async def revoke_id(self, db: AsyncSession, session_id: uuid.UUID) -> None:
        """End a session known only by its row (a support session ended from the admin side)."""
        token_hash = (
            await db.execute(
                select(Session.token_hash).where(
                    Session.id == session_id, Session.revoked_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if token_hash is None:
            return
        await self._redis.delete(_KEY + token_hash)
        await db.execute(
            update(Session).where(Session.id == session_id).values(revoked_at=self._now())
        )

    async def revoke_all(
        self, db: AsyncSession, user_id: uuid.UUID, *, except_session_id: str | None = None
    ) -> int:
        """Sign a person out everywhere (password change, "sign out of all devices")."""
        await self._lock_user(db, user_id)
        rows = (
            await db.execute(
                select(Session.id, Session.token_hash).where(
                    Session.user_id == user_id, Session.revoked_at.is_(None)
                )
            )
        ).all()
        ended = [(sid, token_hash) for sid, token_hash in rows if str(sid) != except_session_id]
        for _, token_hash in ended:
            await self._redis.delete(_KEY + token_hash)
        if ended:
            await db.execute(
                update(Session)
                .where(Session.id.in_([sid for sid, _ in ended]))
                .values(revoked_at=self._now())
            )
        return len(ended)
