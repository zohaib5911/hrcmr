"""Certificates for completed courses, and the public check that finds one by reference.

A reference is 12 characters from ``secrets``, with no look-alike letters, so it cannot be guessed
in practice. The public check sets that one reference for its own transaction, and the database
policy then shows only the certificate with that reference. Nothing else is opened up.
"""

from __future__ import annotations

import asyncio
import secrets
import uuid  # noqa: TC003
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Request, Response
from jinja2 import Environment
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.errors import AppError, NotFoundError
from app.core.rate_limit import RateLimiter
from app.core.rbac_matrix import Scope
from app.db.ids import uuid7
from app.db.session import GlobalDb  # noqa: TC001
from app.modules.auth.deps import client_ip
from app.modules.employees.models import Employee
from app.modules.employees.record_pdf import render_pdf
from app.modules.learning.models import Certificate, Course, CourseAssignment
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0, O, 1 or I
REFERENCE_LENGTH = 12
VERIFY_LIMIT = 30  # checks per connection...
VERIFY_WINDOW_SECONDS = 600  # ...in ten minutes

router = APIRouter(tags=["learning"])
CertReads = Annotated[Access, Depends(require("learning.certificate.read"))]
OwnReads = Annotated[Access, Depends(require("learning.assignment.read_own"))]


class CertificateCheckOut(BaseModel):
    """Only these four fields. Nothing else about the person or the company is ever returned."""

    holder_name: str
    course_title: str
    completed_on: date
    status: str


class CertificateRefOut(BaseModel):
    id: uuid.UUID
    reference: str


def new_reference() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(REFERENCE_LENGTH))


async def issue(db: AsyncSession, assignment: CourseAssignment, course: Course) -> Certificate:
    """The certificate for a course just completed. The names are copied, so they stay put."""
    first, last = (
        await db.execute(
            select(Employee.first_name, Employee.last_name).where(
                Employee.id == assignment.employee_id
            )
        )
    ).one()
    completed = (assignment.completed_at or assignment.updated_at).date()
    certificate = Certificate(
        id=uuid7(),
        company_id=assignment.company_id,
        assignment_id=assignment.id,
        reference=new_reference(),
        holder_name_snapshot=f"{first} {last}".strip(),
        course_title_snapshot=course.title,
        completed_on=completed,
        issued_on=completed,
    )
    db.add(certificate)
    await db.flush()
    return certificate


def certificate_html(certificate: Certificate, verify_url: str, generated: str) -> str:
    # Trusted local template; every value is escaped by autoescape (as for employee records).
    # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
    template = Environment(autoescape=True).from_string(
        Path(__file__).with_name("certificate.html").read_text(encoding="utf-8")
    )
    return template.render(
        holder=certificate.holder_name_snapshot,
        course=certificate.course_title_snapshot,
        completed_on=certificate.completed_on.strftime("%d %B %Y"),
        reference=certificate.reference,
        verify_url=verify_url,
        generated=generated,
    )


@router.get("/learning/assignments/{assignment_id}/certificate", response_model=CertificateRefOut)
async def assignment_certificate(assignment_id: uuid.UUID, access: OwnReads) -> CertificateRefOut:
    if access.employee_id is None:
        raise NotFoundError
    row = (
        await access.db.execute(
            select(Certificate)
            .join(CourseAssignment, CourseAssignment.id == Certificate.assignment_id)
            .where(
                CourseAssignment.id == assignment_id,
                CourseAssignment.employee_id == access.employee_id,
                Certificate.company_id == access.company_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return CertificateRefOut(id=row.id, reference=row.reference)


@router.get(
    "/certificates/{certificate_id}.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "A course certificate"}},
)
async def certificate_pdf(
    certificate_id: uuid.UUID, request: Request, access: CertReads
) -> Response:
    row = (
        await access.db.execute(
            select(Certificate, CourseAssignment)
            .join(CourseAssignment, CourseAssignment.id == Certificate.assignment_id)
            .where(Certificate.id == certificate_id, Certificate.company_id == access.company_id)
        )
    ).first()
    if row is None:
        raise NotFoundError
    certificate, assignment = row
    # Someone who may only see their own certificates gets "not found" for anyone else's.
    if access.scope is not Scope.ALL and assignment.employee_id != access.employee_id:
        raise NotFoundError
    origin = request.app.state.settings.web_origin
    html = certificate_html(
        certificate,
        verify_url=f"{origin}/verify?ref={certificate.reference}",
        generated=datetime.now(UTC).strftime("%d %B %Y"),
    )
    pdf = await asyncio.to_thread(render_pdf, html)
    await access.audit(
        "learning.certificate_downloaded", entity_type="certificate", entity_id=certificate.id
    )
    await access.db.commit()
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{certificate.reference}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/public/certificates/verify", response_model=CertificateCheckOut)
async def verify_certificate(ref: str, request: Request, db: GlobalDb) -> CertificateCheckOut:
    """Anyone can check a certificate by its reference. Limited per connection, and unknown
    references get the same plain answer whatever the reason."""
    name = "certificate_verify"
    result = await RateLimiter(request.app.state.auth.redis).hit(
        name,
        client_ip(request) or "unknown",
        limit=VERIFY_LIMIT,
        window_seconds=VERIFY_WINDOW_SECONDS,
    )
    if not result.allowed:
        raise AppError(
            "RATE_LIMITED",
            "Too many checks from this connection. Try again later.",
            status_code=429,
        )
    if not (10 <= len(ref) <= 20):
        raise NotFoundError("We could not find a certificate with that reference.")
    # One transaction, one reference: the database policy shows only the certificate with it.
    await db.execute(select(func.set_config("app.certificate_ref", ref, True)))
    row = (
        await db.execute(
            select(
                Certificate.holder_name_snapshot,
                Certificate.course_title_snapshot,
                Certificate.completed_on,
            ).where(Certificate.reference == ref)
        )
    ).first()
    if row is None:
        raise NotFoundError("We could not find a certificate with that reference.")
    holder, course, completed = row
    return CertificateCheckOut(
        holder_name=holder, course_title=course, completed_on=completed, status="valid"
    )
