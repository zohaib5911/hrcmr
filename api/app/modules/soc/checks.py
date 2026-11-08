"""Saved sponsorship checks (plan 8.17, T15.6): a draft from one rules check, then a confirmed code.

No FastAPI here. The rules engine's answer is stored as it was computed, with the rules version it
used, so a later rules change does not rewrite a check the company already saved.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic_core import to_jsonable_python
from sqlalchemy import select

from app.modules.soc.models import SocCheck, SocUnitGroup

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.soc_rules.engine import CheckResult, RulesData

HISTORY_LIMIT = 50


def result_snapshot(result: CheckResult) -> dict[str, Any]:
    """The engine's answer as plain JSON (money as strings, dates as ISO text)."""
    snapshot: dict[str, Any] = to_jsonable_python(result)
    return snapshot


async def create_draft(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    job_title: str,
    job_description: str,
    soc_code: str,
    inputs: dict[str, Any],
    rules: RulesData,
    result: CheckResult,
) -> SocCheck:
    if rules.version_id is None:
        raise ValueError("the rules version has no id")
    unit = (
        await db.execute(select(SocUnitGroup).where(SocUnitGroup.code == soc_code))
    ).scalar_one()
    row = SocCheck(
        company_id=company_id,
        status="draft",
        job_title=job_title,
        job_description=job_description,
        soc_code=soc_code,
        soc_title=unit.title,
        rules_version_id=uuid.UUID(rules.version_id),
        rules_version_name=rules.version_name,
        rules_effective_from=rules.effective_from,
        inputs=inputs,
        result=result_snapshot(result),
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def confirm(db: AsyncSession, row: SocCheck, user_id: uuid.UUID) -> SocCheck:
    """Marks the code as confirmed. Confirming twice changes nothing."""
    if row.status == "confirmed":
        return row
    row.status = "confirmed"
    row.confirmed_at = datetime.now(UTC)
    row.confirmed_by = user_id
    row.updated_by = user_id
    await db.flush()
    return row


async def history(db: AsyncSession) -> list[SocCheck]:
    """The company's checks, newest first. The tenant session keeps other companies out."""
    rows = await db.execute(
        select(SocCheck).order_by(SocCheck.created_at.desc(), SocCheck.id).limit(HISTORY_LIMIT)
    )
    return list(rows.scalars().all())
