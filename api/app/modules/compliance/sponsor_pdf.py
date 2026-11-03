"""Dated employee sponsor record; reuse the scoped, masked presentation serializers."""

from __future__ import annotations

import asyncio
import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app.modules.companies.router import _company
from app.modules.compliance.reference import CHANGE_TYPES
from app.modules.compliance.router import employee_changes
from app.modules.employees.record_pdf import record_html, render_pdf
from app.modules.employees.router import _employee
from app.modules.rbac.deps import Access, require
from app.modules.rtw.router import checks
from app.modules.sponsor_documents.reference import DOCUMENT_TYPES, VISA_ROUTES
from app.modules.sponsor_documents.router import documents

router = APIRouter(tags=["compliance-records"])
Reports = Annotated[Access, Depends(require("document.report.generate"))]


@router.get(
    "/employees/{employee_id}/sponsor-record.pdf",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Masked employee sponsor compliance record",
        }
    },
)
async def sponsor_pdf(employee_id: uuid.UUID, access: Reports) -> Response:
    employee = await _employee(access, employee_id)
    company = await _company(access)
    rtw = await checks(employee_id, access)
    docs = await documents(employee_id, access)
    changes = await employee_changes(employee_id, access)
    sections: list[tuple[str, list[dict[str, Any]]]] = [
        (
            "Employee and current Right to Work",
            [
                {
                    "company": company.name,
                    "employee_number": employee.employee_number,
                    "employee_status": employee.status,
                    "rtw_status": rtw.status,
                    "follow_up_due_on": rtw.follow_up_due_on,
                }
            ],
        ),
        (
            "Sponsor documents (all retained versions)",
            [
                {
                    **doc.model_dump(
                        mode="json",
                        exclude={
                            "id",
                            "evidence_file_id",
                            "superseded_by",
                            "doc_type",
                            "visa_route",
                        },
                    ),
                    "document": dict(DOCUMENT_TYPES)[doc.doc_type],
                    "visa_route": dict(VISA_ROUTES).get(doc.visa_route) if doc.visa_route else None,
                }
                for doc in docs
            ],
        ),
        (
            "Right to Work check history",
            [
                check.model_dump(
                    mode="json",
                    exclude={
                        "id",
                        "checked_by_user_id",
                        "evidence_file_id",
                        "superseded_by",
                        "corrected_from_id",
                        "can_correct",
                    },
                )
                for check in rtw.checks
            ],
        ),
        (
            "Change of circumstances (entered snapshots and reporting)",
            [
                {
                    **change.model_dump(
                        mode="json",
                        exclude={
                            "id",
                            "employee_id",
                            "employee_name",
                            "employee_number",
                            "reported_by_user_id",
                            "documents_snapshot",
                            "documents",
                            "change_type",
                            "calendar_holidays",
                        },
                    ),
                    "change": dict(CHANGE_TYPES)[change.change_type],
                    "documents_at_event": [
                        f"{dict(DOCUMENT_TYPES)[doc.doc_type]} · version {doc.version}"
                        for doc in change.documents
                    ],
                }
                for change in changes
            ],
        ),
    ]
    generated = datetime.now(UTC).strftime("%d %b %Y %H:%M UTC")
    html = record_html(
        f"{employee.first_name} {employee.last_name}",
        generated,
        sections,
        report_title="Sponsor compliance record",
        notice="Document references, CoS numbers and share codes are masked. "
        "Salary is included only when the requester may read compensation. "
        "Historical versions and entered change snapshots are retained.",
    )
    pdf = await asyncio.to_thread(render_pdf, html)
    await access.audit(
        "employee.sponsor_record_exported", entity_type="employee", entity_id=employee_id
    )
    await access.db.commit()
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="sponsor-record-{employee_id}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
