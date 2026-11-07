"""Requisitions: company-wide list, create, edit, approval-gated status changes and the summary."""

from __future__ import annotations

import json
import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Annotated, Any, cast
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select

from app.core.crypto import encrypt
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope, scope_for
from app.db.ids import uuid7
from app.modules.companies.compliance_documents import _today as company_today
from app.modules.companies.models import Company
from app.modules.email.models import EmailOutbox
from app.modules.email.outbox import PAYLOAD_CONTEXT
from app.modules.email.templates import check
from app.modules.employees.models import Employee
from app.modules.files.models import File
from app.modules.rbac.deps import Access, require
from app.modules.recruitment import service
from app.modules.recruitment.applications import LABELS, STAGES, check_move
from app.modules.recruitment.ics import interview_ics
from app.modules.recruitment.models import (
    Application,
    Candidate,
    Interview,
    Posting,
    Requisition,
)
from app.modules.recruitment.schemas import (
    ApplicationIn,
    ApplicationOut,
    ApplicationPage,
    ApplicationStageIn,
    CandidateFile,
    CandidateIn,
    CandidateOut,
    CandidatePage,
    InterviewIn,
    InterviewOut,
    InterviewPatch,
    Pipeline,
    PipelineStage,
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
    Stage,
)
from app.modules.recruitment.service import MODE_LABELS

router = APIRouter(tags=["recruitment"])
Reads = Annotated[Access, Depends(require("recruitment.requisition.read"))]
Writes = Annotated[Access, Depends(require("recruitment.requisition.write"))]
PostingReads = Annotated[Access, Depends(require("recruitment.posting.read"))]
CandidateReads = Annotated[Access, Depends(require("recruitment.candidate.read"))]
ApplicationReads = Annotated[Access, Depends(require("recruitment.application.read"))]
ApplicationWrites = Annotated[Access, Depends(require("recruitment.application.write"))]
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


async def _application(access: Access, ident: uuid.UUID, *, lock: bool = False) -> Application:
    query = select(Application).where(Application.id == ident)
    if lock:
        query = query.with_for_update()
    row = (await access.db.execute(query)).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


@router.get("/applications", response_model=ApplicationPage)
async def list_applications(
    access: ApplicationReads,
    stage: Stage | None = None,
    posting_id: uuid.UUID | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApplicationPage:
    company_wide(access)
    query = select(Application)
    if stage is not None:
        query = query.where(Application.stage == stage)
    if posting_id is not None:
        query = query.where(Application.posting_id == posting_id)
    total = (
        await access.db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    rows = (
        (
            await access.db.execute(
                query.order_by(Application.created_at.desc(), Application.id)
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    today = await company_today(access)
    return ApplicationPage(
        items=[await service.application_out(access.db, row, today) for row in rows], total=total
    )


@router.post("/applications", status_code=201, response_model=ApplicationOut)
async def create_application(body: ApplicationIn, access: ApplicationWrites) -> ApplicationOut:
    company_wide(access)
    candidate = (
        await access.db.execute(
            select(Candidate.id).where(
                Candidate.id == body.candidate_id, Candidate.archived_at.is_(None)
            )
        )
    ).first()
    if candidate is None:
        raise AppError(
            "VALIDATION_ERROR",
            "Choose a current candidate from this company.",
            status_code=422,
            field="candidate_id",
        )
    posting = (
        await access.db.execute(select(Posting.status).where(Posting.id == body.posting_id))
    ).first()
    if posting is None or posting[0] != "open":
        raise AppError(
            "POSTING_NOT_OPEN",
            "Applications are closed for this posting.",
            status_code=422,
            field="posting_id",
        )
    existing = (
        await access.db.execute(
            select(Application.id).where(
                Application.candidate_id == body.candidate_id,
                Application.posting_id == body.posting_id,
            )
        )
    ).first()
    if existing is not None:
        raise AppError(
            "APPLICATION_EXISTS",
            "This candidate has already applied for this posting.",
            status_code=409,
        )
    moment = service.now()
    row = Application(
        id=uuid7(),
        company_id=access.company_id,
        candidate_id=body.candidate_id,
        posting_id=body.posting_id,
        stage="applied",
        stage_history=[
            {"stage": "applied", "at": moment.isoformat(), "by": str(access.caller.user_id)}
        ],
        cover_note=body.cover_note,
        applied_via="admin",
    )
    access.db.add(row)
    await access.db.flush()
    await access.db.refresh(row)
    await access.audit(
        "recruitment.application.created",
        entity_type="application",
        entity_id=row.id,
        after={"candidate_id": str(row.candidate_id), "posting_id": str(row.posting_id)},
    )
    await access.db.commit()
    return await service.application_out(access.db, row, await company_today(access))


@router.get("/applications/{application_id}", response_model=ApplicationOut)
async def get_application(application_id: uuid.UUID, access: ApplicationReads) -> ApplicationOut:
    company_wide(access)
    row = await _application(access, application_id)
    return await service.application_out(access.db, row, await company_today(access))


@router.post("/applications/{application_id}/stage", response_model=ApplicationOut)
async def move_application(
    application_id: uuid.UUID, body: ApplicationStageIn, access: ApplicationWrites
) -> ApplicationOut:
    company_wide(access)
    row = await _application(access, application_id, lock=True)
    previous = row.stage
    if body.stage != previous:
        check_move(previous, body.stage)
        moment = service.now()
        row.stage = body.stage
        row.stage_history = [
            *row.stage_history,
            {"stage": body.stage, "at": moment.isoformat(), "by": str(access.caller.user_id)},
        ]
        await access.db.flush()
        await access.audit(
            "recruitment.application.stage_changed",
            entity_type="application",
            entity_id=row.id,
            before={"stage": previous},
            after={"stage": row.stage},
        )
    await access.db.commit()
    return await service.application_out(access.db, row, await company_today(access))


@router.get("/recruitment/pipeline", response_model=Pipeline)
async def pipeline(access: ApplicationReads) -> Pipeline:
    company_wide(access)
    counts = dict(
        (
            await access.db.execute(
                select(Application.stage, func.count()).group_by(Application.stage)
            )
        ).all()
    )
    stages = [
        PipelineStage(
            stage=cast("Stage", stage), label=LABELS[stage], count=int(counts.get(stage, 0))
        )
        for stage in STAGES
    ]
    return Pipeline(stages=stages, total=sum(item.count for item in stages))


InterviewWrites = Annotated[Access, Depends(require("recruitment.interview.write"))]
InterviewReads = Annotated[Access, Depends(require("recruitment.interview.read"))]


async def _interview(
    access: Access, application_id: uuid.UUID, interview_id: uuid.UUID, *, lock: bool = False
) -> Interview:
    query = select(Interview).where(
        Interview.id == interview_id, Interview.application_id == application_id
    )
    if lock:
        query = query.with_for_update()
    row = (await access.db.execute(query)).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


async def _application_context(
    access: Access, application_id: uuid.UUID
) -> tuple[Application, str, str]:
    """The application, the candidate's name and the posting title, all in this company."""
    row = await _application(access, application_id)
    candidate = (
        await access.db.execute(
            select(Candidate.first_name, Candidate.last_name, Candidate.email).where(
                Candidate.id == row.candidate_id
            )
        )
    ).one()
    title = (
        await access.db.execute(select(Posting.title).where(Posting.id == row.posting_id))
    ).scalar_one()
    return row, f"{candidate[0]} {candidate[1]}", title


def _when(starts: datetime, zone: str) -> str:
    return starts.astimezone(ZoneInfo(zone)).strftime("%A %d %B %Y at %H:%M")


@router.get("/applications/{application_id}/interviews", response_model=list[InterviewOut])
async def list_interviews(application_id: uuid.UUID, access: InterviewReads) -> list[InterviewOut]:
    company_wide(access)
    await _application(access, application_id)
    rows = (
        (
            await access.db.execute(
                select(Interview)
                .where(Interview.application_id == application_id)
                .order_by(Interview.scheduled_at, Interview.id)
            )
        )
        .scalars()
        .all()
    )
    return [await service.interview_out(access.db, row) for row in rows]


@router.post(
    "/applications/{application_id}/interviews", status_code=201, response_model=InterviewOut
)
async def create_interview(
    application_id: uuid.UUID, body: InterviewIn, request: Request, access: InterviewWrites
) -> InterviewOut:
    company_wide(access)
    application, candidate_name, title = await _application_context(access, application_id)
    interviewers = (
        (
            await access.db.execute(
                select(Employee).where(
                    Employee.id.in_(body.interviewer_employee_ids),
                    Employee.status.in_(("active", "on_leave")),
                )
            )
        )
        .scalars()
        .all()
        if body.interviewer_employee_ids
        else []
    )
    if len(interviewers) != len(set(body.interviewer_employee_ids)):
        raise AppError(
            "VALIDATION_ERROR",
            "Choose current people from this company as interviewers.",
            status_code=422,
            field="interviewer_employee_ids",
        )
    row = Interview(
        id=uuid7(),
        company_id=access.company_id,
        application_id=application_id,
        scheduled_at=body.scheduled_at,
        duration_minutes=body.duration_minutes,
        mode=body.mode,
        location_or_link=body.location_or_link,
        interviewer_employee_ids=list(body.interviewer_employee_ids),
        outcome="pending",
        notes=body.notes,
    )
    access.db.add(row)
    await access.db.flush()
    await access.db.refresh(row)
    zone = (
        await access.db.execute(select(Company.timezone).where(Company.id == access.company_id))
    ).scalar_one()
    where = body.location_or_link or MODE_LABELS[body.mode]
    settings = request.app.state.settings
    link = f"{settings.web_origin}/recruitment/applications/{application_id}"
    when = _when(body.scheduled_at, zone)
    for person in interviewers:
        if person.email:
            data = {
                "first_name": person.first_name,
                "job_title": title,
                "when": when,
                "where": where,
                "link": link,
            }
            check("interview_invite", data)
            db_row = EmailOutbox(
                to_address=person.email,
                template="interview_invite",
                payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
            )
            access.db.add(db_row)
    candidate_email = (
        await access.db.execute(
            select(Candidate.email).where(Candidate.id == application.candidate_id)
        )
    ).scalar_one()
    if candidate_email:
        first = candidate_name.split(" ")[0]
        data = {"first_name": first, "job_title": title, "when": when, "where": where}
        check("interview_invite_candidate", data)
        access.db.add(
            EmailOutbox(
                to_address=candidate_email,
                template="interview_invite_candidate",
                payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
            )
        )
    await access.audit(
        "recruitment.interview.created",
        entity_type="interview",
        entity_id=row.id,
        after={
            "application_id": str(application_id),
            "scheduled_at": body.scheduled_at.isoformat(),
            "mode": body.mode,
            "interviewers": len(interviewers),
        },
    )
    await access.db.commit()
    return await service.interview_out(access.db, row)


@router.patch(
    "/applications/{application_id}/interviews/{interview_id}", response_model=InterviewOut
)
async def update_interview(
    application_id: uuid.UUID,
    interview_id: uuid.UUID,
    body: InterviewPatch,
    access: InterviewWrites,
) -> InterviewOut:
    company_wide(access)
    row = await _interview(access, application_id, interview_id, lock=True)
    before = {"outcome": row.outcome}
    if body.outcome is not None:
        row.outcome = body.outcome
    if "notes" in body.model_fields_set:
        row.notes = body.notes
    await access.db.flush()
    await access.audit(
        "recruitment.interview.updated",
        entity_type="interview",
        entity_id=row.id,
        before=before,
        after={"outcome": row.outcome},
    )
    await access.db.commit()
    return await service.interview_out(access.db, row)


@router.get(
    "/applications/{application_id}/interviews/{interview_id}/invite.ics", response_class=Response
)
async def interview_invite(
    application_id: uuid.UUID, interview_id: uuid.UUID, request: Request, access: InterviewReads
) -> Response:
    company_wide(access)
    row = await _interview(access, application_id, interview_id)
    application, candidate_name, title = await _application_context(access, application_id)
    people = (
        await access.db.execute(
            select(Employee.first_name, Employee.last_name, Employee.email)
            .where(Employee.id.in_(row.interviewer_employee_ids))
            .order_by(Employee.last_name, Employee.first_name)
        )
    ).all()
    candidate = (
        await access.db.execute(
            select(Candidate.email).where(Candidate.id == application.candidate_id)
        )
    ).scalar_one()
    attendees = [(f"{first} {last}".strip(), email) for first, last, email in people if email]
    if candidate:
        attendees.append((candidate_name, candidate))
    host = urlparse(request.app.state.settings.web_origin).hostname or "invite.local"
    text = interview_ics(
        uid=f"interview-{row.id}@{host}",
        starts=row.scheduled_at,
        duration_minutes=row.duration_minutes,
        summary=f"Interview: {candidate_name} for {title}",
        location=row.location_or_link or MODE_LABELS[row.mode],
        description=f"Interview ({MODE_LABELS[row.mode]}) for {title}.",
        attendees=attendees,
        stamp=service.now(),
    )
    return Response(
        content=text,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="interview-{row.id}.ics"',
            "Cache-Control": "private, no-store",
        },
    )
