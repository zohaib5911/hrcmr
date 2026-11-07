"""Requisitions: company-wide list, create, edit, approval-gated status changes and the summary."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.core.errors import AppError, ForbiddenError
from app.core.rbac_matrix import Scope, scope_for
from app.db.ids import uuid7
from app.modules.rbac.deps import Access, require
from app.modules.recruitment import service
from app.modules.recruitment.models import Application, Candidate, Posting, Requisition
from app.modules.recruitment.schemas import (
    RecruitmentSummary,
    RequisitionIn,
    RequisitionOut,
    RequisitionPage,
    RequisitionStatus,
    RequisitionStatusIn,
)

router = APIRouter(tags=["recruitment"])
Reads = Annotated[Access, Depends(require("recruitment.requisition.read"))]
Writes = Annotated[Access, Depends(require("recruitment.requisition.write"))]


def company_wide(access: Access) -> None:
    """Requisitions belong to the company; a person's own-only grant does not reach them."""
    if access.scope is not Scope.ALL:
        raise ForbiddenError


def _snapshot(row: Requisition) -> dict[str, Any]:
    return {
        "job_title": row.job_title,
        "department_id": str(row.department_id) if row.department_id else None,
        "headcount": row.headcount,
        "grade": row.grade,
        "budget_from": str(row.budget_from) if row.budget_from is not None else None,
        "budget_to": str(row.budget_to) if row.budget_to is not None else None,
        "budget_per": row.budget_per,
    }


@router.get("/requisitions", response_model=RequisitionPage)
async def list_requisitions(
    access: Reads,
    status: RequisitionStatus | None = None,
    search: Annotated[str, Query(max_length=200)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RequisitionPage:
    company_wide(access)
    query = select(Requisition)
    if status is not None:
        query = query.where(Requisition.status == status)
    if search.strip():
        query = query.where(
            func.lower(Requisition.job_title).contains(search.strip().lower(), autoescape=True)
        )
    total = (
        await access.db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    rows = (
        (
            await access.db.execute(
                query.order_by(Requisition.created_at.desc(), Requisition.id)
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return RequisitionPage(items=[await service.out(access.db, row) for row in rows], total=total)


@router.post("/requisitions", status_code=201, response_model=RequisitionOut)
async def create_requisition(body: RequisitionIn, access: Writes) -> RequisitionOut:
    company_wide(access)
    await service.department_ok(access.db, body.department_id)
    row = Requisition(
        id=uuid7(),
        company_id=access.company_id,
        job_title=body.job_title,
        department_id=body.department_id,
        headcount=body.headcount,
        grade=body.grade,
        budget_from=body.budget_from,
        budget_to=body.budget_to,
        budget_per=body.budget_per,
        justification=body.justification,
        status="draft",
    )
    access.db.add(row)
    await access.db.flush()
    await access.db.refresh(row)
    await access.audit(
        "recruitment.requisition.created",
        entity_type="requisition",
        entity_id=row.id,
        after=_snapshot(row),
    )
    await access.db.commit()
    return await service.out(access.db, row)


@router.get("/requisitions/{requisition_id}", response_model=RequisitionOut)
async def get_requisition(requisition_id: uuid.UUID, access: Reads) -> RequisitionOut:
    company_wide(access)
    return await service.out(access.db, await service.requisition(access.db, requisition_id))


@router.patch("/requisitions/{requisition_id}", response_model=RequisitionOut)
async def update_requisition(
    requisition_id: uuid.UUID, body: RequisitionIn, access: Writes
) -> RequisitionOut:
    company_wide(access)
    row = await service.requisition(access.db, requisition_id, lock=True)
    if row.status == "cancelled":
        raise AppError(
            "REQUISITION_CANCELLED",
            "A cancelled requisition cannot change. Create a new one.",
            status_code=409,
        )
    await service.department_ok(access.db, body.department_id)
    before = _snapshot(row)
    row.job_title = body.job_title
    row.department_id = body.department_id
    row.headcount = body.headcount
    row.grade = body.grade
    row.budget_from = body.budget_from
    row.budget_to = body.budget_to
    row.budget_per = body.budget_per
    row.justification = body.justification
    await access.db.flush()
    await access.audit(
        "recruitment.requisition.updated",
        entity_type="requisition",
        entity_id=row.id,
        before=before,
        after=_snapshot(row),
    )
    await access.db.commit()
    return await service.out(access.db, row)


@router.patch("/requisitions/{requisition_id}/status", response_model=RequisitionOut)
async def set_requisition_status(
    requisition_id: uuid.UUID, body: RequisitionStatusIn, access: Writes
) -> RequisitionOut:
    company_wide(access)
    row = await service.requisition(access.db, requisition_id, lock=True)
    previous = row.status
    may_approve = scope_for(access.role, "recruitment.requisition.approve") is not None
    changed = await service.change_status(
        access.db, row, body.status, access.caller.user_id, approver=may_approve
    )
    if changed:
        await access.db.flush()
        await access.audit(
            "recruitment.requisition.status_changed",
            entity_type="requisition",
            entity_id=row.id,
            before={"status": previous},
            after={"status": row.status},
        )
    await access.db.commit()
    return await service.out(access.db, row)


@router.get("/recruitment/summary", response_model=RecruitmentSummary)
async def recruitment_summary(access: Reads) -> RecruitmentSummary:
    company_wide(access)

    async def count(query: Any) -> int:
        return int(
            (
                await access.db.execute(select(func.count()).select_from(query.subquery()))
            ).scalar_one()
        )

    return RecruitmentSummary(
        open_requisitions=await count(select(Requisition.id).where(Requisition.status == "open")),
        requisitions=await count(select(Requisition.id).where(Requisition.status != "cancelled")),
        live_postings=await count(select(Posting.id).where(Posting.status == "open")),
        postings=await count(select(Posting.id).where(Posting.status != "closed")),
        candidates=await count(select(Candidate.id).where(Candidate.archived_at.is_(None))),
        applications_in_progress=await count(
            select(Application.id).where(
                Application.stage.not_in(("hired", "rejected", "withdrawn"))
            )
        ),
    )
