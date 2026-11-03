"""Official dossier links, an original checklist PDF and separately protected platform editing."""

from __future__ import annotations

import asyncio
import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from app.core.errors import NotFoundError
from app.modules.audit.service import record
from app.modules.compliance.dossier_models import DossierLink
from app.modules.compliance.dossier_schemas import DossierLinkIn, DossierLinkOut, DossierOut
from app.modules.employees.record_pdf import record_html, render_pdf
from app.modules.rbac.deps import Access, require
from app.modules.rbac.platform import PlatformAccess, require_platform

router = APIRouter(tags=["compliance-dossier"])
Reads = Annotated[Access, Depends(require("compliance.overview.read"))]
Content = Annotated[PlatformAccess, Depends(require_platform("platform.content.write"))]


def _out(row: DossierLink) -> DossierLinkOut:
    return DossierLinkOut(
        id=row.id,
        section=row.section,  # type: ignore[arg-type]
        title=row.title,
        url=row.url,
        checked_on=row.checked_on,
        position=row.position,
        active=row.active,
    )


@router.get("/compliance/dossier", response_model=DossierOut)
async def dossier(access: Reads) -> DossierOut:
    rows = (
        await access.db.execute(
            select(DossierLink)
            .where(DossierLink.active.is_(True))
            .order_by(DossierLink.position, DossierLink.id)
        )
    ).scalars()
    return DossierOut(links=[_out(row) for row in rows])


@router.get("/admin/dossier-links", response_model=list[DossierLinkOut])
async def admin_links(access: Content) -> list[DossierLinkOut]:
    rows = (
        await access.db.execute(select(DossierLink).order_by(DossierLink.position, DossierLink.id))
    ).scalars()
    return [_out(row) for row in rows]


@router.post("/admin/dossier-links", status_code=201, response_model=DossierLinkOut)
async def add_link(body: DossierLinkIn, access: Content) -> DossierLinkOut:
    row = DossierLink(
        **body.model_dump(), created_by=access.caller.user_id, updated_by=access.caller.user_id
    )
    access.db.add(row)
    await access.db.flush()
    await record(
        access.db,
        access.audit_context,
        "platform.dossier_link_added",
        entity_type="dossier_link",
        entity_id=row.id,
        after=body.model_dump(),
    )
    await access.db.commit()
    return _out(row)


@router.put("/admin/dossier-links/{link_id}", response_model=DossierLinkOut)
async def update_link(link_id: uuid.UUID, body: DossierLinkIn, access: Content) -> DossierLinkOut:
    row = (
        await access.db.execute(
            select(DossierLink).where(DossierLink.id == link_id).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    before = _out(row).model_dump()
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    row.updated_by = access.caller.user_id
    await record(
        access.db,
        access.audit_context,
        "platform.dossier_link_updated",
        entity_type="dossier_link",
        entity_id=row.id,
        before=before,
        after=body.model_dump(),
    )
    await access.db.commit()
    return _out(row)


@router.get(
    "/compliance/rtw-checklist.pdf",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "Original Right to Work checklist"}
    },
)
async def checklist(access: Reads) -> Response:
    sections = [
        (
            "Before work starts",
            [
                {
                    "task": "Use the current GOV.UK employer guide to choose an eligible "
                    "checking method. Apply a consistent process to everyone.",
                    "record": "Employee, proposed work, method and checker.",
                }
            ],
        ),
        (
            "Carry out and retain the check",
            [
                {
                    "task": "Complete the chosen online, eligible digital identity or "
                    "original-document check. Confirm the evidence relates to the person "
                    "and permits the proposed work.",
                    "record": "Check date, outcome, work restrictions and clear evidence "
                    "of the check. Follow the official guide for evidence retention.",
                }
            ],
        ),
        (
            "Follow up",
            [
                {
                    "task": "Where another check is required, record the due date and arrange "
                    "the follow-up. Review missing evidence or an uncertain result with HR "
                    "before deciding next steps.",
                    "record": "Named owner, next action and follow-up date, where applicable.",
                }
            ],
        ),
        (
            "Official sources",
            [
                {
                    "employer_guide": "https://www.gov.uk/government/publications/right-to-work-checks-employers-guide",
                    "check_service": "https://www.gov.uk/check-job-applicant-right-to-work",
                    "checked_on": "03 Nov 2026",
                }
            ],
        ),
    ]
    html = record_html(
        "Right to Work checklist",
        datetime.now(UTC).strftime("%d %b %Y %H:%M UTC"),
        sections,
        report_title="Original working checklist",
        notice="Use alongside the current GOV.UK guidance and record the evidence "
        "in the employee's Right to Work tab.",
    )
    pdf = await asyncio.to_thread(render_pdf, html)
    await access.audit("compliance.checklist_downloaded", entity_type="dossier")
    await access.db.commit()
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="right-to-work-checklist.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
