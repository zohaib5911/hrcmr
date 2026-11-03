"""Daily compliance reconciliation using company-local dates and official calendars."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.rtw import employee_rtw_status
from app.db.session import TenantSession
from app.modules.audit.service import AuditContext, record
from app.modules.companies.models import Company
from app.modules.compliance.calendar import deadline_for
from app.modules.compliance.models import ChangeOfCircumstances, OrgChange
from app.modules.compliance.reminder_models import Reminder
from app.modules.compliance.reminder_service import synchronize_employee
from app.modules.employees.models import Employee
from app.modules.holidays.models import BankHoliday
from app.modules.identity.models import Membership
from app.modules.notifications.models import Notification

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("app.compliance_jobs")


async def _refresh_deadlines(
    db: TenantSession, audit: AuditContext, holidays: dict[str, list[BankHoliday]]
) -> int:
    changed = 0
    for model in (ChangeOfCircumstances, OrgChange):
        query = (
            select(model)
            .where(model.reported_at.is_(None))
            .order_by(model.id)
            .with_for_update(skip_locked=True)
        )
        if model is OrgChange:
            query = query.where(
                OrgChange.archived_at.is_(None), OrgChange.deadline_date.is_not(None)
            )
        rows = cast(
            "list[ChangeOfCircumstances | OrgChange]", list((await db.execute(query)).scalars())
        )
        for row in rows:
            try:
                calculated = deadline_for(
                    row.calendar_region,
                    row.change_date,
                    10 if isinstance(row, ChangeOfCircumstances) else 20,
                    holidays.get(row.calendar_region, []),
                )
            except AppError:
                logger.warning("reporting_calendar_unavailable", company_id=str(db.company_id))
                continue
            dates = [day.isoformat() for day in calculated.holidays]
            if (row.deadline_date, row.calendar_holidays, row.calendar_checked_at) == (
                calculated.deadline_date,
                dates,
                calculated.checked_at,
            ):
                continue
            previous = {
                "deadline_date": str(row.deadline_date),
                "calendar_holidays": row.calendar_holidays,
            }
            row.deadline_date = calculated.deadline_date
            row.calendar_holidays = dates
            row.calendar_checked_at = calculated.checked_at
            row.updated_by = None
            await record(
                db,
                audit,
                "employee.change_deadline_refreshed"
                if isinstance(row, ChangeOfCircumstances)
                else "company.change_deadline_refreshed",
                entity_type="employee" if isinstance(row, ChangeOfCircumstances) else "org_change",
                entity_id=row.employee_id if isinstance(row, ChangeOfCircumstances) else row.id,
                before=previous,
                after={
                    "change_id": str(row.id),
                    "deadline_date": str(row.deadline_date),
                    "calendar_holidays": dates,
                },
            )
            changed += 1
    return changed


async def _notify_admins(db: TenantSession, audit: AuditContext, moment: datetime) -> int:
    due = list(
        (
            await db.execute(
                select(Reminder)
                .where(Reminder.status == "due", Reminder.admin_notified_at.is_(None))
                .with_for_update(skip_locked=True)
            )
        ).scalars()
    )
    if not due:
        return 0
    admins = (
        (
            await db.execute(
                select(Membership.user_id).where(
                    Membership.role.in_(("company_admin", "hr_admin")),
                    Membership.status == "active",
                )
            )
        )
        .scalars()
        .all()
    )
    for user_id in admins:
        db.add(
            Notification(
                company_id=db.company_id,
                user_id=user_id,
                kind="compliance.reminders_due",
                title="Compliance reminders need review",
                body=(
                    f"{len(due)} reminder thresholds need review. "
                    "Nothing has been sent to employees."
                ),
                link="/sponsor-compliance/reminders",
            )
        )
    for row in due:
        row.admin_notified_at = moment
        row.updated_by = None
    await record(
        db,
        audit,
        "compliance.reminder_reviews_notified",
        entity_type="reminder",
        after={"reminder_count": len(due), "recipient_count": len(admins)},
    )
    return len(due)


async def reconcile_reminders(owner: AsyncEngine, *, now: datetime | None = None) -> int:
    moment = now or datetime.now(UTC)
    async with AsyncSession(owner, expire_on_commit=False) as global_db:
        companies = (
            await global_db.execute(
                select(Company.id, Company.timezone).where(Company.status == "active")
            )
        ).all()
        grouped: dict[str, list[BankHoliday]] = defaultdict(list)
        for holiday in (await global_db.execute(select(BankHoliday))).scalars():
            grouped[holiday.region].append(holiday)
    handled = 0
    for company_id, zone in companies:
        audit = AuditContext(company_id=company_id, actor_user_id=None, actor_type="system")
        today = moment.astimezone(ZoneInfo(zone)).date()
        async with TenantSession(owner, company_id=company_id) as db:
            employee_ids: list[uuid.UUID] = list(
                (await db.execute(select(Employee.id).order_by(Employee.id))).scalars()
            )
        for employee_id in employee_ids:
            async with TenantSession(owner, company_id=company_id) as db:
                handled += await synchronize_employee(
                    db, employee_id, audit, today=today, now=moment
                )
                await db.commit()
        async with TenantSession(owner, company_id=company_id) as db:
            handled += await _refresh_deadlines(db, audit, grouped)
            handled += await _notify_admins(db, audit, moment)
            await db.commit()
    return handled


async def reminders_daily(ctx: dict[str, Any]) -> int:
    owner = ctx.get("owner_engine")
    return await reconcile_reminders(owner, now=ctx.get("now")) if owner is not None else 0


async def rtw_status_daily(ctx: dict[str, Any]) -> int:
    # The security-invoker view calculates status from each company's current local day.
    # Reading it evaluates those rules; there is no cached status column to overwrite.
    owner = ctx.get("owner_engine")
    if owner is None:
        return 0
    async with AsyncSession(owner) as db:
        result = await db.execute(
            select(func.count())
            .select_from(employee_rtw_status)
            .join(Employee, Employee.id == employee_rtw_status.c.employee_id)
            .where(Employee.status != "archived")
        )
        return int(result.scalar_one())
