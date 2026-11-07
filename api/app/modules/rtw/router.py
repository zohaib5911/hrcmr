"""RTW records: checked subjects/files, encrypted codes, append-only history and corrections."""

from __future__ import annotations

import asyncio
import uuid  # noqa: TC003
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from app.core.crypto import mask_tail
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope
from app.db.ids import uuid7
from app.db.rtw import employee_rtw_status
from app.integrations.storage import PRESIGN_SECONDS
from app.modules.companies.compliance_documents import _today
from app.modules.employees.document_router import _files
from app.modules.employees.employment_router import _locked_employee
from app.modules.employees.record_pdf import record_html, render_pdf
from app.modules.employees.router import _employee
from app.modules.files.models import File
from app.modules.files.schemas import DownloadOut
from app.modules.identity.models import Membership, User
from app.modules.rbac.deps import Access, require
from app.modules.recruitment.models import Candidate
from app.modules.rtw.models import RTWCheck
from app.modules.rtw.schemas import CheckIn, CheckOut, CorrectionIn, RTWStatus, RTWTab

router = APIRouter(tags=["right-to-work"])
Reads = Annotated[Access, Depends(require("employee.rtw.read"))]
Writes = Annotated[Access, Depends(require("employee.rtw.write"))]
Corrects = Annotated[Access, Depends(require("employee.rtw.correct"))]
Reports = Annotated[Access, Depends(require("document.report.generate"))]


def status_of(row: RTWCheck, today: date, *, clean_evidence: bool) -> RTWStatus:
    if row.outcome == "failed":
        return "failed"
    if row.outcome == "pending":
        return "pending"
    if row.follow_up_due_on and row.follow_up_due_on < today:
        return "expired"
    if not clean_evidence:
        return "evidence_missing"
    if row.follow_up_due_on and (row.follow_up_due_on - today).days <= 60:
        return "expiring"
    return "verified"


async def _by_id(access: Access, employee_id: uuid.UUID, check_id: uuid.UUID) -> RTWCheck:
    row = (
        await access.db.execute(
            select(RTWCheck).where(
                RTWCheck.id == check_id,
                RTWCheck.subject_type == "employee",
                RTWCheck.subject_id == employee_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


async def _out(access: Access, row: RTWCheck, today: date) -> CheckOut:
    checker = (
        (
            await access.db.execute(
                select(User.first_name, User.last_name).where(User.id == row.checked_by_user_id)
            )
        ).first()
        if row.checked_by_user_id
        else None
    )
    file = (
        (
            await access.db.execute(
                select(File.original_name, File.scan_status).where(
                    File.id == row.evidence_file_id,
                    File.owner_type == row.subject_type,
                    File.owner_id == row.subject_id,
                )
            )
        ).first()
        if row.evidence_file_id
        else None
    )
    corrected = (
        await access.db.execute(select(RTWCheck.id).where(RTWCheck.corrected_from_id == row.id))
    ).first()
    return CheckOut(
        id=row.id,
        check_type=row.check_type,  # type: ignore[arg-type]
        share_code_masked=mask_tail(row.share_code, 3) if row.share_code else None,
        idsp_provider=row.idsp_provider,
        idsp_document=row.idsp_document,
        list_b_group=row.list_b_group,
        permission_expires=row.permission_expires,
        permission_expires_on=row.permission_expires_on,
        follow_up_due_on=row.follow_up_due_on,
        check_date=row.check_date,
        checked_by_user_id=row.checked_by_user_id,
        checker_name=f"{checker[0]} {checker[1]}" if checker else None,
        outcome=row.outcome,  # type: ignore[arg-type]
        evidence_file_id=row.evidence_file_id,
        evidence_file_name=file[0] if file else None,
        status=status_of(row, today, clean_evidence=file is not None and file[1] == "clean"),
        superseded_at=row.superseded_at,
        superseded_by=row.superseded_by,
        corrected_from_id=row.corrected_from_id,
        correction_reason=row.correction_reason,
        created_at=row.created_at,
        can_correct=corrected is None,
    )


async def _validate(
    access: Access, employee_id: uuid.UUID, body: CheckIn, *, subject_type: str = "employee"
) -> None:
    if body.check_date > await _today(access):
        raise ConflictError("The date of the check cannot be in the future.", field="check_date")
    checker = (
        await access.db.execute(
            select(Membership.id).where(Membership.user_id == body.checked_by_user_id)
        )
    ).first()
    if checker is None:
        raise NotFoundError
    if body.evidence_file_id:
        evidence = (
            await access.db.execute(
                select(File).where(
                    File.id == body.evidence_file_id,
                    File.owner_type == subject_type,
                    File.owner_id == employee_id,
                    File.scan_status == "clean",
                )
            )
        ).scalar_one_or_none()
        if evidence is None:
            raise NotFoundError


@router.get("/employees/{employee_id}/rtw-checks", response_model=RTWTab)
async def checks(employee_id: uuid.UUID, access: Reads) -> RTWTab:
    await _employee(access, employee_id)
    rows = list(
        (
            await access.db.execute(
                select(RTWCheck)
                .where(RTWCheck.subject_type == "employee", RTWCheck.subject_id == employee_id)
                .order_by(RTWCheck.created_at.desc(), RTWCheck.id.desc())
            )
        ).scalars()
    )
    today = await _today(access)
    result = [await _out(access, r, today) for r in rows]
    current = next((r for r in result if r.superseded_at is None), None)
    status = (
        await access.db.execute(
            select(employee_rtw_status.c.status, employee_rtw_status.c.follow_up_due_on).where(
                employee_rtw_status.c.employee_id == employee_id,
                employee_rtw_status.c.company_id == access.company_id,
            )
        )
    ).one()
    return RTWTab(status=status[0], follow_up_due_on=status[1], current=current, checks=result)


async def _record(
    access: Access,
    employee_id: uuid.UUID,
    body: CheckIn,
    *,
    corrected: RTWCheck | None = None,
    reason: str | None = None,
) -> CheckOut:
    await _validate(access, employee_id, body)
    data = body.model_dump(exclude={"reason"})
    ident = uuid7()
    historic = corrected is not None and corrected.superseded_at is not None
    if not historic:
        current = (
            await access.db.execute(
                select(RTWCheck).where(
                    RTWCheck.subject_type == "employee",
                    RTWCheck.subject_id == employee_id,
                    RTWCheck.superseded_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if current:
            current.superseded_at = datetime.now(UTC)
            current.superseded_by = ident
            await access.db.flush()
    row = RTWCheck(
        id=ident,
        company_id=access.company_id,
        subject_type="employee",
        subject_id=employee_id,
        corrected_from_id=corrected.id if corrected else None,
        correction_reason=reason,
        superseded_at=corrected.superseded_at if historic and corrected else None,
        superseded_by=corrected.superseded_by if historic and corrected else None,
        **data,
    )
    access.db.add(row)
    await access.db.flush()
    from app.modules.compliance.reminder_service import synchronize_employee

    await synchronize_employee(
        access.db, employee_id, access.audit_context, today=await _today(access)
    )
    await access.audit(
        "employee.rtw_corrected" if corrected else "employee.rtw_recorded",
        entity_type="employee",
        entity_id=employee_id,
        after={
            "check_id": str(row.id),
            "check_type": row.check_type,
            "outcome": row.outcome,
            "corrected_from_id": str(corrected.id) if corrected else None,
        },
        reason=reason,
    )
    await access.db.commit()
    return await _out(access, row, await _today(access))


@router.post("/employees/{employee_id}/rtw-checks", status_code=201, response_model=CheckOut)
async def record_check(employee_id: uuid.UUID, body: CheckIn, access: Writes) -> CheckOut:
    await _locked_employee(access, employee_id)
    return await _record(access, employee_id, body)


@router.post(
    "/employees/{employee_id}/rtw-checks/{check_id}/correct",
    status_code=201,
    response_model=CheckOut,
)
async def correct_check(
    employee_id: uuid.UUID, check_id: uuid.UUID, body: CorrectionIn, access: Corrects
) -> CheckOut:
    await _locked_employee(access, employee_id)
    old = await _by_id(access, employee_id, check_id)
    already = (
        await access.db.execute(select(RTWCheck.id).where(RTWCheck.corrected_from_id == old.id))
    ).first()
    if already:
        raise ConflictError(
            "This version has already been corrected. Correct its replacement instead."
        )
    return await _record(access, employee_id, body, corrected=old, reason=body.reason)


@router.get("/employees/{employee_id}/rtw-checks/{check_id}/evidence", response_model=DownloadOut)
async def evidence(
    employee_id: uuid.UUID, check_id: uuid.UUID, request: Request, access: Reads
) -> DownloadOut:
    await _employee(access, employee_id)
    row = await _by_id(access, employee_id, check_id)
    if row.evidence_file_id is None:
        raise NotFoundError
    # Old evidence stays attached to its old version and can only be delivered while clean.
    file = await _files(request).get(access, row.evidence_file_id)
    if file.owner_type != "employee" or file.owner_id != employee_id:
        raise NotFoundError
    url, _ = await _files(request).download_url(access, file.id)
    return DownloadOut(url=url, expires_in=PRESIGN_SECONDS)


@router.get(
    "/employees/{employee_id}/rtw-checks/{check_id}/evidence.pdf",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "Dated, masked RTW evidence sheet"}
    },
)
async def evidence_pdf(employee_id: uuid.UUID, check_id: uuid.UUID, access: Reports) -> Response:
    employee = await _employee(access, employee_id)
    row = await _by_id(access, employee_id, check_id)
    out = await _out(access, row, await _today(access))
    html = record_html(
        f"{employee.first_name} {employee.last_name}",
        datetime.now(UTC).strftime("%d %b %Y %H:%M UTC"),
        [
            ("Check reference", [{"reference": str(row.id)}]),
            ("Right to Work check", [out.model_dump(mode="json")]),
        ],
        report_title="Right to Work evidence sheet",
        notice=(
            "Share codes are masked. Keep this sheet with the original evidence "
            "and the record of the check."
        ),
    )
    pdf = await asyncio.to_thread(render_pdf, html)
    await access.audit(
        "employee.rtw_evidence_exported",
        entity_type="employee",
        entity_id=employee_id,
        after={"check_id": str(row.id)},
    )
    await access.db.commit()
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="rtw-{row.id}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


# --- candidates: the same check, owned by a candidate (plan 8.11, T11.3) ----------------------
CandidateReads = Annotated[Access, Depends(require("recruitment.candidate.read"))]
CandidateWrites = Annotated[Access, Depends(require("recruitment.candidate.write"))]


async def _candidate(access: Access, candidate_id: uuid.UUID, *, lock: bool = False) -> Candidate:
    """A candidate of this company, or a 404. Less than company-wide scope is refused."""
    if access.scope is not Scope.ALL:
        raise ForbiddenError
    query = select(Candidate).where(Candidate.id == candidate_id)
    if lock:
        query = query.with_for_update()
    row = (await access.db.execute(query)).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


@router.get("/candidates/{candidate_id}/rtw-checks", response_model=RTWTab)
async def candidate_checks(candidate_id: uuid.UUID, access: CandidateReads) -> RTWTab:
    await _candidate(access, candidate_id)
    rows = list(
        (
            await access.db.execute(
                select(RTWCheck)
                .where(RTWCheck.subject_type == "candidate", RTWCheck.subject_id == candidate_id)
                .order_by(RTWCheck.created_at.desc(), RTWCheck.id.desc())
            )
        ).scalars()
    )
    today = await _today(access)
    result = [await _out(access, row, today) for row in rows]
    current = next((check for check in result if check.superseded_at is None), None)
    return RTWTab(
        status=current.status if current else "not_recorded",
        follow_up_due_on=current.follow_up_due_on if current else None,
        current=current,
        checks=result,
    )


@router.post("/candidates/{candidate_id}/rtw-checks", status_code=201, response_model=CheckOut)
async def record_candidate_check(
    candidate_id: uuid.UUID, body: CheckIn, access: CandidateWrites
) -> CheckOut:
    await _candidate(access, candidate_id, lock=True)
    await _validate(access, candidate_id, body, subject_type="candidate")
    ident = uuid7()
    current = (
        await access.db.execute(
            select(RTWCheck).where(
                RTWCheck.subject_type == "candidate",
                RTWCheck.subject_id == candidate_id,
                RTWCheck.superseded_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if current is not None:
        current.superseded_at = datetime.now(UTC)
        current.superseded_by = ident
        await access.db.flush()
    row = RTWCheck(
        id=ident,
        company_id=access.company_id,
        subject_type="candidate",
        subject_id=candidate_id,
        **body.model_dump(),
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "candidate.rtw_recorded",
        entity_type="candidate",
        entity_id=candidate_id,
        after={"check_id": str(row.id), "check_type": row.check_type, "outcome": row.outcome},
    )
    await access.db.commit()
    return await _out(access, row, await _today(access))
