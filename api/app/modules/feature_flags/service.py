"""Reading a feature flag (T17.5). A missing flag is off, so a feature stays off until it is turned
on deliberately."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.feature_flags.models import FeatureFlag

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def enabled(db: AsyncSession, key: str) -> bool:
    flag = await db.get(FeatureFlag, key)
    return flag is not None and flag.enabled
