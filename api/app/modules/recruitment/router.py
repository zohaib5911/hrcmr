"""Requisitions: company-wide list, create, edit, approval-gated status changes and the summary."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select

from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope, scope_for
from app.db.ids import uuid7
from app.modules.companies.compliance_documents import _today as company_today
from app.modules.files.models import File
from app.modules.rbac.deps import Access, require
from app.modules.recruitment import service
from app.modules.recruitment.models import Application, Candidate, Posting, Requisition
from app.modules.recruitment.schemas import (
    CandidateFile,
    CandidateIn,
    CandidateOut,
    CandidatePage,
    PostingIn,
    PostingOut,
    PostingPage,
    PostingStatus,
    PostingStatusIn,
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
PostingReads = Annotated[Access, Depends(require("recruitment.posting.read"))]
CandidateReads = Annotated[Access, Depends(require("recruitment.candidate.read"))]
CandidateWrites = Annotated[Access, Depends(require("recruitment.candidate.write"))]
PostingWrites = Annotated[Access, Depends(require("recruitment.posting.write"))]


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


def _posting_snapshot(row: Posting) -> dict[str, Any]:
    return {
        "title": row.title,
        "requisition_id": str(row.requisition_id),
        "visibility": row.visibility,
        "status": row.status,
        "vacancies": row.vacancies,
        "closes_on": row.closes_on.isoformat() if row.closes_on else None,
        "soc_code": row.soc_code,
        "visa_sponsorship": row.visa_sponsorship,
    }


def _apply_posting(row: Posting, body: PostingIn) -> None:
    row.requisition_id = body.requisition_id
    row.title = body.title
    row.visibility = body.visibility
    row.location_id = body.location_id
    row.job_code = body.job_code
    row.soc_code = body.soc_code
    row.vacancies = body.vacancies
    row.posted_on = body.posted_on
    row.closes_on = body.closes_on
    row.contact_email = body.contact_email
    row.contact_phone = body.contact_phone
    row.salary_from = body.salary_from
    row.salary_to = body.salary_to
    row.salary_per = body.salary_per
    row.weekly_hours = body.weekly_hours
    row.description = body.description
    row.visa_sponsorship = body.visa_sponsorship


async def _posting(access: Access, ident: uuid.UUID, *, lock: bool = False) -> Posting:
    query = select(Posting).where(Posting.id == ident)
    if lock:
        query = query.with_for_update()
    row = (await access.db.execute(query)).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


@router.get("/postings", response_model=PostingPage)
async def list_postings(
    request: Request,
    access: PostingReads,
    status: PostingStatus | None = None,
    search: Annotated[str, Query(max_length=200)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PostingPage:
    company_wide(access)
    query = select(Posting)
    if status is not None:
        query = query.where(Posting.status == status)
    if search.strip():
        query = query.where(
            func.lower(Posting.title).contains(search.strip().lower(), autoescape=True)
        )
    total = (
        await access.db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    rows = (
        (
            await access.db.execute(
                query.order_by(Posting.created_at.desc(), Posting.id).offset(offset).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    origin = request.app.state.settings.web_origin
    return PostingPage(
        items=[await service.posting_out(access.db, row, origin) for row in rows], total=total
    )


@router.post("/postings", status_code=201, response_model=PostingOut)
async def create_posting(request: Request, body: PostingIn, access: PostingWrites) -> PostingOut:
    company_wide(access)
    await service.open_requisition(access.db, body.requisition_id)
    await service.location_ok(access.db, body.location_id)
    row = Posting(
        id=uuid7(),
        company_id=access.company_id,
        slug=await service.unique_slug(access.db, body.title),
        status="draft",
    )
    _apply_posting(row, body)
    access.db.add(row)
    await access.db.flush()
    await access.db.refresh(row)
    await access.audit(
        "recruitment.posting.created",
        entity_type="posting",
        entity_id=row.id,
        after=_posting_snapshot(row),
    )
    await access.db.commit()
    return await service.posting_out(access.db, row, request.app.state.settings.web_origin)


@router.get("/postings/{posting_id}", response_model=PostingOut)
async def get_posting(request: Request, posting_id: uuid.UUID, access: PostingReads) -> PostingOut:
    company_wide(access)
    row = await _posting(access, posting_id)
    return await service.posting_out(access.db, row, request.app.state.settings.web_origin)


@router.patch("/postings/{posting_id}", response_model=PostingOut)
async def update_posting(
    request: Request, posting_id: uuid.UUID, body: PostingIn, access: PostingWrites
) -> PostingOut:
    company_wide(access)
    row = await _posting(access, posting_id, lock=True)
    if body.requisition_id != row.requisition_id:
        await service.open_requisition(access.db, body.requisition_id)
    await service.location_ok(access.db, body.location_id)
    before = _posting_snapshot(row)
    _apply_posting(row, body)
    await access.db.flush()
    await access.audit(
        "recruitment.posting.updated",
        entity_type="posting",
        entity_id=row.id,
        before=before,
        after=_posting_snapshot(row),
    )
    await access.db.commit()
    return await service.posting_out(access.db, row, request.app.state.settings.web_origin)


@router.patch("/postings/{posting_id}/status", response_model=PostingOut)
async def set_posting_status(
    request: Request, posting_id: uuid.UUID, body: PostingStatusIn, access: PostingWrites
) -> PostingOut:
    company_wide(access)
    row = await _posting(access, posting_id, lock=True)
    previous = row.status
    changed = await service.change_posting_status(access.db, row, body.status)
    if changed:
        await access.db.flush()
        await access.audit(
            "recruitment.posting.status_changed",
            entity_type="posting",
            entity_id=row.id,
            before={"status": previous},
            after={"status": row.status},
        )
    await access.db.commit()
    return await service.posting_out(access.db, row, request.app.state.settings.web_origin)


async def _candidate_row(access: Access, ident: uuid.UUID, *, lock: bool = False) -> Candidate:
    query = select(Candidate).where(Candidate.id == ident)
    if lock:
        query = query.with_for_update()
    row = (await access.db.execute(query)).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


def _candidate_snapshot(row: Candidate) -> dict[str, Any]:
    return {
        "first_name": row.first_name,
        "last_name": row.last_name,
        "email": row.email,
        "phone": row.phone,
        "source": row.source,
    }


def _apply_candidate(row: Candidate, body: CandidateIn) -> None:
    row.first_name = body.first_name
    row.last_name = body.last_name
    row.email = body.email
    row.phone = body.phone
    row.source = body.source


@router.get("/candidates", response_model=CandidatePage)
async def list_candidates(
    access: CandidateReads,
    search: Annotated[str, Query(max_length=200)] = "",
    include_archived: bool = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CandidatePage:
    company_wide(access)
    query = select(Candidate)
    if not include_archived:
        query = query.where(Candidate.archived_at.is_(None))
    if search.strip():
        term = search.strip().lower()
        query = query.where(
            func.lower(Candidate.first_name + " " + Candidate.last_name).contains(
                term, autoescape=True
            )
            | func.lower(func.coalesce(Candidate.email, "")).contains(term, autoescape=True)
        )
    total = (
        await access.db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    rows = (
        (
            await access.db.execute(
                query.order_by(Candidate.last_name, Candidate.first_name, Candidate.id)
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    today = await company_today(access)
    return CandidatePage(
        items=[await service.candidate_out(access.db, row, today) for row in rows], total=total
    )


@router.post("/candidates", status_code=201, response_model=CandidateOut)
async def create_candidate(body: CandidateIn, access: CandidateWrites) -> CandidateOut:
    company_wide(access)
    row = Candidate(id=uuid7(), company_id=access.company_id)
    _apply_candidate(row, body)
    access.db.add(row)
    await access.db.flush()
    await access.db.refresh(row)
    await access.audit(
        "candidate.created",
        entity_type="candidate",
        entity_id=row.id,
        after=_candidate_snapshot(row),
    )
    await access.db.commit()
    return await service.candidate_out(access.db, row, await company_today(access))


@router.get("/candidates/{candidate_id}", response_model=CandidateOut)
async def get_candidate(candidate_id: uuid.UUID, access: CandidateReads) -> CandidateOut:
    company_wide(access)
    row = await _candidate_row(access, candidate_id)
    return await service.candidate_out(access.db, row, await company_today(access))


@router.patch("/candidates/{candidate_id}", response_model=CandidateOut)
async def update_candidate(
    candidate_id: uuid.UUID, body: CandidateIn, access: CandidateWrites
) -> CandidateOut:
    company_wide(access)
    row = await _candidate_row(access, candidate_id, lock=True)
    before = _candidate_snapshot(row)
    _apply_candidate(row, body)
    await access.db.flush()
    await access.audit(
        "candidate.updated",
        entity_type="candidate",
        entity_id=row.id,
        before=before,
        after=_candidate_snapshot(row),
    )
    await access.db.commit()
    return await service.candidate_out(access.db, row, await company_today(access))


@router.delete("/candidates/{candidate_id}", status_code=204)
async def archive_candidate(candidate_id: uuid.UUID, access: CandidateWrites) -> Response:
    company_wide(access)
    row = await _candidate_row(access, candidate_id, lock=True)
    if row.archived_at is None:
        row.archived_at = service.now()
        await access.db.flush()
        await access.audit("candidate.archived", entity_type="candidate", entity_id=row.id)
    await access.db.commit()
    return Response(status_code=204)


@router.get("/candidates/{candidate_id}/documents", response_model=list[CandidateFile])
async def candidate_documents(
    candidate_id: uuid.UUID, access: CandidateReads
) -> list[CandidateFile]:
    company_wide(access)
    await _candidate_row(access, candidate_id)
    rows = (
        (
            await access.db.execute(
                select(File)
                .where(File.owner_type == "candidate", File.owner_id == candidate_id)
                .order_by(File.created_at.desc(), File.id)
            )
        )
        .scalars()
        .all()
    )
    return [
        CandidateFile(
            id=row.id,
            name=row.original_name,
            mime=row.mime,
            size=row.size,
            scan_status=row.scan_status,
            created_at=row.created_at,
        )
        for row in rows
    ]
