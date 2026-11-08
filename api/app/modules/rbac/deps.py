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

import uuid  # noqa: TC003
from collections.abc import AsyncIterator, Callable  # noqa: TC003
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import Request  # noqa: TC002
from sqlalchemy import select

from app.core.errors import AppError, ForbiddenError
from app.core.rbac_matrix import PERMISSIONS, Scope, scope_for
from app.db.session import GlobalDb, TenantSession, get_engine
from app.modules.audit.service import AuditContext
from app.modules.audit.service import record as record_audit
from app.modules.auth.deps import (
    Auth,
    SignedIn,
    client_ip,
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
        return AuditContext(
            company_id=self.company_id,
            actor_user_id=self.caller.user_id,
            ip=self.ip,
            user_agent=self.user_agent,
            request_id=self.request_id,
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
        request: Request, caller: SignedIn, db: GlobalDb, auth: Auth
    ) -> AsyncIterator[Access]:
        company_id = caller.company_id
        if company_id is None:
            raise AppError("NO_COMPANY", "Choose a company to continue.", status_code=403)
        row = (
            await db.execute(
                select(Membership, Company)
                .join(Company, Company.id == Membership.company_id)
                .where(Membership.user_id == caller.user_id, Membership.company_id == company_id)
            )
        ).first()
        if row is None:
            raise ForbiddenError
        membership, company = row
        if membership.status != "active" or company.status != "active":
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
                role=membership.role,
            )
        )
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
        scope = scope_for(membership.role, permission)
        if scope is None:
            raise ForbiddenError
        if is_gated(request.method, permission) and not is_entitled(company):
            raise AppError(
                "PLAN_REQUIRED",
                "This needs a paid plan. Your data is safe and you can still view it.",
                status_code=402,
            )
        role, employee_id = membership.role, membership.employee_id
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
