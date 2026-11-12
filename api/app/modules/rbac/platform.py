"""Separate platform permission guard; tenant roles never grant platform access.

A platform admin reaches the admin routes only with a platform session (T17.1): a token that
POST /auth/platform-session issued into its own cookie, after MFA. The guard refuses a tenant
session, a session without MFA, and an address outside the optional ADMIN_IP_ALLOWLIST. Every
request it lets through is audited as ``platform.access`` (page views and actions alike)."""

from __future__ import annotations

import ipaddress
from collections.abc import AsyncIterator, Callable  # noqa: TC003
from dataclasses import dataclass

from fastapi import Request  # noqa: TC002
from sqlalchemy import select

from app.core.config import Settings  # noqa: TC001
from app.core.errors import AppError, ForbiddenError
from app.core.rbac_matrix import PLATFORM_PERMISSIONS
from app.db.session import GlobalDb, GlobalSession  # noqa: TC001
from app.modules.audit.service import AuditContext, record
from app.modules.auth.deps import Auth, Caller, platform_caller, state_for
from app.modules.auth.policy import require_mfa_satisfied
from app.modules.identity.models import PlatformAdmin, TermsAcceptance
from app.modules.rbac.deps import PERMISSION_ATTRIBUTE
from app.modules.rbac.visitor import platform_visitor


@dataclass
class PlatformAccess:
    db: GlobalSession
    caller: Caller
    audit_context: AuditContext


def ip_allowed(ip: str | None, allowlist: list[str]) -> bool:
    """True when there is no allowlist, or ``ip`` is one of its addresses or inside one of its
    networks. An entry that does not parse matches nothing, so a typo narrows access, not widens."""
    if not allowlist:
        return True
    if ip is None:
        return False
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in allowlist:
        try:
            if address in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def require_allowed_network(request: Request, settings: Settings) -> None:
    """Refuse a platform request from outside ADMIN_IP_ALLOWLIST (no-op when it is unset)."""
    ip, _ = platform_visitor(request, settings)
    if not ip_allowed(ip, settings.admin_ip_allowlist):
        raise ForbiddenError


def require_platform(permission: str) -> Callable[..., AsyncIterator[PlatformAccess]]:
    if permission not in PLATFORM_PERMISSIONS:
        raise ValueError(f"unknown platform permission {permission!r}")
    # Other platform actions get their level-specific policies in Phase 17. Publishing SOC rules
    # (T15.7) uses the same policy as the course editor: any platform admin, with MFA and terms.
    # Company and user administration (T17.2): any platform admin reads and changes them. Marking a
    # company for deletion is the one owner-only action, checked in its handler.
    if permission not in {
        "platform.content.write",
        "platform.rules.publish",
        "platform.companies.read",
        "platform.companies.write",
        "platform.impersonate",  # support mode (T17.3); writes on is owner-only, in its handler
        "platform.billing.refund",  # refunds (T17.4); owner only, checked in its handler
        "platform.jobs.run",  # re-run a failed job (T17.6); allow-listed jobs, with a reason
    }:
        raise ValueError(f"platform policy is not implemented for {permission!r}")

    async def dependency(
        request: Request, db: GlobalDb, auth: Auth
    ) -> AsyncIterator[PlatformAccess]:
        caller = await platform_caller(request, db, auth)
        require_allowed_network(request, auth.settings)
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
        ip, agent = platform_visitor(request, auth.settings)
        context = AuditContext(
            company_id=None,
            actor_user_id=caller.user_id,
            actor_type="platform_admin",
            ip=ip,
            user_agent=agent,
            request_id=str(getattr(request.state, "request_id", "")) or None,
        )
        # Committed here, before the handler, so a page view is kept even if the handler fails.
        await record(db, context, "platform.access", summary=f"{request.method} {request.url.path}")
        await db.commit()
        yield PlatformAccess(db=db, caller=caller, audit_context=context)

    setattr(dependency, PERMISSION_ATTRIBUTE, permission)
    return dependency
