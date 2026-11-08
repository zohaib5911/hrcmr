"""Who is calling an endpoint: the session cookie, and what it stands for."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from sqlalchemy import select

from app.core.client_ip import client_ip_of
from app.core.errors import AppError, ForbiddenError
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
    """The visitor's address; forwarded headers count only from a trusted proxy (core/client_ip)."""
    return client_ip_of(request)


def user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def unauthenticated() -> AppError:
    return AppError("UNAUTHENTICATED", "Sign in to continue.", status_code=401)


# --- the session cookie ------------------------------------------------------------------------


def set_session_cookie(
    response: Response,
    settings: Settings,
    token: str,
    expires_at: datetime,
    *,
    name: str | None = None,
) -> None:
    """Sets the tenant session cookie, or the platform one when ``name`` is given (T17.1)."""
    deployed = settings.app_env.is_deployed
    response.set_cookie(
        name or settings.session_cookie_name,
        token,
        expires=expires_at,
        path="/",
        domain=f".{settings.domain}" if deployed else None,
        secure=deployed,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(
    response: Response, settings: Settings, *, name: str | None = None
) -> None:
    deployed = settings.app_env.is_deployed
    response.delete_cookie(
        name or settings.session_cookie_name,
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


async def _caller(
    request: Request, db: GlobalDb, auth: AuthContainer, *, platform: bool = False
) -> Caller:
    """The caller for the tenant cookie, or for the platform cookie when ``platform`` is set.

    The token kind must match the cookie: a platform session is refused on the tenant routes and a
    tenant session on the platform routes, whichever cookie carries it (T17.1)."""
    name = (
        auth.settings.platform_session_cookie_name
        if platform
        else auth.settings.session_cookie_name
    )
    token = request.cookies.get(name)
    data = await auth.sessions.get(token)
    if token is None or data is None or data.platform is not platform:
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


async def platform_caller(request: Request, db: GlobalDb, auth: Auth) -> Caller:
    """A platform session (T17.1), from the platform cookie only.

    A tenant session is never accepted here. A person signed in on the tenant cookie but without a
    platform session gets 403 FORBIDDEN (as a non-admin always has); no session at all gets 401."""
    try:
        return await _caller(request, db, auth, platform=True)
    except AppError as error:
        if error.code != "UNAUTHENTICATED":
            raise
        tenant = await auth.sessions.get(request.cookies.get(auth.settings.session_cookie_name))
        if tenant is not None and not tenant.platform:
            raise ForbiddenError(
                "Platform admin access is needed for that page. Start a platform session first."
            ) from error
        raise


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
