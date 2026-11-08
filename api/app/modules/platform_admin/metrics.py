"""The overview numbers (T17.2, plan 8.18). Read from the database only; Stripe is not called.

Definitions, so the figures can be checked by hand:

* signups: companies created in the last 24 hours and the last 7 days.
* MRR and ARR estimate: active, entitled annual companies at £50 a year (plan L51). The 10-year
  plan is paid once, so it adds nothing to MRR.
* churn (30 days): paid plans (annual or 10-year) whose end date fell in the last 30 days. It is an
  estimate from the end date; a plan that was renewed or re-bought moves its end date and drops out.
* refunds (30 days): Stripe refunds recorded on a subscription in the last 30 days (a count).

Not here yet: error rate, job queue health and register freshness (the jobs and register screens,
T17.6), which need sources that do not exist at this step.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select

from app.db.session import GlobalSession  # noqa: TC001
from app.modules.billing.entitlements import is_entitled
from app.modules.billing.models import Subscription
from app.modules.companies.models import Company
from app.modules.platform_admin.schemas import MetricsOut

# plan.md L51: "Annual: £50 a year." Used only for the estimate above, in pence.
ANNUAL_PRICE_PENCE = 5000
PAID_PLANS = ("annual", "ten_year")
PLANS = ("free", "annual", "ten_year")


async def overview(db: GlobalSession, now: datetime | None = None) -> MetricsOut:
    moment = now or datetime.now(UTC)
    day = moment - timedelta(days=1)
    week = moment - timedelta(days=7)
    month = moment - timedelta(days=30)

    signups_24h = await _count(db, select(func.count(Company.id)).where(Company.created_at >= day))
    signups_7d = await _count(db, select(func.count(Company.id)).where(Company.created_at >= week))
    companies_active = await _count(
        db, select(func.count(Company.id)).where(Company.status == "active")
    )
    by_plan = await db.execute(
        select(Company.plan, func.count(Company.id))
        .where(Company.status == "active")
        .group_by(Company.plan)
    )
    plans_active = dict.fromkeys(PLANS, 0)
    for plan, count in by_plan.all():
        plans_active[str(plan)] = int(count)

    annual = (
        await db.execute(
            select(Company).where(Company.status == "active", Company.plan == "annual")
        )
    ).scalars()
    annual_entitled = sum(1 for company in annual if is_entitled(company, moment))
    ten_year = (
        await db.execute(
            select(Company).where(Company.status == "active", Company.plan == "ten_year")
        )
    ).scalars()
    ten_year_entitled = sum(1 for company in ten_year if is_entitled(company, moment))

    churn_30d = await _count(
        db,
        select(func.count(Company.id)).where(
            Company.plan.in_(PAID_PLANS),
            Company.status != "deleted",
            Company.subscription_ends_at >= month,
            Company.subscription_ends_at <= moment,
        ),
    )
    refunds_30d = await _count(
        db, select(func.count(Subscription.id)).where(Subscription.refunded_at >= month)
    )

    return MetricsOut(
        generated_at=moment,
        signups_24h=signups_24h,
        signups_7d=signups_7d,
        companies_active=companies_active,
        plans_active=plans_active,
        paid_entitled=annual_entitled + ten_year_entitled,
        mrr_pence=round(annual_entitled * ANNUAL_PRICE_PENCE / 12),
        arr_pence=annual_entitled * ANNUAL_PRICE_PENCE,
        churn_30d=churn_30d,
        refunds_30d=refunds_30d,
    )


async def _count(db: GlobalSession, statement: Select[Any]) -> int:
    value = await db.scalar(statement)
    return int(value or 0)
