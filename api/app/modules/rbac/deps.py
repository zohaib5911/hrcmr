"""``require("permission")``: the one way an endpoint says who may call it (plan.md 4.4).

    @router.get("/employees/{id}")
    async def read_employee(
        id: UUID, access: Annotated[Access, Depends(require("employee.profile.read"))]
    ):
        if not await access.can_reach(id):
            raise NotFoundError()
        ...

The dependency does everything an endpoint needs before it starts, in one place so no endpoint can
forget a step: there is a live session; its second step is done (and, if the company's policy
demands it, set up); the e-mail address is verified; the current terms are accepted; the person
still belongs to an active company in an active membership; and their role holds the permission.
It then opens the company-scoped database session the endpoint works through, and says how far the
permission reaches (everyone, only reports, only the person's own record).
"""

from __future__ import annotations

import time
import uuid  # noqa: TC003
from collections.abc import AsyncIterator, Callable  # noqa: TC003
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import Request  # noqa: TC002
from sqlalchemy import exists, select, true

from app.core.errors import AppError, ForbiddenError
from app.core.rbac_matrix import PERMISSIONS, Scope, scope_for
from app.db.session import GlobalDb, TenantSession, get_engine
from app.modules.audit.service import AuditContext
from app.modules.audit.service import record as record_audit
from app.modules.auth.deps import (
    SAFE_METHODS,
    Auth,
    TenantCaller,
    client_ip,
    support_read_only,
    user_agent,
)
from app.modules.auth.policy import mfa_state, require_mfa_satisfied
from app.modules.billing.entitlements import is_entitled, is_gated
from app.modules.companies.models import Company
from app.modules.identity.models import Membership, TermsAcceptance
from app.modules.rbac.reports import Relation, ReportsGraph

if TYPE_CHECKING:
    from app.modules.auth.deps import Caller

PERMISSION_ATTRIBUTE = "rbac_permission"
# Support mode (T17.3) sees the company as its administrator does; changes still need writes on.
SUPPORT_ROLE = "company_admin"
# O6.1.5: every request used to read the current terms version and the person's acceptance of it.
# The version is kept per app process for a minute (new terms reach every request within 60 s; the
# account screens read it fresh). An acceptance, once seen, is remembered in Redis: it is never
# withdrawn, so only a "yes" is cached. Membership status and role are never cached.
TERMS_CACHE_SECONDS = 60.0
ACCEPTED_TTL_SECONDS = 30 * 24 * 3600


async def _terms_version(request: Request, db: GlobalDb) -> str:
    cached: tuple[float, str] | None = getattr(request.app.state, "terms_version_cache", None)
    now = time.monotonic()
    if cached is not None and now - cached[0] < TERMS_CACHE_SECONDS:
        return cached[1]
    from app.modules.auth.accounts import current_terms

    version = (await current_terms(db)).version
    request.app.state.terms_version_cache = (now, version)
    return version


def forget_terms_version(app: Any) -> None:
    """Called when terms are published: this process sees the new version at once."""
    app.state.terms_version_cache = None


def _accepted_key(user_id: uuid.UUID, version: str) -> str:
    return f"terms-accepted:{user_id}:{version}"


@dataclass
class Access:
    caller: Caller
    company_id: uuid.UUID
    role: str
    permission: str
    scope: Scope
    db: TenantSession
    employee_id: uuid.UUID | None  # the HR record this person is, if they have one
    reports: ReportsGraph
    ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None

    @property
    def audit_context(self) -> AuditContext:
        """In support mode the change is the platform admin's, marked with the support session."""
        support = self.caller.support
        return AuditContext(
            company_id=self.company_id,
            actor_user_id=self.caller.user_id,
            actor_type="platform_admin" if support else "user",
            ip=self.ip,
            user_agent=self.user_agent,
            request_id=self.request_id,
            impersonation_session_id=support.id if support else None,
        )

    async def audit(
        self,
        action: str,
        *,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        reason: str | None = None,
        summary: str | None = None,
    ) -> None:
        """Record what this request did, in the same transaction as the change itself."""
        await record_audit(
            self.db,
            self.audit_context,
            action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            reason=reason,
            summary=summary,
        )

    async def can_reach(self, employee_id: uuid.UUID, relation: Relation = "reporting") -> bool:
        """May this person use the permission on that employee's record?"""
        if self.scope is Scope.ALL:
            return True
        if self.employee_id is None:
            return False
        if self.scope is Scope.OWN:
            return employee_id == self.employee_id
        return await self.reports.is_report(self.employee_id, employee_id, relation)


def _known(permission: str) -> bool:
    return permission in PERMISSIONS or any(
        f"{permission}{suffix}" in PERMISSIONS for suffix in ("_own", "_reports")
    )


def require(permission: str) -> Callable[..., AsyncIterator[Access]]:
    """A dependency that admits only roles holding ``permission`` (or its ``_reports``/``_own``)."""
    if not _known(permission):
        raise ValueError(f"unknown permission {permission!r}")

    async def dependency(
        request: Request, caller: TenantCaller, db: GlobalDb, auth: Auth
    ) -> AsyncIterator[Access]:
        company_id = caller.company_id
        if company_id is None:
            raise AppError("NO_COMPANY", "Choose a company to continue.", status_code=403)
        version = await _terms_version(request, db)
        key = _accepted_key(caller.user_id, version)
        known_accepted = bool(await auth.redis.exists(key))
        # One statement: the membership and company, and (unless already known) the acceptance.
        accepted_column = (
            true()
            if known_accepted
            else exists().where(
                TermsAcceptance.user_id == caller.user_id, TermsAcceptance.version == version
            )
        ).label("accepted")
        if caller.support is not None:
            # Support mode (T17.3): no membership; the grant was checked in tenant_caller.
            if request.method not in SAFE_METHODS and not caller.support.write_enabled:
                raise support_read_only()
            found = (
                await db.execute(select(Company, accepted_column).where(Company.id == company_id))
            ).first()
            if found is None:
                raise ForbiddenError
            company, accepted = found
            role, status, employee_id = SUPPORT_ROLE, "active", None
        else:
            row = (
                await db.execute(
                    select(Membership, Company, accepted_column)
                    .join(Company, Company.id == Membership.company_id)
                    .where(
                        Membership.user_id == caller.user_id, Membership.company_id == company_id
                    )
                )
            ).first()
            if row is None:
                raise ForbiddenError
            membership, company, accepted = row
            role, status, employee_id = membership.role, membership.status, membership.employee_id
        if status != "active" or company.status != "active":
            raise AppError("ACCOUNT_SUSPENDED", "This account is not active.", status_code=403)
        if caller.user.email_verified_at is None:
            raise AppError(
                "EMAIL_NOT_VERIFIED", "Confirm your email address to continue.", status_code=403
            )
        require_mfa_satisfied(
            mfa_state(
                enrolled=caller.user.mfa_enabled,
                passed=caller.session.mfa_passed,
                policy=company.mfa_policy,
                role=role,
            )
        )
        if not accepted:
            raise AppError(
                "TERMS_ACCEPTANCE_REQUIRED", "Accept the new terms to continue.", status_code=403
            )
        if not known_accepted:
            await auth.redis.set(key, "1", ex=ACCEPTED_TTL_SECONDS)
        scope = scope_for(role, permission)
        if scope is None:
            raise ForbiddenError
        if is_gated(request.method, permission) and not is_entitled(company):
            raise AppError(
                "PLAN_REQUIRED",
                "This needs a paid plan. Your data is safe and you can still view it.",
                status_code=402,
            )
        await db.commit()  # free this connection before the endpoint takes its own

        async with TenantSession(
            get_engine(request), company_id=company_id, user_id=caller.user_id
        ) as tenant:
            yield Access(
                caller=caller,
                company_id=company_id,
                role=role,
                permission=permission,
                scope=scope,
                db=tenant,
                employee_id=employee_id,
                reports=ReportsGraph(tenant, company_id),
                ip=client_ip(request),
                user_agent=user_agent(request),
                request_id=str(getattr(request.state, "request_id", "")) or None,
            )

    setattr(dependency, PERMISSION_ATTRIBUTE, permission)
    return dependency
