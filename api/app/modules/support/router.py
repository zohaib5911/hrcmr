"""Support mode (T17.3, plan 8.18): a platform admin opens a company in the tenant app.

* ``POST /platform/companies/{id}/impersonate`` (reason + ticket reference) sets the support cookie:
  for 30 minutes the admin's tenant requests are that company's, read-only.
* ``POST /platform/impersonation/{id}/writes`` turns changes on (owner level, on their own session,
  with ``confirm: true``) or off again (any platform admin).
* ``POST /platform/impersonation/{id}/end`` ends it from the admin side; ``DELETE
  /auth/support-session`` ends the caller's own from the tenant banner.

The company's audit trail records each step, with the reason and the ticket reference.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from app.core.errors import AppError, ForbiddenError
from app.db.session import GlobalDb  # noqa: TC001
from app.modules.audit.service import AuditContext
from app.modules.auth.deps import (
    Auth,
    clear_session_cookie,
    client_ip,
    set_session_cookie,
    user_agent,
)
from app.modules.identity.models import PlatformAdmin
from app.modules.rbac.platform import PlatformAccess, require_platform
from app.modules.support import service
from app.modules.support.models import ImpersonationSession
from app.modules.support.schemas import SupportSessionOut, SupportStartIn, SupportWritesIn

router = APIRouter(tags=["support-mode"])
Support = Annotated[PlatformAccess, Depends(require_platform("platform.impersonate"))]


@router.post(
    "/platform/companies/{company_id}/impersonate",
    status_code=201,
    response_model=SupportSessionOut,
    summary="Start support mode on a company (read-only, 30 minutes)",
)
async def start_support(
    company_id: uuid.UUID,
    body: SupportStartIn,
    request: Request,
    response: Response,
    access: Support,
    auth: Auth,
) -> SupportSessionOut:
    token, row, company = await service.start(
        access.db,
        auth.sessions,
        access.audit_context,
        company_id=company_id,
        admin_id=access.caller.user_id,
        reason=body.reason.strip(),
        ticket_ref=body.ticket_ref,
        ip=client_ip(request),
        user_agent=user_agent(request),
    )
    await access.db.commit()
    set_session_cookie(
        response,
        auth.settings,
        token,
        row.expires_at,
        name=auth.settings.support_session_cookie_name,
    )
    return service.out(row, company.name)


@router.post(
    "/platform/impersonation/{support_id}/writes",
    response_model=SupportSessionOut,
    summary="Turn changes on (owner level, confirmed) or off in a support session",
)
async def set_support_writes(
    support_id: uuid.UUID, body: SupportWritesIn, access: Support
) -> SupportSessionOut:
    row = await service.row_or_404(access.db, support_id)
    if body.enabled:
        level = (
            await access.db.execute(
                select(PlatformAdmin.level).where(PlatformAdmin.user_id == access.caller.user_id)
            )
        ).scalar_one_or_none()
        if level != "owner":
            raise ForbiddenError("Only an owner-level admin can turn on changes in support mode.")
        if row.started_by != access.caller.user_id:
            raise ForbiddenError("Changes can be turned on only in your own support session.")
        if not body.confirm:
            raise AppError(
                "CONFIRMATION_REQUIRED",
                "Confirm that support mode may make changes to this company.",
                status_code=422,
                field="confirm",
            )
    await service.set_writes(
        access.db,
        access.audit_context,
        row,
        admin_id=access.caller.user_id,
        enabled=body.enabled,
    )
    await access.db.commit()
    return service.out(row, await service.company_name(access.db, row.company_id))


@router.post(
    "/platform/impersonation/{support_id}/end",
    response_model=SupportSessionOut,
    summary="End a support session",
)
async def end_support(
    support_id: uuid.UUID, response: Response, access: Support, auth: Auth
) -> SupportSessionOut:
    row = await service.row_or_404(access.db, support_id)
    await service.end(
        access.db, auth.sessions, access.audit_context, row, admin_id=access.caller.user_id
    )
    await access.db.commit()
    if row.started_by == access.caller.user_id:
        clear_session_cookie(
            response, auth.settings, name=auth.settings.support_session_cookie_name
        )
    return service.out(row, await service.company_name(access.db, row.company_id))


@router.delete(
    "/auth/support-session",
    status_code=204,
    summary="Leave support mode (the support cookie's own session; the tenant session is kept)",
)
async def leave_support(request: Request, db: GlobalDb, auth: Auth) -> Response:
    """Always clears the support cookie. Ends the session behind it when it is still live, so the
    banner's button works even after the 30 minutes are up."""
    response = Response(status_code=204)
    clear_session_cookie(response, auth.settings, name=auth.settings.support_session_cookie_name)
    token = request.cookies.get(auth.settings.support_session_cookie_name)
    data = await auth.sessions.get(token)
    if token is None or data is None or data.support_id is None:
        return response
    user_id = uuid.UUID(data.user_id)
    await db.act_as(user_id)
    row = (
        await db.execute(
            select(ImpersonationSession).where(
                ImpersonationSession.id == uuid.UUID(data.support_id),
                ImpersonationSession.started_by == user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None or not service.is_live(row, service.now()):
        await auth.sessions.revoke(db, token, data)
        await db.commit()
        return response
    context = AuditContext(
        company_id=None,
        actor_user_id=user_id,
        actor_type="platform_admin",
        ip=client_ip(request),
        user_agent=user_agent(request),
        request_id=str(getattr(request.state, "request_id", "")) or None,
    )
    await service.end(db, auth.sessions, context, row, admin_id=user_id)
    await auth.sessions.revoke(db, token, data)
    await db.commit()
    return response
