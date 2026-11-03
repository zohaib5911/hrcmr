"""Separate platform permission guard; tenant roles never grant platform access."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable  # noqa: TC003
from dataclasses import dataclass

from fastapi import Request  # noqa: TC002
from sqlalchemy import select

from app.core.errors import AppError, ForbiddenError
from app.core.rbac_matrix import PLATFORM_PERMISSIONS
from app.db.session import GlobalDb, GlobalSession  # noqa: TC001
from app.modules.audit.service import AuditContext
from app.modules.auth.deps import Caller, SignedIn, client_ip, state_for, user_agent
from app.modules.auth.policy import require_mfa_satisfied
from app.modules.identity.models import PlatformAdmin, TermsAcceptance
from app.modules.rbac.deps import PERMISSION_ATTRIBUTE


@dataclass
class PlatformAccess:
    db: GlobalSession
    caller: Caller
    audit_context: AuditContext


def require_platform(permission: str) -> Callable[..., AsyncIterator[PlatformAccess]]:
    if permission not in PLATFORM_PERMISSIONS:
        raise ValueError(f"unknown platform permission {permission!r}")
    # Other platform actions get their level-specific policies in Phase 17.
    if permission != "platform.content.write":
        raise ValueError(f"platform policy is not implemented for {permission!r}")

    async def dependency(
        request: Request, caller: SignedIn, db: GlobalDb
    ) -> AsyncIterator[PlatformAccess]:
        admin = (
            await db.execute(
                select(PlatformAdmin.id).where(PlatformAdmin.user_id == caller.user_id)
            )
        ).first()
        if admin is None:
            raise ForbiddenError
        if caller.user.email_verified_at is None:
            raise AppError(
                "EMAIL_NOT_VERIFIED", "Confirm your email address to continue.", status_code=403
            )
        require_mfa_satisfied(state_for(caller, policy="all", role=None, platform_admin=True))
        from app.modules.auth.accounts import current_terms

        terms = await current_terms(db)
        accepted = (
            await db.execute(
                select(TermsAcceptance.id).where(
                    TermsAcceptance.user_id == caller.user_id,
                    TermsAcceptance.version == terms.version,
                )
            )
        ).first()
        if accepted is None:
            raise AppError(
                "TERMS_ACCEPTANCE_REQUIRED", "Accept the new terms to continue.", status_code=403
            )
        await db.act_as(caller.user_id)
        yield PlatformAccess(
            db=db,
            caller=caller,
            audit_context=AuditContext(
                company_id=None,
                actor_user_id=caller.user_id,
                actor_type="platform_admin",
                ip=client_ip(request),
                user_agent=user_agent(request),
                request_id=str(getattr(request.state, "request_id", "")) or None,
            ),
        )

    setattr(dependency, PERMISSION_ATTRIBUTE, permission)
    return dependency
