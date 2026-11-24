"""The platform session (T17.1): a platform admin's step from a signed-in session into the admin
routes. POST issues the platform cookie after MFA; DELETE ends it. The tenant session is not
touched by either: a platform admin keeps both, and each works only on its own routes."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy import select

from app.core.errors import AppError, ForbiddenError
from app.db.session import GlobalDb  # noqa: TC001
from app.modules.audit.service import AuditContext, record
from app.modules.auth.deps import (
    Auth,
    SignedIn,
    clear_session_cookie,
    client_ip,
    platform_caller,
    set_session_cookie,
    state_for,
    user_agent,
)
from app.modules.auth.policy import require_mfa_satisfied
from app.modules.auth.sessions import require_step_up
from app.modules.identity.models import PlatformAdmin
from app.modules.rbac.platform import require_allowed_network

router = APIRouter(tags=["platform-session"])

# Shorter than a tenant session (14 days absolute): the admin tools are used in short bursts.
PLATFORM_SESSION_LIFETIME = timedelta(hours=8)


class PlatformSessionOut(BaseModel):
    expires_at: datetime


def _audit(request: Request, user_id: uuid.UUID) -> AuditContext:
    return AuditContext(
        company_id=None,
        actor_user_id=user_id,
        actor_type="platform_admin",
        ip=client_ip(request),
        user_agent=user_agent(request),
        request_id=str(getattr(request.state, "request_id", "")) or None,
    )


@router.post(
    "/auth/platform-session",
    status_code=201,
    response_model=PlatformSessionOut,
    summary="Start a platform session (platform admins, after MFA, allowed network)",
)
async def start_platform_session(
    request: Request, response: Response, caller: SignedIn, db: GlobalDb, auth: Auth
) -> PlatformSessionOut:
    require_allowed_network(request, auth.settings)
    admin = (
        await db.execute(select(PlatformAdmin.id).where(PlatformAdmin.user_id == caller.user_id))
    ).first()
    if admin is None:
        raise ForbiddenError
    if caller.user.email_verified_at is None:
        raise AppError(
            "EMAIL_NOT_VERIFIED", "Confirm your email address to continue.", status_code=403
        )
    # Mandatory MFA: a platform admin with no authenticator set up is refused (ENROL), and one
    # whose session has not passed the second step never reaches this line (signed_in_caller).
    require_mfa_satisfied(state_for(caller, policy="all", role=None, platform_admin=True))
    # A stolen tenant session must not open the admin site by itself: the person confirms their
    # password or authenticator code again, within the last 10 minutes (O6.1.7).
    require_step_up(caller.session)
    token, data = await auth.sessions.create(
        db,
        user_id=caller.user_id,
        company_id=None,
        ip=client_ip(request),
        user_agent=user_agent(request),
        mfa_passed=True,
        absolute_expiry=datetime.now(UTC) + PLATFORM_SESSION_LIFETIME,
        platform=True,
        parent_token=caller.token,
    )
    await record(db, _audit(request, caller.user_id), "platform.session.started")
    await db.commit()
    set_session_cookie(
        response,
        auth.settings,
        token,
        data.absolute_expiry,
        name=auth.settings.platform_session_cookie_name,
    )
    return PlatformSessionOut(expires_at=data.absolute_expiry)


@router.delete(
    "/auth/platform-session",
    status_code=204,
    summary="End the platform session (the tenant session is kept)",
)
async def end_platform_session(request: Request, db: GlobalDb, auth: Auth) -> Response:
    caller = await platform_caller(request, db, auth)
    await auth.sessions.revoke(db, caller.token, caller.session)
    await record(db, _audit(request, caller.user_id), "platform.session.ended")
    await db.commit()
    response = Response(status_code=204)
    clear_session_cookie(response, auth.settings, name=auth.settings.platform_session_cookie_name)
    return response
