"""T22.2: a company-sized data set for performance checks (development and tests only; seed/ is
not in the production image). 1,000 employees by default, each with a current assignment, a few
leave requests and a month of attendance. Set-based SQL, so it takes seconds, not minutes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncConnection

DEPARTMENTS = ("Care", "Kitchen", "Housekeeping", "Office", "Maintenance", "Nursing")

_STATEMENTS = (
    # Departments and one job title each.
    """
    insert into departments (company_id, name)
    select :company, d from unnest(cast(:departments as text[])) as d
    on conflict do nothing
    """,
    """
    insert into designations (company_id, department_id, title)
    select company_id, id, name || ' assistant' from departments where company_id = :company
    on conflict do nothing
    """,
    """
    insert into leave_types (company_id, name)
    values (:company, 'Perf annual leave')
    on conflict do nothing
    """,
    # People: about 5% leavers, 2% on leave, the rest active.
    """
    insert into employees (company_id, employee_number, first_name, last_name, email, hire_date,
                           status)
    select :company,
           'P' || lpad(n::text, 5, '0'),
           (array['Amara','Ben','Chloe','Dev','Ella','Femi','Grace','Hari','Isla','Jon'])
               [n % 10 + 1],
           'Perf' || lpad(n::text, 5, '0'),
           'perf' || n || '@example.com',
           date '2020-01-01' + (n % 1500),
           case when n % 20 = 0 then 'leaver' when n % 50 = 1 then 'on_leave' else 'active' end
    from generate_series(1, :count) as n
    """,
    # A current assignment for everyone, spread over the departments.
    """
    insert into employee_assignments (company_id, employee_id, department_id, designation_id,
                                      employment_type, effective_from)
    select e.company_id, e.id, g.department_id, g.id,
           case when row_number() over () % 4 = 0 then 'part_time' else 'full_time' end,
           e.hire_date
    from employees e
    join lateral (
        select id, department_id from designations
        where company_id = e.company_id
        order by abs(hashtext(e.id::text || id::text)) limit 1
    ) g on true
    where e.company_id = :company and e.employee_number like 'P%'
    """,
    # Three leave requests each, across the last year.
    """
    insert into leave_requests (company_id, employee_id, leave_type_id, start_date, end_date,
                                working_days, working_dates, status)
    select e.company_id, e.id, t.id, d, d, 1, jsonb_build_object(d::text, 1),
           (array['pending','approved','approved','rejected'])
               [(k + length(e.employee_number)) % 4 + 1]
    from employees e
    cross join generate_series(1, 3) as k
    cross join lateral (
        select current_date - (abs(hashtext(e.id::text || k)) % 365) as d
    ) day
    join leave_types t on t.company_id = e.company_id and t.name = 'Perf annual leave'
    where e.company_id = :company and e.employee_number like 'P%'
    """,
    # The last 30 days of attendance for active people.
    """
    insert into attendance_records (company_id, employee_id, date, status, hours)
    select e.company_id, e.id, current_date - k,
           case when k % 13 = 0 then 'sick' when k % 7 = 0 then 'late' else 'present' end, 7.5
    from employees e cross join generate_series(1, 30) as k
    where e.company_id = :company and e.status = 'active' and e.employee_number like 'P%'
    on conflict do nothing
    """,
    "analyze employees, employee_assignments, leave_requests, attendance_records",
)


async def seed_company(connection: AsyncConnection, company: uuid.UUID, count: int = 1000) -> int:
    """Adds ``count`` employees and their records to ``company``. Run as the owner (no RLS)."""
    params = {"company": company, "count": count, "departments": list(DEPARTMENTS)}
    for statement in _STATEMENTS:
        await connection.execute(text(statement), params)
    return count


async def seed_perf_test_company(connection: AsyncConnection) -> int | None:
    """Creates company ``perf-test`` and seeds it. Returns None if it already exists."""
    exists = await connection.scalar(text("select id from companies where slug = 'perf-test'"))
    if exists is not None:
        return None
    company = await connection.scalar(
        text(
            "insert into companies (name, slug, plan, subscription_status) "
            "values ('Perf test', 'perf-test', 'annual', 'active') returning id"
        )
    )
    return await seed_company(connection, company)
