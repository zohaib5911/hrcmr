"""Scoped bulk attendance, spreadsheet/PDF reports and recorded monthly absences."""

from __future__ import annotations

import asyncio
import uuid  # noqa: TC003
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response
from jinja2 import Environment
from sqlalchemy import select

from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope, scope_for
from app.modules.attendance.batch_schemas import AbsenceOut, GridIn, GridOut, GridPerson, GridSaved
from app.modules.attendance.models import AttendanceRecord
from app.modules.attendance.router import Reads, Writes, _company, _ids, _out
from app.modules.attendance.schemas import AttendanceStatus  # noqa: TC001
from app.modules.attendance.service import save_record
from app.modules.attendance.workbooks import xlsx_bytes
from app.modules.employees.models import Employee
from app.modules.employees.record_pdf import render_pdf
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from app.modules.companies.models import Company

router = APIRouter(prefix="/attendance", tags=["attendance"])
Exports = Annotated[Access, Depends(require("document.report.generate"))]
ABSENCES = ("absent", "sick", "on_leave", "half_day")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/grid", response_model=GridOut)
async def grid(
    access: Reads,
    start: date,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> GridOut:
    try:
        end = start + timedelta(days=6)
    except OverflowError as error:
        raise AppError("VALIDATION_ERROR", "Choose a valid week.", status_code=422) from error
    ids = await _ids(access, None, own=False)
    query = (
        select(Employee)
        .where(
            Employee.status != "archived",
            Employee.hire_date <= end,
            Employee.leave_date.is_(None) | (Employee.leave_date >= start),
        )
        .order_by(Employee.last_name, Employee.first_name, Employee.id)
    )
    if ids is not None:
        query = query.where(Employee.id.in_(ids))
    people = list((await access.db.execute(query.offset(offset).limit(limit + 1))).scalars())
    selected = people[:limit]
    records = list(
        (
            await access.db.execute(
                select(AttendanceRecord)
                .where(
                    AttendanceRecord.employee_id.in_([p.id for p in selected]),
                    AttendanceRecord.date >= start,
                    AttendanceRecord.date <= end,
                )
                .order_by(AttendanceRecord.date)
            )
        ).scalars()
    )
    company = await _company(access)
    by_id = {p.id: p for p in selected}
    return GridOut(
        start=start,
        end=end,
        timezone=company.timezone,
        people=[
            GridPerson(
                id=p.id,
                name=f"{p.first_name} {p.last_name}",
                employee_number=p.employee_number,
                hire_date=p.hire_date,
                leave_date=p.leave_date,
            )
            for p in selected
        ],
        records=[_out(r, by_id[r.employee_id], ZoneInfo(company.timezone)) for r in records],
        next_offset=offset + limit if len(people) > limit else None,
    )


@router.put("/grid", response_model=GridSaved)
async def save_grid(body: GridIn, access: Writes) -> GridSaved:
    if access.scope is not Scope.ALL:
        raise ForbiddenError("Bulk attendance entry needs company-wide write access.")
    keys = {(r.employee_id, r.date) for r in body.rows}
    if len(keys) != len(body.rows):
        raise AppError("VALIDATION_ERROR", "Use one entry per employee and date.", status_code=422)
    ids = {r.employee_id for r in body.rows}
    found = set(
        (
            await access.db.execute(
                select(Employee.id)
                .where(Employee.id.in_(ids))
                .order_by(Employee.id)
                .with_for_update()
            )
        ).scalars()
    )
    if found != ids:
        raise NotFoundError
    for row in body.rows:
        await save_record(access, row, source="grid")
    await access.audit("attendance.grid_saved", after={"rows": len(body.rows)})
    await access.db.commit()
    return GridSaved(count=len(body.rows))


def _export_scope(access: Access) -> Access:
    scope = scope_for(access.role, "attendance.record.read")
    if scope is None:
        raise ForbiddenError
    return replace(access, permission="attendance.record.read", scope=scope)


async def _report_rows(
    access: Access,
    start: date,
    end: date,
    employee_id: uuid.UUID | None,
    status: AttendanceStatus | None = None,
    *,
    absences_only: bool = False,
    limit: int = 50_000,
) -> tuple[Company, list[tuple[AttendanceRecord, Employee]]]:
    if end < start or (end - start).days > 366:
        raise AppError(
            "VALIDATION_ERROR", "Choose a date range of up to one year.", status_code=422
        )
    ids = await _ids(access, employee_id, own=False)
    query = (
        select(AttendanceRecord, Employee)
        .join(Employee, Employee.id == AttendanceRecord.employee_id)
        .where(AttendanceRecord.date >= start, AttendanceRecord.date <= end)
    )
    if ids is not None:
        query = query.where(AttendanceRecord.employee_id.in_(ids))
    if status is not None:
        query = query.where(AttendanceRecord.status == status)
    if absences_only:
        query = query.where(AttendanceRecord.status.in_(ABSENCES))
    rows = [
        (r, e)
        for r, e in (
            await access.db.execute(
                query.order_by(AttendanceRecord.date, Employee.last_name, Employee.id).limit(
                    limit + 1
                )
            )
        ).all()
    ]
    if len(rows) > limit:
        raise AppError(
            "REPORT_TOO_LARGE",
            "Choose a shorter date range or one employee for this report.",
            status_code=422,
        )
    return await _company(access), rows


async def _export_audit(access: Access, start: date, end: date, count: int, kind: str) -> None:
    await access.audit(
        "attendance.exported",
        after={"start": start.isoformat(), "end": end.isoformat(), "rows": count, "format": kind},
    )
    await access.db.commit()


@router.get("/export.xlsx", response_class=Response, responses={200: {"content": {XLSX: {}}}})
async def export_xlsx(
    access: Exports,
    start: date,
    end: date,
    employee_id: uuid.UUID | None = None,
    status: AttendanceStatus | None = None,
    absences_only: bool = False,
) -> Response:
    scoped = _export_scope(access)
    company, rows = await _report_rows(
        scoped, start, end, employee_id, status, absences_only=absences_only
    )
    values = []
    for record, employee in rows:
        row = _out(record, employee, ZoneInfo(company.timezone))
        values.append(
            [
                employee.employee_number,
                row.employee_name,
                row.date.isoformat(),
                row.status.replace("_", " ").capitalize(),
                row.clock_in_local,
                row.clock_out_local,
                row.unpaid_break_minutes,
                float(row.hours) if row.hours is not None else None,
                row.note,
                row.source,
            ]
        )
    content = await asyncio.to_thread(
        xlsx_bytes,
        [
            "Employee number",
            "Employee",
            "Date",
            "Status",
            "Clock in",
            "Clock out",
            "Break (minutes)",
            "Hours",
            "Note",
            "Source",
        ],
        values,
    )
    await _export_audit(access, start, end, len(rows), "xlsx")
    return Response(
        content,
        media_type=XLSX,
        headers={
            "Content-Disposition": f'attachment; filename="attendance-{start}-{end}.xlsx"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/export.pdf", response_class=Response, responses={200: {"content": {"application/pdf": {}}}}
)
async def export_pdf(
    access: Exports,
    start: date,
    end: date,
    employee_id: uuid.UUID | None = None,
    status: AttendanceStatus | None = None,
    absences_only: bool = False,
) -> Response:
    scoped = _export_scope(access)
    company, rows = await _report_rows(
        scoped, start, end, employee_id, status, absences_only=absences_only, limit=1000
    )
    records = [_out(r, e, ZoneInfo(company.timezone)) for r, e in rows]
    # Trusted local template and escaped values; the renderer refuses external resources.
    # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
    template = Environment(autoescape=True).from_string(
        Path(__file__).with_name("report.html").read_text()
    )
    html = template.render(
        company=company.name,
        start=start.isoformat(),
        end=end.isoformat(),
        timezone=company.timezone,
        generated=datetime.now(UTC).isoformat(),
        rows=records,
    )
    content = await asyncio.to_thread(render_pdf, html)
    await _export_audit(access, start, end, len(rows), "pdf")
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="attendance-{start}-{end}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/absences", response_model=AbsenceOut)
async def absences(
    access: Reads, month: Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
) -> AbsenceOut:
    try:
        start = date.fromisoformat(month + "-01")
        end = date(start.year + (start.month == 12), start.month % 12 + 1, 1) - timedelta(days=1)
    except ValueError as error:
        raise AppError("VALIDATION_ERROR", "Choose a valid month.", status_code=422) from error
    company, rows = await _report_rows(access, start, end, None, absences_only=True)
    records = [_out(r, e, ZoneInfo(company.timezone)) for r, e in rows]
    return AbsenceOut(
        month=month,
        days=sum(
            (Decimal("0.5") if r.status == "half_day" else Decimal(1) for r in records), Decimal(0)
        ),
        employees=len({r.employee_id for r in records}),
        records=records,
        timezone=company.timezone,
    )
