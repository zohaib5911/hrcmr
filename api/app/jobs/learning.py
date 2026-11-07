"""Daily course upkeep: an open course past its due day becomes overdue, once. Tell the person.

It runs at 06:15 for each company, on that company's own date. Running it twice in a day changes
nothing the second time: only courses still open are flipped, so nobody is notified twice.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import TenantSession
from app.modules.audit.service import AuditContext, record
from app.modules.companies.models import Company
from app.modules.identity.models import Membership, User
from app.modules.learning.models import Course, CourseAssignment
from app.modules.notifications.models import Notification

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

KIND = "learning.overdue"
NOTICE_TITLE = "Course overdue"
OPEN = ("not_started", "in_progress")


async def mark_overdue(db: TenantSession, audit: AuditContext, today: date) -> int:
    rows = (
        await db.execute(
            select(CourseAssignment, Course)
            .join(Course, Course.id == CourseAssignment.course_id)
            .where(CourseAssignment.status.in_(OPEN), CourseAssignment.due_on < today)
            .with_for_update(of=CourseAssignment, skip_locked=True)
        )
    ).all()
    if not rows:
        return 0
    people = {assignment.employee_id for assignment, _ in rows}
    links = (
        await db.execute(
            select(User.id, Membership.employee_id)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.employee_id.in_(people),
                Membership.status == "active",
                User.is_active.is_(True),
                User.email_verified_at.is_not(None),
            )
        )
    ).all()
    user_for = {employee: user for user, employee in links if employee is not None}
    for assignment, course in rows:
        assignment.status = "overdue"
        user_id = user_for.get(assignment.employee_id)
        if user_id is not None:
            db.add(
                Notification(
                    company_id=db.company_id,
                    user_id=user_id,
                    kind=KIND,
                    title=NOTICE_TITLE,
                    body=f"{course.title} · Due {assignment.due_on}",
                    link=f"/learning/assignments/{assignment.id}",
                )
            )
    await record(
        db,
        audit,
        "learning.overdue_marked",
        entity_type="course_assignment",
        after={"count": len(rows)},
    )
    return len(rows)


async def reconcile_learning(owner: AsyncEngine, *, now: datetime | None = None) -> int:
    moment = now or datetime.now(UTC)
    async with AsyncSession(owner, expire_on_commit=False) as global_db:
        companies = (
            await global_db.execute(
                select(Company.id, Company.timezone).where(Company.status == "active")
            )
        ).all()
    handled = 0
    for company_id, zone in companies:
        audit = AuditContext(company_id=company_id, actor_user_id=None, actor_type="system")
        today = moment.astimezone(ZoneInfo(zone)).date()
        async with TenantSession(owner, company_id=company_id) as db:
            handled += await mark_overdue(db, audit, today)
            await db.commit()
    return handled


async def learning_overdue_daily(ctx: dict[str, Any]) -> int:
    owner = ctx.get("owner_engine")
    if owner is None:
        return 0
    return await reconcile_learning(owner, now=ctx.get("now"))
