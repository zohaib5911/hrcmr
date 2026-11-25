"""Scanned attendance imports: bounded preview, row errors and stale-safe atomic commit."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid  # noqa: TC003
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import select

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope
from app.db.ids import uuid7
from app.modules.attendance.batch_schemas import AttendanceImportOut, ImportRowOut
from app.modules.attendance.models import AttendanceImport, AttendanceRecord
from app.modules.attendance.router import Writes, _company
from app.modules.attendance.schemas import AttendanceIn
from app.modules.attendance.service import check_replaceable, save_record, times
from app.modules.attendance.workbooks import (
    HEADERS,
    MAX_BYTES,
    ParsedRow,
    csv_bytes,
    parse_rows,
    xlsx_bytes,
)
from app.modules.employees.models import Employee
from app.modules.files.models import File

if TYPE_CHECKING:
    from app.modules.files.service import FileService
    from app.modules.rbac.deps import Access

router = APIRouter(prefix="/attendance/import", tags=["attendance"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _full(access: Access) -> None:
    if access.scope is not Scope.ALL:
        raise ForbiddenError("Attendance imports need company-wide attendance write access.")


def _code(value: str) -> str:
    return "".join(value.split()).lower()


def _input(row: ParsedRow, employee: Employee) -> AttendanceIn:
    raw = row.values
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw["date"].strip()):
        raise ValueError("Use a date in YYYY-MM-DD format.")
    for field in ("clock_in", "clock_out"):
        if raw[field].strip() and not re.fullmatch(r"\d{2}:\d{2}", raw[field].strip()):
            raise ValueError("Clock times must use HH:MM.")
    pause = raw.get("unpaid_break_minutes", "").strip() or "0"
    if not pause.isascii() or not pause.isdigit():
        raise ValueError("Unpaid break minutes must be a whole number.")
    folds = {}
    for field in ("clock_in", "clock_out"):
        occurrence = raw.get(field + "_occurrence", "").strip().lower()
        if occurrence not in ("", "first", "second"):
            raise ValueError("Repeated-hour occurrences must be first or second.")
        folds[field + "_fold"] = {"": None, "first": 0, "second": 1}[occurrence]
    return AttendanceIn.model_validate(
        {
            "employee_id": employee.id,
            "date": date.fromisoformat(raw["date"].strip()),
            "status": raw["status"].strip().lower().replace(" ", "_").replace("-", "_"),
            "clock_in": raw["clock_in"].strip() or None,
            "clock_out": raw["clock_out"].strip() or None,
            "note": raw["note"],
            "unpaid_break_minutes": int(pause),
            **folds,
        }
    )


def _fingerprint(employee: Employee, existing: AttendanceRecord | None) -> str:
    values = {
        "employee_id": str(employee.id),
        "name": [employee.first_name, employee.last_name],
        "number": employee.employee_number,
        "hire": employee.hire_date.isoformat(),
        "leave": employee.leave_date.isoformat() if employee.leave_date else None,
        "status": employee.status,
        "record_id": str(existing.id) if existing else None,
        "record_updated": existing.updated_at.isoformat() if existing else None,
    }
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


async def _existing(access: Access, employee_id: uuid.UUID, day: date) -> AttendanceRecord | None:
    return (
        await access.db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == employee_id, AttendanceRecord.date == day
            )
        )
    ).scalar_one_or_none()


def _employment(employee: Employee, day: date) -> None:
    if (
        employee.status == "archived"
        or day < employee.hire_date
        or (employee.leave_date is not None and day > employee.leave_date)
    ):
        raise ValueError(
            "Choose a date within this employee's employment; archived records cannot be changed."
        )


def _out(row: AttendanceImport, file: File) -> AttendanceImportOut:
    return AttendanceImportOut(
        id=row.id,
        filename=file.original_name,
        status=row.status,
        from_date=row.from_date,
        to_date=row.to_date,
        rows_total=row.rows_total,
        rows_valid=row.rows_valid,
        rows=[ImportRowOut.model_validate(r) for r in row.rows],
        committed_at=row.committed_at,
    )


@router.get(
    "/template.csv", response_class=Response, responses={200: {"content": {"text/csv": {}}}}
)
async def csv_template(access: Writes) -> Response:
    _full(access)
    return Response(
        csv_bytes(HEADERS, []),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="attendance-template.csv"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/template.xlsx", response_class=Response, responses={200: {"content": {XLSX: {}}}})
async def xlsx_template(access: Writes) -> Response:
    _full(access)
    content = await asyncio.to_thread(xlsx_bytes, HEADERS, [], template=True)
    return Response(
        content,
        media_type=XLSX,
        headers={
            "Content-Disposition": 'attachment; filename="attendance-template.xlsx"',
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/preview", response_model=AttendanceImportOut, status_code=201)
async def preview(file: UploadFile, request: Request, access: Writes) -> AttendanceImportOut:
    _full(access)
    ident = uuid7()
    files: FileService = request.app.state.files
    stored = await files.upload(
        access,
        file.file,
        filename=file.filename,
        owner_type="attendance_import",
        owner_id=ident,
        category="attendance_import",
        kinds=frozenset({"csv", "xlsx"}),
        max_bytes=MAX_BYTES,
        commit=False,
    )
    await file.seek(0)
    parsed = await asyncio.to_thread(
        parse_rows, await file.read(MAX_BYTES + 1), xlsx=stored.mime == XLSX
    )
    company = await _company(access)
    people: dict[str, list[Employee]] = {}
    for employee in (await access.db.execute(select(Employee))).scalars():
        people.setdefault(_code(employee.employee_number), []).append(employee)
    reviewed: list[dict[str, Any]] = []
    seen: dict[tuple[uuid.UUID, date], int] = {}
    for source in parsed:
        result: dict[str, Any] = {
            "number": source.number,
            "values": source.values,
            "employee_name": None,
            "action": None,
            "errors": [],
        }
        reviewed.append(result)
        if source.error:
            result["errors"].append(source.error)
            continue
        matches = people.get(_code(source.values["employee_number"]), [])
        if len(matches) != 1:
            result["errors"].append("Employee number was not found uniquely in this company.")
            continue
        employee = matches[0]
        result["employee_name"] = f"{employee.first_name} {employee.last_name}"
        try:
            body = _input(source, employee)
            _employment(employee, body.date)
            times(body, ZoneInfo(company.timezone))
            existing = await _existing(access, employee.id, body.date)
            check_replaceable(existing, "import")
            result.update(
                input=body.model_dump(mode="json"),
                expected=_fingerprint(employee, existing),
                action="update" if existing else "create",
            )
            key = (employee.id, body.date)
            if key in seen:
                result["errors"].append("This employee and date appear more than once.")
                reviewed[seen[key]]["errors"].append(
                    "This employee and date appear more than once."
                )
            else:
                seen[key] = len(reviewed) - 1
        except ValidationError as error:
            result["errors"].extend(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                for e in error.errors(include_input=False)
            )
        except (ValueError, AppError) as error:
            result["errors"].append(error.message if isinstance(error, AppError) else str(error))
    valid_dates = [date.fromisoformat(r["input"]["date"]) for r in reviewed if "input" in r]
    row = AttendanceImport(
        id=ident,
        company_id=access.company_id,
        file_id=stored.id,
        from_date=min(valid_dates) if valid_dates else None,
        to_date=max(valid_dates) if valid_dates else None,
        rows_total=len(reviewed),
        rows_valid=sum(not r["errors"] for r in reviewed),
        rows=reviewed,
        errors=[{"row": r["number"], "errors": r["errors"]} for r in reviewed if r["errors"]],
        timezone=company.timezone,
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "attendance.import_previewed",
        entity_type="attendance_import",
        entity_id=row.id,
        after={"rows": row.rows_total, "valid": row.rows_valid, "file_id": str(stored.id)},
    )
    await access.db.commit()
    return _out(row, stored)


async def _load(
    access: Access, ident: uuid.UUID, *, lock: bool = False
) -> tuple[AttendanceImport, File]:
    query = select(AttendanceImport).where(AttendanceImport.id == ident)
    if lock:
        query = query.with_for_update()
    row = (await access.db.execute(query)).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    file = (
        await access.db.execute(select(File).where(File.id == row.file_id))
    ).scalar_one_or_none()
    if (
        file is None
        or file.scan_status != "clean"
        or file.owner_type != "attendance_import"
        or file.owner_id != row.id
    ):
        raise NotFoundError
    return row, file


@router.get("/{import_id}", response_model=AttendanceImportOut)
async def read_preview(import_id: uuid.UUID, access: Writes) -> AttendanceImportOut:
    _full(access)
    row, file = await _load(access, import_id)
    return _out(row, file)


@router.post("/{import_id}/commit", response_model=AttendanceImportOut)
async def commit(import_id: uuid.UUID, access: Writes) -> AttendanceImportOut:
    _full(access)
    row, file = await _load(access, import_id, lock=True)
    if row.status == "committed":
        return _out(row, file)
    if row.rows_valid != row.rows_total:
        raise ConflictError("Fix all row errors and upload a new preview before committing.")
    company = await _company(access)
    if company.timezone != row.timezone:
        raise ConflictError("The company time zone changed. Upload and review the file again.")
    bodies = [AttendanceIn.model_validate(r["input"]) for r in row.rows]
    ids = {b.employee_id for b in bodies}
    people = {
        p.id: p
        for p in (
            await access.db.execute(
                select(Employee).where(Employee.id.in_(ids)).order_by(Employee.id).with_for_update()
            )
        ).scalars()
    }
    for saved, body in zip(row.rows, bodies, strict=True):
        employee = people.get(body.employee_id)
        if employee is None or saved["expected"] != _fingerprint(
            employee, await _existing(access, body.employee_id, body.date)
        ):
            raise ConflictError(
                "Employee details or attendance changed after preview. "
                "Upload and review the file again."
            )
    for body in bodies:
        await save_record(access, body, source="import")
    row.status = "committed"
    row.committed_at = datetime.now(UTC)
    await access.audit(
        "attendance.import_committed",
        entity_type="attendance_import",
        entity_id=row.id,
        after={"rows": len(bodies)},
    )
    await access.db.commit()
    return _out(row, file)
