"""Reads one rules version from the database into ``RulesData`` for the engine (plan 8.17, T15.3).

The rows come back in the same shapes the parser makes, so the engine runs the same way on a
stored version as on freshly parsed pages. With no version id it reads the live version.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.soc_rules.engine import RulesData
from app.modules.soc_rules.models import (
    GoingRate,
    IneligibleCode,
    PayScaleRate,
    RulesVersion,
    SalaryRule,
    ShortageListEntry,
)
from app.modules.soc_rules.source import (
    GoingRateRow,
    IneligibleRow,
    PayScaleRow,
    SalaryRuleRow,
    ShortageRow,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class NoRulesVersionError(LookupError):
    """No live rules version (nothing published yet), or no version with that id."""


async def load_rules_data(db: AsyncSession, version_id: uuid.UUID | None = None) -> RulesData:
    query = select(RulesVersion)
    query = (
        query.where(RulesVersion.id == version_id)
        if version_id is not None
        else query.where(RulesVersion.status == "live")
    )
    version = (await db.execute(query)).scalar_one_or_none()
    if version is None:
        raise NoRulesVersionError("No rules version has been published yet.")
    vid = version.id

    going = (
        await db.execute(
            select(GoingRate).where(GoingRate.rules_version_id == vid).order_by(GoingRate.id)
        )
    ).scalars()
    pay = (
        await db.execute(
            select(PayScaleRate)
            .where(PayScaleRate.rules_version_id == vid)
            .order_by(PayScaleRate.id)
        )
    ).scalars()
    ineligible = (
        await db.execute(
            select(IneligibleCode)
            .where(IneligibleCode.rules_version_id == vid)
            .order_by(IneligibleCode.soc_code)
        )
    ).scalars()
    shortage = (
        await db.execute(
            select(ShortageListEntry)
            .where(ShortageListEntry.rules_version_id == vid)
            .order_by(ShortageListEntry.list_name, ShortageListEntry.soc_code)
        )
    ).scalars()
    salary = (
        await db.execute(
            select(SalaryRule).where(SalaryRule.rules_version_id == vid).order_by(SalaryRule.option)
        )
    ).scalars()

    return RulesData(
        version_id=str(vid),
        version_name=version.name,
        effective_from=version.effective_from,
        going_rates=tuple(
            GoingRateRow(
                table=r.table,
                soc_code=r.soc_code,
                title=r.title,
                administration=r.administration,
                related_titles=tuple(r.related_titles),
                soc2010_codes=tuple(r.soc2010_codes),
                annual_rate=r.annual_rate,
                hourly_rate=r.hourly_rate,
                rate_90=r.rate_90,
                rate_80=r.rate_80,
                rate_70=r.rate_70,
                phd_points_eligible=r.phd_points_eligible,
                basis_hours=r.basis_hours,
                notes=r.notes,
            )
            for r in going
        ),
        pay_scales=tuple(
            PayScaleRow(
                source_table=r.source_table,
                soc_code=r.soc_code,
                administration=r.administration,
                band_or_role=r.band_or_role,
                annual_rate=r.annual_rate,
                basis_hours=r.basis_hours,
            )
            for r in pay
        ),
        ineligible=tuple(
            IneligibleRow(
                soc_code=r.soc_code,
                title=r.title,
                related_titles=tuple(r.related_titles),
                reason=r.reason,
            )
            for r in ineligible
        ),
        shortage=tuple(
            ShortageRow(
                list_name=r.list_name,
                soc_code=r.soc_code,
                title=r.title,
                condition_text=r.condition_text,
                job_types=tuple(r.job_types),
                nations=tuple(r.nations),
                removal_date=r.removal_date,
            )
            for r in shortage
        ),
        salary_rules=tuple(
            SalaryRuleRow(
                option=r.option,
                general_threshold=r.general_threshold,
                going_rate_pct=r.going_rate_pct,
                criteria_key=r.criteria_key,
                applies_to=r.applies_to,
                requirement_text=r.requirement_text,
                further_rules=r.further_rules,
            )
            for r in salary
        ),
        table_notes=dict(version.table_notes),
    )
