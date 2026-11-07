"""Company policy drafts, reviewed audiences, sent versions and retained history."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, UploadFile
from sqlalchemy import func, select

from app.core.errors import ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope
from app.db.ids import uuid7
from app.modules.files.models import File
from app.modules.policies import service
from app.modules.policies.models import PolicyAcceptance, PolicyDocument
from app.modules.policies.own_router import receipt_out, view_file
from app.modules.policies.schemas import (
    PolicyAction,
    PolicyDraft,
    PolicyOut,
    PolicyPage,
    PolicyReceipt,
    PolicyRecipient,
    PolicyRecipients,
    PolicySend,
)
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from app.modules.files.service import FileService

router = APIRouter(prefix="/policies", tags=["policies"])
Reads = Annotated[Access, Depends(require("policy.document.read"))]
Writes = Annotated[Access, Depends(require("policy.document.write"))]
KINDS = frozenset({"pdf", "jpg", "png", "doc", "docx"})


def all_scope(access: Access) -> None:
    if access.scope is not Scope.ALL:
        raise ForbiddenError


@router.get("", response_model=PolicyPage)
async def list_policies(
    access: Reads,
    search: Annotated[str, Query(max_length=200)] = "",
    show_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PolicyPage:
    all_scope(access)
    query = select(PolicyDocument)
    if not show_archived:
        query = query.where(PolicyDocument.status != "archived")
    if search.strip():
        query = query.where(
            func.lower(PolicyDocument.title).contains(search.strip().lower(), autoescape=True)
        )
    total = (
        await access.db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    rows = (
        (
            await access.db.execute(
                query.order_by(PolicyDocument.created_at.desc(), PolicyDocument.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    today = await service.company_day(access.db)
    return PolicyPage(items=[await service.out(access.db, row, today) for row in rows], total=total)


@router.post("", status_code=201, response_model=PolicyOut)
async def create_policy(body: PolicyDraft, access: Writes) -> PolicyOut:
    all_scope(access)
    await service.validate_audience(access.db, body)
    ident = uuid7()
    row = PolicyDocument(
        id=ident, group_id=ident, company_id=access.company_id, **body.model_dump()
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "policy.created",
        entity_type="policy_document",
        entity_id=row.id,
        after=service.metadata(row),
    )
    await access.db.commit()
    return await service.out(access.db, row, await service.company_day(access.db))


@router.get("/{policy_id}", response_model=PolicyOut)
async def get_policy(policy_id: uuid.UUID, access: Reads) -> PolicyOut:
    all_scope(access)
    return await service.out(
        access.db, await service.policy(access.db, policy_id), await service.company_day(access.db)
    )


@router.patch("/{policy_id}", response_model=PolicyOut)
async def update_policy(policy_id: uuid.UUID, body: PolicyDraft, access: Writes) -> PolicyOut:
    all_scope(access)
    row = await service.policy(access.db, policy_id, lock=True)
    service.draft_only(row)
    await service.validate_audience(access.db, body)
    before = service.metadata(row)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    if row.file_id:
        file = await access.db.get(File, row.file_id)
        if file:
            file.category = row.category
    if before != service.metadata(row):
        await access.audit(
            "policy.updated",
            entity_type="policy_document",
            entity_id=row.id,
            before=before,
            after=service.metadata(row),
        )
    await access.db.commit()
    return await service.out(access.db, row, await service.company_day(access.db))


@router.post("/{policy_id}/file", response_model=PolicyOut)
async def upload_policy_file(
    policy_id: uuid.UUID, request: Request, file: UploadFile, access: Writes
) -> PolicyOut:
    all_scope(access)
    row = await service.policy(access.db, policy_id, lock=True)
    service.draft_only(row)
    files: FileService = request.app.state.files
    record = await files.upload(
        access,
        file.file,
        filename=file.filename,
        owner_type="policy_document",
        owner_id=row.id,
        category=row.category,
        kinds=KINDS,
        commit=False,
    )
    before = row.file_id
    row.file_id = record.id
    await access.audit(
        "policy.file_uploaded",
        entity_type="policy_document",
        entity_id=row.id,
        before={"file_id": str(before) if before else None},
        after={"file_id": str(record.id)},
    )
    await access.db.commit()
    return await service.out(access.db, row, await service.company_day(access.db))


@router.get("/{policy_id}/recipients", response_model=PolicyRecipients)
async def preview_recipients(policy_id: uuid.UUID, access: Reads) -> PolicyRecipients:
    all_scope(access)
    row = await service.policy(access.db, policy_id)
    today = await service.company_day(access.db)
    items = await service.recipients(access.db, row, today)
    people = [service.Candidate(p.employee_id, "", "", p.employee_number) for p in items]
    return PolicyRecipients(items=items, preview_token=service.preview_token(row, people, today))


@router.get("/{policy_id}/acceptances", response_model=list[PolicyRecipient])
async def policy_acceptances(policy_id: uuid.UUID, access: Reads) -> list[PolicyRecipient]:
    all_scope(access)
    row = await service.policy(access.db, policy_id)
    return (
        []
        if row.status == "draft"
        else await service.recipients(access.db, row, await service.company_day(access.db))
    )


@router.post("/{policy_id}/send", response_model=PolicyOut)
async def send_policy(
    policy_id: uuid.UUID, body: PolicySend, request: Request, access: Writes
) -> PolicyOut:
    all_scope(access)
    row = await service.policy(access.db, policy_id, lock=True)
    if row.status != "sent":
        await service.send(
            access.db,
            row,
            body.preview_token,
            access.caller.user_id,
            access.audit_context,
            request.app.state.settings.web_origin,
        )
    await access.db.commit()
    return await service.out(access.db, row, await service.company_day(access.db))


@router.post("/{policy_id}/remind", response_model=PolicyAction)
async def remind_policy(policy_id: uuid.UUID, request: Request, access: Writes) -> PolicyAction:
    """Nudge only the people who have not yet accepted or signed this sent version."""
    all_scope(access)
    row = await service.policy(access.db, policy_id, lock=True)
    count = await service.remind(
        access.db, row, access.audit_context, request.app.state.settings.web_origin
    )
    await access.db.commit()
    return PolicyAction(count=count)


@router.post("/{policy_id}/new-version", status_code=201, response_model=PolicyOut)
async def new_policy_version(policy_id: uuid.UUID, access: Writes) -> PolicyOut:
    all_scope(access)
    row = await service.policy(access.db, policy_id, lock=True)
    draft = await service.new_version(access.db, row, access.audit_context)
    await access.db.commit()
    return await service.out(access.db, draft, await service.company_day(access.db))


@router.delete("/{policy_id}", status_code=204)
async def archive_policy(policy_id: uuid.UUID, access: Writes) -> Response:
    all_scope(access)
    row = await service.policy(access.db, policy_id, lock=True)
    if row.status != "archived":
        row.status, row.archived_at = "archived", service.now()
        await access.audit(
            "policy.archived",
            entity_type="policy_document",
            entity_id=row.id,
            after={"version": row.version},
        )
    await access.db.commit()
    return Response(status_code=204)


@router.get("/{policy_id}/view", response_class=Response)
async def policy_file_view(policy_id: uuid.UUID, request: Request, access: Reads) -> Response:
    all_scope(access)
    return await view_file(request, access, await service.policy(access.db, policy_id))


@router.get("/{policy_id}/acceptances/{acceptance_id}/receipt", response_model=PolicyReceipt)
async def employee_receipt(
    policy_id: uuid.UUID, acceptance_id: uuid.UUID, access: Reads
) -> PolicyReceipt:
    all_scope(access)
    row = await service.policy(access.db, policy_id)
    receipt = (
        await access.db.execute(
            select(PolicyAcceptance).where(
                PolicyAcceptance.id == acceptance_id, PolicyAcceptance.policy_document_id == row.id
            )
        )
    ).scalar_one_or_none()
    if receipt is None:
        raise NotFoundError
    return await receipt_out(access, row, receipt)
