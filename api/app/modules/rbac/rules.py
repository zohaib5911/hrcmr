"""The rules about roles themselves (plan.md 7.3)."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.core.errors import AppError, ConflictError, ForbiddenError
from app.core.rbac_matrix import Role, has_permission
from app.modules.companies.models import Company
from app.modules.identity.models import Membership

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def forbid_self_approval(
    actor_employee_id: uuid.UUID | None, subject_employee_id: uuid.UUID
) -> None:
    """No one approves their own leave or timesheet, whatever role they hold."""
    if actor_employee_id is not None and actor_employee_id == subject_employee_id:
        raise AppError("SELF_APPROVAL", "You cannot approve your own request.", status_code=403)


def check_can_invite(actor_role: str, invited_role: str) -> None:
    """HR Admins invite everyone except Company Admins; only a Company Admin invites one."""
    if not has_permission(actor_role, "rbac.user.invite"):
        raise ForbiddenError
    if invited_role == Role.COMPANY_ADMIN and actor_role != Role.COMPANY_ADMIN:
        raise ForbiddenError("Only a Company Admin can invite another Company Admin.")


def check_can_change_role(actor_role: str, *, current_role: str, new_role: str) -> None:
    """Changing a role needs ``rbac.role.assign``, and the Company Admin role can only be given or
    taken away by a Company Admin."""
    if not has_permission(actor_role, "rbac.role.assign"):
        raise ForbiddenError
    touches_admin = Role.COMPANY_ADMIN in (current_role, new_role)
    if touches_admin and actor_role != Role.COMPANY_ADMIN:
        raise ForbiddenError("Only a Company Admin can give or remove the Company Admin role.")


class LastCompanyAdminError(ConflictError):
    def __init__(self) -> None:
        super().__init__("A company must always have at least one active Company Admin.")


async def ensure_company_keeps_an_admin(
    db: AsyncSession,
    company_id: uuid.UUID,
    membership_id: uuid.UUID,
    *,
    new_role: str | None = None,
    new_status: str | None = None,
    removing: bool = False,
) -> None:
    """Refuse a change that would leave the company with no active Company Admin.

    Call it before demoting, suspending or removing a membership. ``db`` is a tenant session."""
    await db.execute(select(Company.id).where(Company.id == company_id).with_for_update())
    membership = (
        await db.execute(
            select(Membership)
            .where(Membership.id == membership_id, Membership.company_id == company_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if membership is None:
        return
    is_active_admin = membership.role == Role.COMPANY_ADMIN and membership.status == "active"
    stays_admin = (
        not removing
        and (new_role or membership.role) == Role.COMPANY_ADMIN
        and (new_status or membership.status) == "active"
    )
    if not is_active_admin or stays_admin:
        return
    others = (
        await db.execute(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.company_id == company_id,
                Membership.role == Role.COMPANY_ADMIN,
                Membership.status == "active",
                Membership.id != membership_id,
            )
        )
    ).scalar_one()
    if others == 0:
        raise LastCompanyAdminError
