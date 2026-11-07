"""Requisition rules: who may open one, what a cancelled requisition allows, and the audit trail."""

from __future__ import annotations

import re
import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from sqlalchemy import and_, select

from app.core.errors import AppError, NotFoundError
from app.modules.companies.models import Company, Department, Location
from app.modules.identity.models import User
from app.modules.recruitment.models import Posting, Requisition
from app.modules.recruitment.schemas import (
    BudgetPer,
    PostingOut,
    PostingStatus,
    PostingVisibility,
    RequisitionOut,
    RequisitionStatus,
    VisaSponsorship,
)

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


# Where a posting may move from. Opening one also needs its requisition to be open.
POSTING_NEXT: dict[PostingStatus, frozenset[PostingStatus]] = {
    "draft": frozenset({"open", "closed"}),
    "open": frozenset({"closed"}),
    "closed": frozenset({"open"}),
}
_SLUG_GAPS = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    return _SLUG_GAPS.sub("-", title.lower()).strip("-")[:100] or "posting"


async def unique_slug(db: TenantSession, title: str, *, ignore: uuid.UUID | None = None) -> str:
    """The title as a URL part, numbered if another posting in this company already uses it."""
    base = slugify(title)
    candidate, number = base, 2
    while True:
        conditions = [Posting.slug == candidate]
        if ignore is not None:
            conditions.append(Posting.id != ignore)
        if (await db.execute(select(Posting.id).where(and_(*conditions)))).first() is None:
            return candidate
        candidate = f"{base}-{number}"
        number += 1


async def open_requisition(db: TenantSession, requisition_id: uuid.UUID) -> Requisition:
    """An open requisition in this company.

    Anything else, including another company's requisition, gets the same refusal.
    """
    row = (
        await db.execute(select(Requisition).where(Requisition.id == requisition_id))
    ).scalar_one_or_none()
    if row is None or row.status != "open":
        raise AppError(
            "POSTING_REQUISITION_NOT_OPEN",
            "Choose an open requisition. A role is advertised only once it is approved.",
            status_code=422,
            field="requisition_id",
        )
    return row


async def location_ok(db: TenantSession, location_id: uuid.UUID | None) -> None:
    if location_id is None:
        return
    found = (
        await db.execute(
            select(Location.id).where(Location.id == location_id, Location.archived_at.is_(None))
        )
    ).first()
    if found is None:
        raise AppError(
            "VALIDATION_ERROR",
            "Choose a current location from this company.",
            status_code=422,
            field="location_id",
        )


def public_link(company_slug: str, row: Posting, web_origin: str) -> str | None:
    """Only an external, open posting has a public page. Closing it removes the link."""
    if row.visibility != "external" or row.status != "open":
        return None
    return f"{web_origin.rstrip('/')}/careers/{company_slug}/{row.slug}"


async def change_posting_status(db: TenantSession, row: Posting, target: PostingStatus) -> bool:
    current = cast("PostingStatus", row.status)
    if current == target:
        return False
    if target not in POSTING_NEXT[current]:
        raise AppError(
            "POSTING_STATUS_INVALID",
            f"A {current} posting cannot become {target}.",
            status_code=409,
        )
    if target == "open":
        requisition_row = (
            await db.execute(select(Requisition).where(Requisition.id == row.requisition_id))
        ).scalar_one()
        if requisition_row.status != "open":
            raise AppError(
                "POSTING_REQUISITION_NOT_OPEN",
                "Open the requisition before opening its posting.",
                status_code=422,
            )
    row.status = target
    return True


async def posting_out(db: TenantSession, row: Posting, web_origin: str) -> PostingOut:
    requisition_title = (
        await db.execute(select(Requisition.job_title).where(Requisition.id == row.requisition_id))
    ).scalar_one()
    location = (
        (
            await db.execute(select(Location.name).where(Location.id == row.location_id))
        ).scalar_one_or_none()
        if row.location_id
        else None
    )
    company_slug = (
        await db.execute(select(Company.slug).where(Company.id == row.company_id))
    ).scalar_one()
    return PostingOut(
        id=row.id,
        requisition_id=row.requisition_id,
        requisition_title=requisition_title,
        title=row.title,
        slug=row.slug,
        visibility=cast("PostingVisibility", row.visibility),
        location_id=row.location_id,
        location=location,
        job_code=row.job_code,
        soc_code=row.soc_code,
        vacancies=row.vacancies,
        posted_on=row.posted_on,
        closes_on=row.closes_on,
        contact_email=row.contact_email,
        contact_phone=row.contact_phone,
        salary_from=row.salary_from,
        salary_to=row.salary_to,
        salary_per=cast("BudgetPer | None", row.salary_per),
        weekly_hours=row.weekly_hours,
        description=row.description,
        visa_sponsorship=cast("VisaSponsorship", row.visa_sponsorship),
        status=cast("PostingStatus", row.status),
        public_link=public_link(company_slug, row, web_origin),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
