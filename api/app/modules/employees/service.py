"""Creating an employee record. One place checks the number is free and writes the row.

Both the employees API and the conversion of a candidate (T11.5) call this, so the rules match.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import ConflictError
from app.modules.employees.models import Employee

if TYPE_CHECKING:
    from app.db.session import TenantSession
    from app.modules.employees.schemas import EmployeeIn


def number_key(number: str) -> str:
    """Numbers compare ignoring case and spaces: "E 001" and "e001" are the same person."""
    return "".join(number.split()).lower()


async def add_employee(db: TenantSession, company_id: uuid.UUID, body: EmployeeIn) -> Employee:
    taken = (
        await db.execute(
            select(Employee.id).where(
                func.lower(func.regexp_replace(Employee.employee_number, r"\s", "", "g"))
                == number_key(body.employee_number)
            )
        )
    ).first()
    in_use = ConflictError("That employee number is already in use.", field="employee_number")
    if taken is not None:
        raise in_use
    employee = Employee(
        company_id=company_id,
        employee_number=body.employee_number,
        first_name=body.first_name,
        last_name=body.last_name,
        email=str(body.email).strip().lower(),
        phone=body.phone,
        hire_date=body.hire_date,
        status=body.status,
    )
    db.add(employee)
    try:
        await db.flush()
    except IntegrityError as exc:  # two people saving the same number at once
        raise in_use from exc
    return employee
