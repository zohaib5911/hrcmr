"""A dated inspection record, rendered from escaped text with sensitive values already masked."""

from __future__ import annotations

import asyncio
import uuid  # noqa: TC003
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from jinja2 import Environment

from app.core.rbac_matrix import scope_for
from app.modules.employees.compensation_router import compensation_history
from app.modules.employees.document_router import list_documents
from app.modules.employees.employment_router import employment_tab
from app.modules.employees.personal_router import _tab
from app.modules.employees.router import _employee, _profile
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["employees"])
Reports = Annotated[Access, Depends(require("document.report.generate"))]


def _rows(record: dict[str, Any]) -> list[tuple[str, str]]:
    """Only scalar presentation data enters the template; IDs and internal flags are omitted."""
    result = []
    for key, value in record.items():
        if key == "id" or key.endswith("_id") or key in {"sensitive_visible", "has_photo"}:
            continue
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            continue
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        result.append(
            (key.replace("_", " ").capitalize(), str(value) if value is not None else "Not set")
        )
    return result


def record_html(
    name: str,
    generated: str,
    sections: list[tuple[str, list[dict[str, Any]]]],
    *,
    report_title: str = "Employee record",
    notice: str = (
        "National Insurance, passport and bank numbers are masked. "
        "Salary is included only when the requester may read compensation."
    ),
) -> str:
    # FastAPI has no Flask render_template. Record values are escaped (test_employee_pdf.py);
    # this trusted local template cannot fetch resources in the PDF renderer.
    # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
    template = Environment(autoescape=True).from_string(
        Path(__file__).with_name("record.html").read_text()
    )
    return template.render(
        name=name,
        report_title=report_title,
        notice=notice,
        generated=generated,
        sections=[(title, [_rows(record) for record in records]) for title, records in sections],
    )


def _no_resources(url: str, *args: object, **kwargs: object) -> Any:
    """The text-only report needs no file, HTTP, data or other external resources."""
    raise ValueError("External resources are not allowed in employee PDFs.")


def render_pdf(html: str) -> bytes:
    # Lazy import: OpenAPI/type generation and startup need no native PDF libraries.
    from weasyprint import HTML

    result: bytes = HTML(string=html, url_fetcher=_no_resources).write_pdf()
    return result


@router.get(
    "/employees/{employee_id}/record.pdf",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Masked employee inspection record",
        }
    },
)
async def employee_pdf(employee_id: uuid.UUID, access: Reports) -> Response:
    employee = await _employee(access, employee_id)
    profile = (await _profile(access, employee)).model_dump(mode="json")
    personal = (await _tab(access, employee)).model_dump(mode="json")
    employment = (await employment_tab(employee_id, access)).model_dump(mode="json")
    sections: list[tuple[str, list[dict[str, Any]]]] = [
        ("Record", [profile]),
        ("Personal details", [personal["details"]]),
    ]
    for key, title in [
        ("address", "Correspondence address"),
        ("identity", "National Insurance and passport (masked)"),
        ("bank", "Bank details (masked)"),
    ]:
        sections.append((title, [personal[key]] if personal[key] else []))
    sections.append(("Emergency contacts", personal["contacts"]))
    for key, title in [
        ("assignments", "Role history"),
        ("responsibilities", "Key responsibilities"),
        ("education", "Education"),
        ("training", "Training"),
        ("memberships", "Certified memberships"),
    ]:
        sections.append((title, employment[key]))
    previous = employment["previous_employment"]
    sections.append(("Previous employment", [previous] if previous else []))
    if scope_for(access.role, "employee.compensation.read") is not None:
        salary = await compensation_history(employee_id, access)
        sections.append(("Salary history", [r.model_dump(mode="json") for r in salary.records]))
    if scope_for(access.role, "document.file.read") is not None:
        documents = await list_documents(employee_id, access)
        sections.append(("Documents", [d.model_dump(mode="json") for d in documents]))
    generated = datetime.now(UTC).strftime("%d %b %Y %H:%M UTC")
    html = record_html(f"{employee.first_name} {employee.last_name}", generated, sections)
    pdf = await asyncio.to_thread(render_pdf, html)
    await access.audit("employee.record_exported", entity_type="employee", entity_id=employee.id)
    await access.db.commit()
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="employee-{employee.id}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
