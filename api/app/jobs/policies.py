"""Daily policy upkeep: mark overdue acceptances and assign new starters by company day."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import TenantSession
from app.modules.audit.service import AuditContext
from app.modules.companies.models import Company
from app.modules.policies import service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("app.jobs.policies")


async def reconcile_policies(
    owner: AsyncEngine, web_origin: str, *, now: datetime | None = None
) -> int:
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
        try:
            async with TenantSession(owner, company_id=company_id) as db:
                done = await service.mark_overdue(db, audit, today, web_origin)
                done += await service.assign_new_starters(db, audit, today, web_origin)
                await db.commit()
        except Exception as exc:
            # One company's failure must not stop the others' upkeep (ISS-31); it retries tomorrow.
            logger.warning(
                "policy_upkeep_failed", company_id=str(company_id), kind=type(exc).__name__
            )
            continue
        handled += done
    return handled


async def policies_overdue_daily(ctx: dict[str, Any]) -> int:
    owner, settings = ctx.get("owner_engine"), ctx.get("settings")
    if owner is None or settings is None:
        return 0
    return await reconcile_policies(owner, settings.web_origin, now=ctx.get("now"))
