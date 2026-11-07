"""Platform admins: the SOC rules versions, publish a draft, roll back to a retired one (T15.7).

Every change is audited under the platform admin. A draft is made only by the daily watch (or the
owner's import command), so a person reviews the diff here before anything goes live. A saved SOC
check keeps the rules version it was made with, so none of this rewrites one.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (FastAPI reads the path parameter type at runtime)
from datetime import date, datetime  # noqa: TC003  (pydantic reads the field types at runtime)
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.core.errors import AppError, NotFoundError
from app.modules.audit.service import record
from app.modules.rbac.platform import PlatformAccess, require_platform
from app.modules.soc_rules.importer import (
    RulesImportError,
    publish_rules_version,
    rollback_rules_version,
)
from app.modules.soc_rules.models import RulesVersion

router = APIRouter(tags=["platform-rules"])
Publisher = Annotated[PlatformAccess, Depends(require_platform("platform.rules.publish"))]
LIST_LIMIT = 20


class RulesVersionOut(BaseModel):
    id: str
    name: str
    status: str  # draft | live | retired
    effective_from: date
    published_at: datetime | None
    created_at: datetime
    diff_summary: dict[str, Any]  # what the draft changes against the live version
    pages: list[dict[str, Any]]  # the GOV.UK pages it was made from, with their hashes


class RulesVersionsOut(BaseModel):
    items: list[RulesVersionOut]


def _out(row: RulesVersion) -> RulesVersionOut:
    return RulesVersionOut(
        id=str(row.id),
        name=row.name,
        status=row.status,
        effective_from=row.effective_from,
        published_at=row.published_at,
        created_at=row.created_at,
        diff_summary=row.diff_summary,
        pages=row.source_urls,
    )


async def _version(access: PlatformAccess, version_id: uuid.UUID) -> RulesVersion:
    row = await access.db.get(RulesVersion, version_id)
    if row is None:
        raise NotFoundError("We could not find that rules version.")
    return row


@router.get("/platform/rules", response_model=RulesVersionsOut)
async def list_versions(access: Publisher) -> RulesVersionsOut:
    rows = await access.db.execute(
        select(RulesVersion).order_by(RulesVersion.created_at.desc()).limit(LIST_LIMIT)
    )
    return RulesVersionsOut(items=[_out(row) for row in rows.scalars().all()])


@router.post("/platform/rules/{version_id}/publish", response_model=RulesVersionOut)
async def publish(version_id: uuid.UUID, access: Publisher) -> RulesVersionOut:
    row = await _version(access, version_id)
    try:
        await publish_rules_version(access.db, version_id, published_by=access.caller.user_id)
    except RulesImportError as exc:
        raise AppError("NOT_A_DRAFT", str(exc), status_code=409) from exc
    await record(
        access.db,
        access.audit_context,
        "platform.rules_published",
        entity_type="rules_version",
        entity_id=version_id,
        after={"name": row.name},
    )
    result = _out(row)
    await access.db.commit()
    return result


@router.post("/platform/rules/{version_id}/rollback", response_model=RulesVersionOut)
async def rollback(version_id: uuid.UUID, access: Publisher) -> RulesVersionOut:
    row = await _version(access, version_id)
    try:
        await rollback_rules_version(access.db, version_id, published_by=access.caller.user_id)
    except RulesImportError as exc:
        raise AppError("NOT_RETIRED", str(exc), status_code=409) from exc
    await record(
        access.db,
        access.audit_context,
        "platform.rules_rolled_back",
        entity_type="rules_version",
        entity_id=version_id,
        after={"name": row.name},
    )
    result = _out(row)
    await access.db.commit()
    return result
