"""Employee-owned policy confirmations and version-bound, immutable evidence receipts."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date  # noqa: TC003
from typing import TYPE_CHECKING, Annotated, Any, cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, or_, select

from app.core.errors import AppError, NotFoundError
from app.integrations.storage import PRESIGN_SECONDS
from app.modules.auth.deps import client_ip
from app.modules.employees.models import Employee
from app.modules.files.models import File
from app.modules.files.schemas import DownloadOut
from app.modules.policies import service
from app.modules.policies.models import PolicyAcceptance, PolicyDocument
from app.modules.policies.schemas import (
    OwnPolicy,
    OwnPolicyPage,
    OwnPolicySummary,
    PolicyAccept,
    PolicyReceipt,
)
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from app.modules.files.service import FileService
    from app.modules.policies.reference import AcceptanceStatus, ConfirmationMode

router = APIRouter(prefix="/policies", tags=["policies"])
Reads = Annotated[Access, Depends(require("policy.acceptance.read"))]
Writes = Annotated[Access, Depends(require("policy.acceptance.write"))]


async def assigned(
    access: Access, policy_id: uuid.UUID, *, lock: bool = False
) -> tuple[PolicyDocument, PolicyAcceptance]:
    if access.employee_id is None:
        raise NotFoundError
    row = await service.policy(access.db, policy_id, lock=lock)
    query = select(PolicyAcceptance).where(
        PolicyAcceptance.policy_document_id == row.id,
        PolicyAcceptance.employee_id == access.employee_id,
    )
    if lock:
        query = query.with_for_update()
    receipt = (await access.db.execute(query)).scalar_one_or_none()
    if receipt is None or row.status == "draft":
        raise NotFoundError
    return row, receipt


async def receipt_out(
    access: Access, row: PolicyDocument, receipt: PolicyAcceptance
) -> PolicyReceipt:
    if receipt.accepted_at is None:
        raise NotFoundError
    employee = (
        await access.db.execute(
            select(Employee.first_name, Employee.last_name).where(
                Employee.id == receipt.employee_id
            )
        )
    ).one()
    return PolicyReceipt(
        id=receipt.id,
        policy_document_id=row.id,
        title=row.title,
        version=row.version,
        employee_id=receipt.employee_id,
        employee_name=f"{employee.first_name} {employee.last_name}".strip(),
        confirmation_mode=cast("ConfirmationMode", row.confirmation_mode),
        accepted_at=receipt.accepted_at,
        typed_signature=receipt.typed_signature,
        ip=receipt.ip,
        user_agent=receipt.user_agent,
    )


async def available_file(access: Access, row: PolicyDocument) -> File:
    if row.file_id is None:
        raise NotFoundError
    file = await access.db.get(File, row.file_id)
    if file is None or file.scan_status != "clean":
        raise NotFoundError
    return file


async def view_file(request: Request, access: Access, row: PolicyDocument) -> Response:
    file = await available_file(access, row)
    if file.mime not in {"application/pdf", "image/jpeg", "image/png"}:
        raise AppError(
            "POLICY_PREVIEW_UNAVAILABLE", "Download this document to read it.", status_code=415
        )
    if file.size > 25 * 1024 * 1024:
        raise AppError(
            "POLICY_PREVIEW_TOO_LARGE", "Download this document to read it.", status_code=413
        )
    files: FileService = request.app.state.files
    if files.storage is None:
        raise AppError("STORAGE_NOT_CONFIGURED", "Document storage is not set up.", status_code=503)
    # In pieces (C6.1.11): a 25 MB policy is never held whole in this process.
    content = await files.storage.open(file.storage_key)
    await access.audit(
        "policy.file_viewed",
        entity_type="policy_document",
        entity_id=row.id,
        after={"version": row.version},
    )
    await access.db.commit()
    return StreamingResponse(
        content,
        media_type=file.mime,
        headers={
            "Content-Disposition": "inline; filename*=UTF-8''" + quote(file.original_name, safe=""),
            "Content-Length": str(file.size),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": (
                "default-src 'none'; frame-ancestors "
                f"{request.app.state.settings.web_origin}; sandbox allow-scripts allow-same-origin"
            ),
        },
    )


@router.get("/own", response_model=OwnPolicyPage)
async def own_policies(
    access: Reads,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OwnPolicyPage:
    if access.employee_id is None:
        return OwnPolicyPage(items=[], total=0)
    query = _own_query(access.employee_id)
    total = (
        await access.db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    rows = (
        await access.db.execute(
            query.order_by(
                PolicyAcceptance.accepted_at.is_not(None),
                PolicyAcceptance.due_on,
                PolicyDocument.sent_at.desc(),
                PolicyDocument.id,
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()
    today = await service.company_day(access.db)
    return OwnPolicyPage(items=[_own_out(row, today) for row in rows], total=total)


def _own_query(employee_id: uuid.UUID) -> Any:
    """The person's own assigned policies that are sent, or that they have already confirmed."""
    return (
        select(
            PolicyDocument,
            PolicyAcceptance.due_on,
            PolicyAcceptance.status,
            PolicyAcceptance.accepted_at,
            File.mime,
        )
        .join(PolicyAcceptance, PolicyAcceptance.policy_document_id == PolicyDocument.id)
        .join(File, File.id == PolicyDocument.file_id)
        .where(
            PolicyAcceptance.employee_id == employee_id,
            or_(PolicyDocument.status == "sent", PolicyAcceptance.accepted_at.is_not(None)),
        )
    )


def _own_out(row: Any, today: date) -> OwnPolicy:
    policy, due, status, accepted, mime = row
    return OwnPolicy(
        id=policy.id,
        title=policy.title,
        version=policy.version,
        confirmation_mode=cast("ConfirmationMode", policy.confirmation_mode),
        due_on=due,
        status="overdue" if accepted is None and due < today else cast("AcceptanceStatus", status),
        accepted_at=accepted,
        file_mime=mime,
        archived=policy.status == "archived",
    )


@router.get("/own/summary", response_model=OwnPolicySummary)
async def own_policy_summary(access: Reads) -> OwnPolicySummary:
    if access.employee_id is None:
        return OwnPolicySummary(pending=0, overdue=0, completed=0)
    today = await service.company_day(access.db)
    pending = PolicyAcceptance.accepted_at.is_(None)
    counts = (
        await access.db.execute(
            select(
                func.sum(case((pending & (PolicyAcceptance.due_on >= today), 1), else_=0)),
                func.sum(case((pending & (PolicyAcceptance.due_on < today), 1), else_=0)),
                func.sum(case((PolicyAcceptance.accepted_at.is_not(None), 1), else_=0)),
            )
            .join(PolicyDocument, PolicyDocument.id == PolicyAcceptance.policy_document_id)
            .where(
                PolicyAcceptance.employee_id == access.employee_id,
                or_(PolicyDocument.status == "sent", PolicyAcceptance.accepted_at.is_not(None)),
            )
        )
    ).one()
    return OwnPolicySummary(
        pending=counts[0] or 0, overdue=counts[1] or 0, completed=counts[2] or 0
    )


@router.get("/own/{policy_id}", response_model=OwnPolicy)
async def own_policy(policy_id: uuid.UUID, access: Reads) -> OwnPolicy:
    """One of the person's own policies, for a link from a notice (ISS-14). Anyone else's is 404."""
    row = (
        (
            await access.db.execute(
                _own_query(access.employee_id).where(PolicyDocument.id == policy_id)
            )
        ).first()
        if access.employee_id is not None
        else None
    )
    if row is None:
        raise AppError("NOT_FOUND", "That policy is not one of yours.", status_code=404)
    return _own_out(row, await service.company_day(access.db))


@router.get("/own/{policy_id}/view", response_class=Response)
async def own_policy_view(policy_id: uuid.UUID, request: Request, access: Reads) -> Response:
    row, receipt = await assigned(access, policy_id)
    if row.status == "archived" and receipt.accepted_at is None:
        raise NotFoundError
    return await view_file(request, access, row)


@router.get("/own/{policy_id}/download", response_model=DownloadOut)
async def own_policy_download(policy_id: uuid.UUID, request: Request, access: Reads) -> DownloadOut:
    row, receipt = await assigned(access, policy_id)
    if row.status == "archived" and receipt.accepted_at is None:
        raise NotFoundError
    file = await available_file(access, row)
    files: FileService = request.app.state.files
    url, _ = await files.download_url(access, file.id)
    return DownloadOut(url=url, expires_in=PRESIGN_SECONDS)


@router.get("/{policy_id}/receipt", response_model=PolicyReceipt)
async def own_policy_receipt(policy_id: uuid.UUID, access: Reads) -> PolicyReceipt:
    row, receipt = await assigned(access, policy_id)
    return await receipt_out(access, row, receipt)


@router.post("/{policy_id}/accept", response_model=PolicyReceipt)
async def accept_policy(
    policy_id: uuid.UUID, body: PolicyAccept, request: Request, access: Writes
) -> PolicyReceipt:
    row, receipt = await assigned(access, policy_id, lock=True)
    if not body.confirmed:
        raise AppError(
            "POLICY_CONFIRMATION_REQUIRED",
            "Confirm that you have read the document.",
            status_code=422,
            field="confirmed",
        )
    if row.confirmation_mode == "sign" and not body.typed_signature:
        raise AppError(
            "POLICY_SIGNATURE_REQUIRED",
            "Type your full name to sign.",
            status_code=422,
            field="typed_signature",
        )
    if row.confirmation_mode == "accept" and body.typed_signature is not None:
        raise AppError(
            "POLICY_MODE_MISMATCH",
            "This document requires acceptance rather than a signature.",
            status_code=422,
        )
    if receipt.accepted_at is not None:
        if body.typed_signature != receipt.typed_signature:
            raise AppError(
                "POLICY_ALREADY_CONFIRMED", "This version already has a receipt.", status_code=409
            )
        return await receipt_out(access, row, receipt)
    if row.status != "sent":
        raise AppError(
            "POLICY_ARCHIVED",
            "This version is archived. Open your current documents.",
            status_code=409,
        )
    await available_file(access, row)
    receipt.status = "signed" if row.confirmation_mode == "sign" else "accepted"
    receipt.accepted_at, receipt.accepted_by = service.now(), access.caller.user_id
    receipt.typed_signature = body.typed_signature
    receipt.ip = client_ip(request)
    receipt.user_agent = request.headers.get("user-agent", "")[:500] or None
    await access.audit(
        "policy.signed" if row.confirmation_mode == "sign" else "policy.accepted",
        entity_type="policy_acceptance",
        entity_id=receipt.id,
        after={
            "policy_document_id": str(row.id),
            "version": row.version,
            "employee_id": str(receipt.employee_id),
        },
    )
    await access.db.commit()
    return await receipt_out(access, row, receipt)
