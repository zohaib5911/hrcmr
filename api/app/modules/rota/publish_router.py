"""Scoped publication, transactional digests, private print and last-published My Shifts."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request, Response
from jinja2 import Environment
from sqlalchemy import select

from app.core.crypto import encrypt
from app.core.errors import AppError
from app.core.rbac_matrix import Scope
from app.modules.attendance.router import _company
from app.modules.email.models import EmailOutbox
from app.modules.email.outbox import PAYLOAD_CONTEXT
from app.modules.email.templates import check
from app.modules.employees.record_pdf import render_pdf_async
from app.modules.identity.models import Membership, User
from app.modules.notifications.models import Notification
from app.modules.notifications.preferences import email_modes
from app.modules.rbac.deps import Access, require
from app.modules.rota.week_models import RotaWeek
from app.modules.rota.week_router import Reads, Writes  # noqa: TC001
from app.modules.rota.week_schemas import ActionOut, OwnShifts, ShiftOut, WeekVersion
from app.modules.rota.weeks import check_monday, lock_week, monday, rows, shift_out, write_ids

router = APIRouter(prefix="/rota", tags=["rota"])
Own = Annotated[Access, Depends(require("rota.scheduled_shift.read"))]


def _canonical(items: list[dict[str, object]]) -> str:
    return json.dumps(sorted(items, key=lambda r: str(r["id"])), sort_keys=True)


@router.post("/weeks/{week_start}/publish", response_model=ActionOut)
async def publish(
    week_start: date, body: WeekVersion, access: Writes, request: Request
) -> ActionOut:
    week = await lock_week(access, week_start, body.version)
    ids = await write_ids(access)
    company = await _company(access)
    current = [
        shift_out(r, e, name, ZoneInfo(company.timezone)).model_dump(mode="json")
        for r, e, name in await rows(access, week_start)
    ]
    previous = week.published_shifts
    allowed_ids = {str(i) for i in ids} if ids is not None else None

    def allowed(employee: object) -> bool:
        return allowed_ids is None or employee in allowed_ids

    incoming = [r for r in current if allowed(r["employee_id"])]
    combined = [r for r in previous if not allowed(r["employee_id"])] + incoming
    affected = {str(r["employee_id"]) for r in [*previous, *incoming] if allowed(r["employee_id"])}
    changed = {
        e
        for e in affected
        if _canonical([r for r in previous if r["employee_id"] == e])
        != _canonical([r for r in combined if r["employee_id"] == e])
    }
    week.published_shifts = combined
    week.status = "published" if _canonical(combined) == _canonical(current) else "draft"
    week.published_at, week.published_by = datetime.now(UTC), access.caller.user_id
    week.version += 1
    recipients = (
        (
            await access.db.execute(
                select(User, Membership.employee_id)
                .join(Membership, Membership.user_id == User.id)
                .where(
                    Membership.company_id == access.company_id,
                    Membership.employee_id.in_({uuid.UUID(e) for e in changed}),
                    Membership.status == "active",
                    User.is_active.is_(True),
                    User.email_verified_at.is_not(None),
                )
            )
        ).all()
        if changed
        else []
    )
    # Only "immediate" people get the e-mail now; "daily" and "off" see the in-app notice.
    modes = await email_modes(access.db, [user.id for user, _ in recipients])
    for user, employee_id in recipients:
        count = sum(r["employee_id"] == str(employee_id) for r in combined)
        data = {
            "first_name": user.first_name,
            "dates": f"{week_start} to {week_start + timedelta(days=6)}",
            "shift_count": str(count),
            "link": f"{request.app.state.settings.web_origin}/my-shifts?week={week_start}",
        }
        check("rota_published", data)
        access.db.add(
            Notification(
                company_id=access.company_id,
                user_id=user.id,
                kind="rota.published",
                title="Your rota has been published",
                body=f"Week starting {week_start}. Open My Shifts to review your schedule.",
                link=f"/my-shifts?week={week_start}",
            )
        )
        if modes.get(user.id, "immediate") == "immediate":
            access.db.add(
                EmailOutbox(
                    to_address=user.email,
                    template="rota_published",
                    payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
                )
            )
    await access.audit(
        "rota.week_published",
        after={
            "week_start": week_start.isoformat(),
            "affected_employees": len(changed),
            "shifts": len(incoming),
        },
    )
    result = ActionOut(count=len(changed), version=week.version)
    await access.db.commit()
    return result


@router.get("/own", response_model=OwnShifts)
async def own_shifts(access: Own, start: date, end: date) -> OwnShifts:
    if end < start or (end - start).days > 366:
        raise AppError("VALIDATION_ERROR", "Choose a range of up to one year.", status_code=422)
    company = await _company(access)
    if access.employee_id is None:
        return OwnShifts(timezone=company.timezone, shifts=[])
    weeks = list(
        (
            await access.db.execute(
                select(RotaWeek).where(
                    RotaWeek.week_start >= monday(start),
                    RotaWeek.week_start <= monday(end),
                    RotaWeek.published_at.is_not(None),
                )
            )
        ).scalars()
    )
    shifts = [
        ShiftOut.model_validate(r)
        for week in weeks
        for r in week.published_shifts
        if r["employee_id"] == str(access.employee_id)
        and start.isoformat() <= r["date"] <= end.isoformat()
    ]
    return OwnShifts(
        timezone=company.timezone, shifts=sorted(shifts, key=lambda s: (s.starts_at, s.id))
    )


@router.get(
    "/weeks/{week_start}/print.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def print_week(week_start: date, access: Reads) -> Response:
    check_monday(week_start)
    ids = (
        await access.reports.reports_of(access.employee_id)
        if access.scope is Scope.REPORTS and access.employee_id
        else (frozenset() if access.scope is Scope.REPORTS else None)
    )
    company = await _company(access)
    shifts = [
        shift_out(r, e, name, ZoneInfo(company.timezone))
        for r, e, name in await rows(access, week_start, ids)
    ]
    if len(shifts) > 1000:
        raise AppError(
            "ROTA_TOO_LARGE", "Print a week with fewer than 1,000 shifts.", status_code=422
        )
    week = (
        await access.db.execute(select(RotaWeek).where(RotaWeek.week_start == week_start))
    ).scalar_one_or_none()
    # Trusted local template; all company, employee and note values are escaped.
    html = (
        # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
        Environment(autoescape=True)
        .from_string(Path(__file__).with_name("week.html").read_text())
        .render(
            company=company.name,
            week_start=week_start,
            timezone=company.timezone,
            draft=week is None or week.status == "draft",
            shifts=shifts,
        )
    )
    content = await render_pdf_async(html)
    await access.audit(
        "rota.week_printed", after={"week_start": week_start.isoformat(), "shifts": len(shifts)}
    )
    await access.db.commit()
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="rota-{week_start}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )
