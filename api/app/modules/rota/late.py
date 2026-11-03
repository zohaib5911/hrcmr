"""Clock lateness uses the employee-visible schedule and dated department/job policy."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.modules.employees.models import EmployeeAssignment
from app.modules.rota.models import LatePolicy
from app.modules.rota.week_models import RotaWeek

if TYPE_CHECKING:
    from app.modules.companies.models import Company
    from app.modules.employees.models import Employee
    from app.modules.rbac.deps import Access


async def clock_status(
    access: Access, company: Company, employee: Employee, instant: datetime
) -> Literal["present", "late"]:
    local = instant.astimezone(ZoneInfo(company.timezone)).date()
    start = local - timedelta(days=local.weekday())
    previous = start - timedelta(days=7) if start.toordinal() > 7 else start
    weeks = list(
        (
            await access.db.execute(
                select(RotaWeek).where(
                    RotaWeek.week_start <= start,
                    RotaWeek.week_start >= previous,
                    RotaWeek.published_at.is_not(None),
                )
            )
        ).scalars()
    )
    shifts = [
        s
        for week in weeks
        for s in week.published_shifts
        if s["employee_id"] == str(employee.id)
        and (
            s["date"] == local.isoformat()
            or datetime.fromisoformat(s["starts_at"])
            <= instant
            <= datetime.fromisoformat(s["ends_at"])
        )
    ]
    if not shifts:
        return "present"
    shift = min(
        shifts,
        key=lambda s: abs((instant - datetime.fromisoformat(s["starts_at"])).total_seconds()),
    )
    if shift["shift_type_id"] is None:
        return "present"
    scheduled_date = date.fromisoformat(shift["date"])
    assignment = (
        await access.db.execute(
            select(EmployeeAssignment).where(
                EmployeeAssignment.employee_id == employee.id,
                EmployeeAssignment.effective_from <= scheduled_date,
                EmployeeAssignment.ended_at.is_(None)
                | (EmployeeAssignment.ended_at > scheduled_date),
            )
        )
    ).scalar_one_or_none()
    if assignment is None:
        return "present"
    policy = (
        await access.db.execute(
            select(LatePolicy).where(
                LatePolicy.department_id == assignment.department_id,
                LatePolicy.designation_id == assignment.designation_id,
                LatePolicy.shift_type_id == uuid.UUID(shift["shift_type_id"]),
                LatePolicy.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if policy and instant > datetime.fromisoformat(shift["starts_at"]) + timedelta(
        minutes=policy.grace_minutes
    ):
        return "late"
    return "present"
