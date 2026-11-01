"""Who is calling an endpoint: the session cookie, and what it stands for."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from sqlalchemy import select

from app.core.errors import AppError
from app.db.session import GlobalDb  # noqa: TC001  (FastAPI reads the annotation at run time)
from app.modules.auth.container import AuthContainer
from app.modules.auth.policy import MfaState, mfa_state, require_mfa_satisfied
from app.modules.identity.models import User

if TYPE_CHECKING:
    from datetime import datetime

    from fastapi import Response

    from app.core.config import Settings
    from app.modules.auth.sessions import SessionData


def container(request: Request) -> AuthContainer:
    value: AuthContainer = request.app.state.auth
    return value


Auth = Annotated[AuthContainer, Depends(container)]


def client_ip(request: Request) -> str | None:
    # Behind Cloudflare and Railway the real address is in these headers; Cloudflare's wins because
    # it is set by Cloudflare itself. Locally there is no proxy and the socket address is used.
    for header in ("cf-connecting-ip", "x-real-ip"):
        value = request.headers.get(header)
        if value:
            return value.strip()[:45]
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def unauthenticated() -> AppError:
    return AppError("UNAUTHENTICATED", "Sign in to continue.", status_code=401)


# --- the session cookie ------------------------------------------------------------------------


def set_session_cookie(
    response: Response, settings: Settings, token: str, expires_at: datetime
) -> None:
    deployed = settings.app_env.is_deployed
    response.set_cookie(
        settings.session_cookie_name,
        token,
        expires=expires_at,
        path="/",
        domain=f".{settings.domain}" if deployed else None,
        secure=deployed,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    deployed = settings.app_env.is_deployed
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        domain=f".{settings.domain}" if deployed else None,
        secure=deployed,
        httponly=True,
        samesite="lax",
    )


# --- who is calling -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Caller:
    token: str
    session: SessionData
    user: User

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def company_id(self) -> uuid.UUID | None:
        return uuid.UUID(self.session.company_id) if self.session.company_id else None


async def _caller(request: Request, db: GlobalDb, auth: AuthContainer) -> Caller:
    token = request.cookies.get(auth.settings.session_cookie_name)
    data = await auth.sessions.get(token)
    if token is None or data is None:
        raise unauthenticated()
    user = (
        await db.execute(select(User).where(User.id == uuid.UUID(data.user_id)))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise unauthenticated()
    await db.act_as(user.id)
    touched = await auth.sessions.touch(db, token, data)
    if touched.db_seen_at != data.db_seen_at:
        await (
            db.commit()
        )  # the "last seen" note is kept even when the request itself changes nothing
    return Caller(token=token, session=touched, user=user)


async def session_caller(request: Request, db: GlobalDb, auth: Auth) -> Caller:
    """Anyone with a live session, even one that still owes the second step."""
    return await _caller(request, db, auth)


async def signed_in_caller(request: Request, db: GlobalDb, auth: Auth) -> Caller:
    """A live session whose second step (if the person has one) has been passed."""
    caller = await _caller(request, db, auth)
    if caller.user.mfa_enabled and not caller.session.mfa_passed:
        require_mfa_satisfied(MfaState.CHALLENGE)
    return caller


SessionCaller = Annotated[Caller, Depends(session_caller)]
SignedIn = Annotated[Caller, Depends(signed_in_caller)]


def state_for(caller: Caller, *, policy: str, role: str | None, platform_admin: bool) -> MfaState:
    return mfa_state(
        enrolled=caller.user.mfa_enabled,
        passed=caller.session.mfa_passed,
        policy=policy,
        role=role,
        platform_admin=platform_admin,
    )
