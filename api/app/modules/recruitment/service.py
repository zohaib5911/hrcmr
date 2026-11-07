"""Requisition rules: who may open one, what a cancelled requisition allows, and the audit trail."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from sqlalchemy import select

from app.core.errors import AppError, NotFoundError
from app.modules.companies.models import Department
from app.modules.identity.models import User
from app.modules.recruitment.models import Requisition
from app.modules.recruitment.schemas import BudgetPer, RequisitionOut, RequisitionStatus

if TYPE_CHECKING:
    from app.db.session import TenantSession

# Where a requisition may move from. A cancelled requisition moves nowhere.
NEXT_FROM: dict[RequisitionStatus, frozenset[RequisitionStatus]] = {
    "draft": frozenset({"open", "on_hold", "filled", "cancelled"}),
    "open": frozenset({"on_hold", "filled", "cancelled"}),
    "on_hold": frozenset({"open", "filled", "cancelled"}),
    "filled": frozenset({"cancelled", "on_hold"}),
    "cancelled": frozenset(),
}


def now() -> datetime:
    return datetime.now(UTC)


async def requisition(db: TenantSession, ident: uuid.UUID, *, lock: bool = False) -> Requisition:
    query = select(Requisition).where(Requisition.id == ident)
    if lock:
        query = query.with_for_update()
    row = (await db.execute(query)).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


async def department_ok(db: TenantSession, department_id: uuid.UUID | None) -> None:
    if department_id is None:
        return
    found = (
        await db.execute(
            select(Department.id).where(
                Department.id == department_id, Department.archived_at.is_(None)
            )
        )
    ).first()
    if found is None:
        raise AppError(
            "VALIDATION_ERROR",
            "Choose a current department from this company.",
            status_code=422,
            field="department_id",
        )


async def change_status(
    db: TenantSession,
    row: Requisition,
    target: RequisitionStatus,
    actor: uuid.UUID,
    *,
    approver: bool,
) -> bool:
    """Move a requisition to ``target``; returns False when it already has that status."""
    current = cast("RequisitionStatus", row.status)
    if current == target:
        return False
    if current == "cancelled":
        raise AppError(
            "REQUISITION_CANCELLED",
            "A cancelled requisition cannot change. Create a new one.",
            status_code=409,
        )
    if target not in NEXT_FROM[current]:
        raise AppError(
            "REQUISITION_STATUS_INVALID",
            f"A {current.replace('_', ' ')} requisition cannot become {target.replace('_', ' ')}.",
            status_code=409,
        )
    if target == "open":
        if not approver:
            raise AppError(
                "REQUISITION_APPROVAL_REQUIRED",
                "Only someone allowed to approve requisitions can open one.",
                status_code=403,
            )
        row.approved_by, row.approved_at = actor, now()
    row.status = target
    return True


async def approver_name(db: TenantSession, row: Requisition) -> str | None:
    if row.approved_by is None:
        return None
    user = (await db.execute(select(User).where(User.id == row.approved_by))).scalar_one_or_none()
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


async def out(db: TenantSession, row: Requisition) -> RequisitionOut:
    department = (
        (
            await db.execute(select(Department.name).where(Department.id == row.department_id))
        ).scalar_one_or_none()
        if row.department_id
        else None
    )
    return RequisitionOut(
        id=row.id,
        job_title=row.job_title,
        department_id=row.department_id,
        department=department,
        headcount=row.headcount,
        grade=row.grade,
        budget_from=row.budget_from,
        budget_to=row.budget_to,
        budget_per=cast("BudgetPer | None", row.budget_per),
        justification=row.justification,
        status=cast("RequisitionStatus", row.status),
        approved_at=row.approved_at,
        approved_by_name=await approver_name(db, row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
