"""Feature flags for the platform admins (T17.5, plan 8.18 Settings).

Setting a flag creates it or changes it. Nothing changes when the value and the description stay
the same, and then nothing is audited. Every real change is audited under the platform admin, with
the before and after values and the reason.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (pydantic reads the field types at runtime)
from datetime import datetime  # noqa: TC003  (same)
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.audit.service import AuditContext, record
from app.modules.feature_flags.models import FeatureFlag
from app.modules.platform_admin.schemas import FeatureFlagRow, FeatureFlagsOut

if TYPE_CHECKING:
    from app.db.session import GlobalSession


def row(flag: FeatureFlag) -> FeatureFlagRow:
    return FeatureFlagRow(
        key=flag.key,
        enabled=flag.enabled,
        description=flag.description,
        updated_at=flag.updated_at,
    )


async def flags(db: GlobalSession) -> FeatureFlagsOut:
    found = (await db.execute(select(FeatureFlag).order_by(FeatureFlag.key))).scalars().all()
    items = [row(flag) for flag in found]
    return FeatureFlagsOut(items=items, total=len(items))


async def set_flag(
    db: GlobalSession,
    context: AuditContext,
    key: str,
    *,
    enabled: bool,
    description: str | None,
    reason: str,
    actor: uuid.UUID,
    now: datetime,
) -> FeatureFlag:
    flag = await db.get(FeatureFlag, key)
    if flag is None:
        flag = FeatureFlag(
            key=key,
            enabled=enabled,
            description=description or "",
            updated_at=now,
            updated_by=actor,
        )
        db.add(flag)
        before: dict[str, object] = {"enabled": None, "description": None}
    else:
        new_description = flag.description if description is None else description
        if flag.enabled == enabled and flag.description == new_description:
            return flag  # nothing changes: nothing is written or audited
        before = {"enabled": flag.enabled, "description": flag.description}
        flag.enabled = enabled
        flag.description = new_description
        flag.updated_at = now
        flag.updated_by = actor
    await db.flush()
    await record(
        db,
        context,
        "platform.feature_flag_changed",
        entity_type="feature_flag",
        before=before,
        after={"key": key, "enabled": enabled, "description": flag.description},
        reason=reason,
        summary=f"Feature {key} turned {'on' if enabled else 'off'}",
    )
    return flag
