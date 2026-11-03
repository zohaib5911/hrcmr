"""Serialized own daily writes and retained, reasoned administrative changes."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import scope_for
from app.modules.attendance.router import _company
from app.modules.employees.models import Employee, EmployeeResponsibility
from app.modules.work_log.models import WorkLogEntry
from app.modules.work_log.schemas import OwnResponsibility, WorkLogIn, WorkLogOut

if TYPE_CHECKING:
    from app.modules.rbac.deps import Access


def now() -> datetime:
    return datetime.now(UTC)


async def today(access: Access) -> date:
    return now().astimezone(ZoneInfo((await _company(access)).timezone)).date()


async def own_employee(access: Access) -> Employee:
    if access.employee_id is None:
        raise ForbiddenError("Your account needs a linked employee record to add work log entries.")
    row = (
        await access.db.execute(
            select(Employee).where(Employee.id == access.employee_id).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


async def locked_entry(
    access: Access, ident: uuid.UUID, *, own: bool = False
) -> tuple[WorkLogEntry, Employee]:
    row = (
        await access.db.execute(select(WorkLogEntry).where(WorkLogEntry.id == ident))
    ).scalar_one_or_none()
    if (
        row is None
        or (own and row.employee_id != access.employee_id)
        or not await access.can_reach(row.employee_id)
    ):
        raise NotFoundError
    employee = (
        await access.db.execute(
            select(Employee).where(Employee.id == row.employee_id).with_for_update()
        )
    ).scalar_one()
    row = (
        await access.db.execute(
            select(WorkLogEntry)
            .where(WorkLogEntry.id == ident)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    return row, employee


def revision(row: WorkLogEntry, expected: datetime) -> None:
    if expected.tzinfo is None or row.updated_at != expected:
        raise ConflictError("This entry changed. Reload it and review your changes again.")


def snapshot(row: WorkLogEntry) -> dict[str, Any]:
    return {
        "date": row.date.isoformat(),
        "from_time": row.from_time.isoformat(),
        "to_time": row.to_time.isoformat(),
        "hours": str(row.hours),
        "responsibility_id": str(row.responsibility_id) if row.responsibility_id else None,
        "responsibility_text": row.responsibility_text,
        "description": row.description,
    }


def audit_snapshot(row: WorkLogEntry) -> dict[str, Any]:
    result = snapshot(row)
    result.pop("responsibility_text")
    result.pop("description")
    return {"entry_id": str(row.id), **result}


async def apply(
    access: Access,
    employee: Employee,
    body: WorkLogIn,
    row: WorkLogEntry | None = None,
    *,
    own: bool = False,
) -> WorkLogEntry:
    on = await today(access)
    if (
        body.date > on
        or body.date < employee.hire_date
        or (employee.leave_date and body.date > employee.leave_date)
    ):
        raise AppError(
            "VALIDATION_ERROR",
            "Choose a past or current date within this employee's employment.",
            status_code=422,
            field="date",
        )
    if own and employee.status == "archived":
        raise ForbiddenError("Archived employees cannot add or edit work log entries.")
    if row is not None and row.removed_at is not None:
        raise ConflictError("Removed work log entries cannot be changed.")
    if own and row is not None and (row.date != on or body.date != on):
        raise ForbiddenError(
            "You can edit entries on their work date only. "
            "Ask an administrator to correct an older entry."
        )
    if body.responsibility_id is not None:
        responsibility = (
            await access.db.execute(
                select(EmployeeResponsibility).where(
                    EmployeeResponsibility.id == body.responsibility_id,
                    EmployeeResponsibility.employee_id == employee.id,
                )
            )
        ).scalar_one_or_none()
        if responsibility is None:
            raise NotFoundError
        responsibility_text = str(
            OwnResponsibility.model_validate(responsibility).model_dump()["text"]
        )
    else:
        responsibility_text = body.responsibility_text or ""
    if row is None:
        row = WorkLogEntry(company_id=access.company_id, employee_id=employee.id)
        access.db.add(row)
    minutes = (
        body.to_time.hour * 60
        + body.to_time.minute
        - body.from_time.hour * 60
        - body.from_time.minute
    ) % 1440
    row.date, row.from_time, row.to_time = body.date, body.from_time, body.to_time
    row.hours = (Decimal(minutes) / 60).quantize(Decimal("0.01"))
    row.responsibility_id, row.responsibility_text = body.responsibility_id, responsibility_text
    row.description = body.description
    await access.db.flush()
    return row


def out(row: WorkLogEntry, employee: Employee, access: Access, on: date) -> WorkLogOut:
    return WorkLogOut(
        id=row.id,
        employee_id=employee.id,
        employee_name=f"{employee.first_name} {employee.last_name}",
        date=row.date,
        from_time=row.from_time,
        to_time=row.to_time,
        hours=row.hours,
        responsibility_id=row.responsibility_id,
        responsibility_text=row.responsibility_text,
        description=row.description,
        removed_at=row.removed_at,
        corrected_from=row.corrected_from,
        can_edit=row.employee_id == access.employee_id
        and row.date == on
        and row.removed_at is None
        and employee.status != "archived"
        and scope_for(access.role, "work_log.entry.write_own") is not None,
        revision=row.updated_at,
    )
