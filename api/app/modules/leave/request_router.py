"""Scoped leave submission, preview, decisions and atomic booking/notifications."""

from __future__ import annotations

import json
import uuid  # noqa: TC003
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.core.crypto import encrypt
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope, scope_for
from app.modules.attendance.models import AttendanceRecord
from app.modules.companies.models import Company
from app.modules.email.models import EmailOutbox
from app.modules.email.outbox import PAYLOAD_CONTEXT
from app.modules.email.templates import check
from app.modules.employees.models import Employee
from app.modules.identity.models import Membership, User
from app.modules.leave.ledger import balance, leave_type, lock_employee, reconcile
from app.modules.leave.models import LeaveLedger, LeaveType
from app.modules.leave.request_models import LeaveRequest
from app.modules.leave.request_schemas import (
    LeaveDatesIn,
    LeaveDecisionIn,
    LeavePreview,
    LeaveRequestIn,
    LeaveRequestOut,
)
from app.modules.leave.requests import RequestPlan, conflicts, plan_request
from app.modules.notifications.models import Notification
from app.modules.rbac.deps import Access, require

router = APIRouter(prefix="/leave", tags=["leave"])
Reads = Annotated[Access, Depends(require("leave.request.read"))]
Creates = Annotated[Access, Depends(require("leave.request.create"))]
Approves = Annotated[Access, Depends(require("leave.request.approve"))]


async def _employee(access: Access, ident: uuid.UUID, *, relation: str = "reporting") -> Employee:
    if not await access.can_reach(ident, relation="leave" if relation == "leave" else "reporting"):
        raise NotFoundError
    return await lock_employee(access.db, ident)


def _own(access: Access) -> uuid.UUID:
    if access.employee_id is None:
        raise AppError(
            "EMPLOYEE_NOT_LINKED",
            "Your account needs a linked employee record to request leave.",
            status_code=422,
        )
    return access.employee_id


async def _preview(access: Access, employee_id: uuid.UUID, body: LeaveDatesIn) -> LeavePreview:
    employee = await _employee(access, employee_id)
    await leave_type(access.db, body.leave_type_id)
    plan = await plan_request(access.db, employee, body)
    warnings = await conflicts(access.db, employee_id, body.start_date, body.end_date, plan)
    return LeavePreview(
        working_days=plan.total, working_dates=list(plan.quantities), conflicts=warnings
    )


@router.post("/requests/preview", response_model=LeavePreview)
async def preview_request(body: LeaveRequestIn, access: Creates) -> LeavePreview:
    return await _preview(access, body.employee_id, body)


@router.post("/requests/own/preview", response_model=LeavePreview)
async def preview_own(body: LeaveDatesIn, access: Creates) -> LeavePreview:
    return await _preview(access, _own(access), body)


async def _list(
    access: Access, *, own: bool = False, approvals: bool = False, status: str | None = None
) -> list[LeaveRequestOut]:
    query = (
        select(LeaveRequest, Employee, LeaveType)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
        .order_by(LeaveRequest.start_date.desc(), LeaveRequest.id.desc())
    )
    if own or access.scope is Scope.OWN:
        if access.employee_id is None:
            return []
        query = query.where(LeaveRequest.employee_id == access.employee_id)
    elif access.scope is Scope.REPORTS:
        if access.employee_id is None:
            return []
        reports = await access.reports.reports_of(
            access.employee_id, relation="leave" if approvals else "reporting"
        )
        query = query.where(LeaveRequest.employee_id.in_(reports))
    if approvals:
        query = query.where(LeaveRequest.status == "pending")
        if access.employee_id is not None:
            query = query.where(LeaveRequest.employee_id != access.employee_id)
    elif status is not None:
        query = query.where(LeaveRequest.status == status)
    return [
        LeaveRequestOut.model_validate(row).model_copy(
            update={
                "employee_name": f"{employee.first_name} {employee.last_name}",
                "leave_type_name": kind.name,
                "colour": kind.colour,
            }
        )
        for row, employee, kind in (await access.db.execute(query.limit(200))).all()
    ]


@router.get("/requests", response_model=list[LeaveRequestOut])
async def requests(
    access: Reads,
    status: Annotated[str | None, Query(pattern="^(pending|approved|rejected|cancelled)$")] = None,
) -> list[LeaveRequestOut]:
    return await _list(access, status=status)


@router.get("/requests/own", response_model=list[LeaveRequestOut])
async def own_requests(access: Reads) -> list[LeaveRequestOut]:
    return await _list(access, own=True)


@router.get("/approvals/own", response_model=list[LeaveRequestOut])
async def own_approvals(access: Approves) -> list[LeaveRequestOut]:
    return await _list(access, approvals=True)


async def _notify_decision(access: Access, row: LeaveRequest, request: Request) -> None:
    recipients = (
        (
            await access.db.execute(
                select(User)
                .join(Membership, Membership.user_id == User.id)
                .where(
                    Membership.company_id == access.company_id,
                    Membership.employee_id == row.employee_id,
                    Membership.status == "active",
                    User.is_active.is_(True),
                    User.email_verified_at.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for user in recipients:
        access.db.add(
            Notification(
                company_id=access.company_id,
                user_id=user.id,
                kind="leave.decision",
                title=f"Your leave request was {row.status}",
                body="Open My Leave to see your request and allowance.",
                link="/my-leave",
            )
        )
        data = {
            "first_name": user.first_name,
            "decision": row.status,
            "dates": f"{row.start_date.isoformat()} to {row.end_date.isoformat()}",
            "link": f"{request.app.state.settings.web_origin}/my-leave",
        }
        check("leave_decision", data)
        access.db.add(
            EmailOutbox(
                to_address=user.email,
                template="leave_decision",
                payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
            )
        )


async def _notify_approvers(access: Access, row: LeaveRequest) -> None:
    memberships = (
        (
            await access.db.execute(
                select(Membership).where(
                    Membership.company_id == access.company_id, Membership.status == "active"
                )
            )
        )
        .scalars()
        .all()
    )
    for member in memberships:
        if member.employee_id == row.employee_id:
            continue
        scope = scope_for(member.role, "leave.request.approve")
        allowed = scope is Scope.ALL or (
            scope is Scope.REPORTS
            and member.employee_id is not None
            and await access.reports.is_report(
                member.employee_id, row.employee_id, relation="leave"
            )
        )
        if allowed:
            access.db.add(
                Notification(
                    company_id=access.company_id,
                    user_id=member.user_id,
                    kind="leave.request_created",
                    title="A leave request needs your decision",
                    body="Open My Approvals to review the dates and coverage.",
                    link="/my-approvals",
                )
            )


def _body(row: LeaveRequest) -> LeaveDatesIn:
    return LeaveDatesIn(
        leave_type_id=row.leave_type_id,
        start_date=row.start_date,
        end_date=row.end_date,
        half_day_start=row.half_day_start,
        half_day_end=row.half_day_end,
        note=row.note,
    )


async def _book(
    access: Access, row: LeaveRequest, employee: Employee, plan: RequestPlan, *, automatic: bool
) -> None:
    kind = await leave_type(access.db, row.leave_type_id)
    company = (
        await access.db.execute(select(Company).where(Company.id == access.company_id))
    ).scalar_one()
    today = datetime.now(ZoneInfo(company.timezone)).date()
    for year, days in plan.by_year.items():
        if kind.days_per_year is not None:
            # Regular allowances reconcile first; irregular hours use reviewed manual grants.
            try:
                await reconcile(
                    access.db,
                    employee.id,
                    kind.id,
                    max(
                        year,
                        min(today, date(year.year + 1, year.month, year.day) - timedelta(days=1)),
                    ),
                )
            except AppError as error:
                if error.code != "IRREGULAR_HOURS":
                    raise
            current = await balance(access.db, employee.id, kind.id, year)
            if not company.allow_negative_leave_balance and current < days:
                raise ConflictError(
                    "This request exceeds the available leave balance.", field="working_days"
                )
        access.db.add(
            LeaveLedger(
                company_id=access.company_id,
                employee_id=employee.id,
                leave_type_id=kind.id,
                leave_year_start=year,
                entry_type="taken",
                days=-days,
                reason="Approved leave request",
                leave_request_id=row.id,
            )
        )
    for day in plan.quantities:
        half = (day == row.start_date and row.half_day_start) or (
            day == row.end_date and row.half_day_end
        )
        access.db.add(
            AttendanceRecord(
                company_id=access.company_id,
                employee_id=employee.id,
                date=day,
                status="half_day" if half else "on_leave",
                source="leave_sync",
                leave_request_id=row.id,
            )
        )
    row.status = "approved"
    row.decided_by = None if automatic else access.caller.user_id
    row.decided_at = datetime.now(UTC)


async def _create(
    access: Access, employee_id: uuid.UUID, body: LeaveDatesIn, request: Request
) -> LeaveRequestOut:
    employee = await _employee(access, employee_id)
    kind = await leave_type(access.db, body.leave_type_id)
    plan = await plan_request(access.db, employee, body)
    warnings = await conflicts(access.db, employee_id, body.start_date, body.end_date, plan)
    if any(w.code == "EMPLOYEE_OVERLAP" for w in warnings):
        raise ConflictError("There is already pending or approved leave on these working days.")
    row = LeaveRequest(
        company_id=access.company_id,
        employee_id=employee_id,
        working_days=plan.total,
        working_dates=plan.snapshot(),
        **body.model_dump(),
    )
    access.db.add(row)
    await access.db.flush()
    if not kind.requires_approval:
        if any(w.blocking for w in warnings):
            raise ConflictError("Review existing attendance before booking this leave.")
        await _book(access, row, employee, plan, automatic=True)
        await _notify_decision(access, row, request)
    else:
        await _notify_approvers(access, row)
    await access.audit(
        "leave.request_created",
        entity_type="employee",
        entity_id=employee_id,
        after={
            "request_id": str(row.id),
            "working_days": str(row.working_days),
            "status": row.status,
        },
    )
    await access.db.commit()
    return LeaveRequestOut.model_validate(row)


@router.post("/requests", status_code=201, response_model=LeaveRequestOut)
async def create_request(
    body: LeaveRequestIn, request: Request, access: Creates
) -> LeaveRequestOut:
    dates_body = LeaveDatesIn.model_validate(body.model_dump(exclude={"employee_id"}))
    return await _create(access, body.employee_id, dates_body, request)


@router.post("/requests/own", status_code=201, response_model=LeaveRequestOut)
async def create_own(body: LeaveDatesIn, request: Request, access: Creates) -> LeaveRequestOut:
    return await _create(access, _own(access), body, request)


async def _locked(
    access: Access, request_id: uuid.UUID, *, approval: bool
) -> tuple[LeaveRequest, Employee]:
    row = (
        await access.db.execute(select(LeaveRequest).where(LeaveRequest.id == request_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    employee = await _employee(
        access, row.employee_id, relation="leave" if approval else "reporting"
    )
    row = (
        await access.db.execute(
            select(LeaveRequest)
            .where(LeaveRequest.id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    if row.status != "pending":
        raise ConflictError("Only pending leave requests can be changed.")
    return row, employee


async def _decide(
    access: Access, request_id: uuid.UUID, body: LeaveDecisionIn, request: Request, *, approve: bool
) -> LeaveRequestOut:
    row, employee = await _locked(access, request_id, approval=True)
    if row.employee_id == access.employee_id:
        raise ForbiddenError("You cannot decide your own leave request.")
    if approve:
        plan = await plan_request(access.db, employee, _body(row))
        if row.working_dates != plan.snapshot() or row.working_days != plan.total:
            raise ConflictError(
                "The working pattern or calendar changed. Cancel this request and "
                "submit the updated dates for review."
            )
        warnings = await conflicts(
            access.db, employee.id, row.start_date, row.end_date, plan, exclude=row.id
        )
        if any(w.blocking for w in warnings):
            raise ConflictError("Resolve overlapping leave or recorded attendance before approval.")
        await _book(access, row, employee, plan, automatic=False)
    else:
        row.status = "rejected"
        row.decided_by = access.caller.user_id
        row.decided_at = datetime.now(UTC)
    row.decision_note = body.note.strip() or None if body.note is not None else None
    await _notify_decision(access, row, request)
    await access.audit(
        f"leave.request_{row.status}",
        entity_type="employee",
        entity_id=employee.id,
        after={
            "request_id": str(row.id),
            "working_days": str(row.working_days),
            "status": row.status,
        },
    )
    await access.db.commit()
    return LeaveRequestOut.model_validate(row)


@router.post("/requests/{request_id}/approve", response_model=LeaveRequestOut)
async def approve_request(
    request_id: uuid.UUID, body: LeaveDecisionIn, request: Request, access: Approves
) -> LeaveRequestOut:
    return await _decide(access, request_id, body, request, approve=True)


@router.post("/requests/{request_id}/reject", response_model=LeaveRequestOut)
async def reject_request(
    request_id: uuid.UUID, body: LeaveDecisionIn, request: Request, access: Approves
) -> LeaveRequestOut:
    return await _decide(access, request_id, body, request, approve=False)


@router.post("/requests/{request_id}/cancel", response_model=LeaveRequestOut)
async def cancel_request(request_id: uuid.UUID, access: Creates) -> LeaveRequestOut:
    row, employee = await _locked(access, request_id, approval=False)
    row.status = "cancelled"
    await access.audit(
        "leave.request_cancelled",
        entity_type="employee",
        entity_id=employee.id,
        after={"request_id": str(row.id)},
    )
    await access.db.commit()
    return LeaveRequestOut.model_validate(row)


@router.get("/approvals/{request_id}/preview", response_model=LeavePreview)
async def approval_preview(request_id: uuid.UUID, access: Approves) -> LeavePreview:
    row, employee = await _locked(access, request_id, approval=True)
    if row.employee_id == access.employee_id:
        raise ForbiddenError("You cannot decide your own leave request.")
    plan = await plan_request(access.db, employee, _body(row))
    warnings = await conflicts(
        access.db, employee.id, row.start_date, row.end_date, plan, exclude=row.id
    )
    return LeavePreview(
        working_days=plan.total, working_dates=list(plan.quantities), conflicts=warnings
    )
