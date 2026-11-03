"""Seed each new company's defaults in the same transaction as signup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.leave.models import LeaveType
from app.modules.leave.reference import CHECKED_ON, DEFAULT_TYPES

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


async def seed_types(db: AsyncSession, company_id: uuid.UUID) -> None:
    db.add_all(
        [
            LeaveType(company_id=company_id, checked_on=CHECKED_ON, **values)
            for values in DEFAULT_TYPES
        ]
    )
    await db.flush()
