"""Company leave configuration: scoped CRUD, soft archive and transactional audit."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.core.errors import AppError, ConflictError, NotFoundError
from app.modules.companies.models import Company
from app.modules.leave.models import LeaveType
from app.modules.leave.schemas import (
    LeaveSettingsOut,
    LeaveSettingsPatch,
    LeaveTypeIn,
    LeaveTypeOut,
    LeaveTypePatch,
)
from app.modules.rbac.deps import Access, require

router = APIRouter(prefix="/leave", tags=["leave"])
Reads = Annotated[Access, Depends(require("leave.type.read"))]
Writes = Annotated[Access, Depends(require("leave.type.write"))]
SettingsReads = Annotated[Access, Depends(require("leave.config.read"))]
SettingsWrites = Annotated[Access, Depends(require("leave.config.write"))]


async def _company(access: Access, *, lock: bool = False) -> Company:
    query = select(Company).where(Company.id == access.company_id)
    if lock:
        query = query.with_for_update()
    company = (await access.db.execute(query)).scalar_one_or_none()
    if company is None:
        raise NotFoundError
    return company


def _non_null(values: dict[str, Any], *, nullable: frozenset[str] = frozenset()) -> dict[str, Any]:
    for field, value in values.items():
        if value is None and field not in nullable:
            raise AppError(
                "VALIDATION_ERROR", "Give a value for this field.", status_code=422, field=field
            )
    return values


@router.get("/settings", response_model=LeaveSettingsOut)
async def settings(access: SettingsReads) -> LeaveSettingsOut:
    return LeaveSettingsOut.model_validate(await _company(access))


@router.patch("/settings", response_model=LeaveSettingsOut)
async def update_settings(body: LeaveSettingsPatch, access: SettingsWrites) -> LeaveSettingsOut:
    company = await _company(access, lock=True)
    before = LeaveSettingsOut.model_validate(company).model_dump(mode="json")
    for name, value in _non_null(body.model_dump(exclude_unset=True)).items():
        setattr(company, name, value)
    after = LeaveSettingsOut.model_validate(company)
    if before != after.model_dump(mode="json"):
        await access.audit(
            "leave.settings_updated",
            entity_type="company",
            entity_id=company.id,
            before=before,
            after=after.model_dump(mode="json"),
        )
    await access.db.commit()
    return after


async def _type(access: Access, type_id: uuid.UUID) -> LeaveType:
    row = (
        await access.db.execute(
            select(LeaveType).where(LeaveType.id == type_id, LeaveType.archived_at.is_(None))
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


def _snapshot(row: LeaveType) -> dict[str, Any]:
    return LeaveTypeOut.model_validate(row).model_dump(mode="json", exclude={"id"})


async def _unique_name(access: Access, name: str, except_id: uuid.UUID | None = None) -> None:
    query = select(LeaveType.id).where(
        func.lower(LeaveType.name) == name.lower(), LeaveType.archived_at.is_(None)
    )
    if except_id is not None:
        query = query.where(LeaveType.id != except_id)
    if (await access.db.execute(query)).first():
        raise ConflictError("You already have a leave type with that name.", field="name")


@router.get("/types", response_model=list[LeaveTypeOut])
async def list_types(
    access: Reads, include_archived: Annotated[bool, Query()] = False
) -> list[LeaveTypeOut]:
    query = select(LeaveType).order_by(LeaveType.created_at, LeaveType.id)
    if not include_archived:
        query = query.where(LeaveType.archived_at.is_(None))
    return [LeaveTypeOut.model_validate(row) for row in (await access.db.execute(query)).scalars()]


@router.get("/types/{type_id}", response_model=LeaveTypeOut)
async def read_type(type_id: uuid.UUID, access: Reads) -> LeaveTypeOut:
    return LeaveTypeOut.model_validate(await _type(access, type_id))


@router.post("/types", status_code=201, response_model=LeaveTypeOut)
async def create_type(body: LeaveTypeIn, access: Writes) -> LeaveTypeOut:
    await _company(access, lock=True)
    await _unique_name(access, body.name)
    row = LeaveType(company_id=access.company_id, **body.model_dump())
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "leave.type_created", entity_type="leave_type", entity_id=row.id, after=_snapshot(row)
    )
    await access.db.commit()
    return LeaveTypeOut.model_validate(row)


@router.patch("/types/{type_id}", response_model=LeaveTypeOut)
async def update_type(type_id: uuid.UUID, body: LeaveTypePatch, access: Writes) -> LeaveTypeOut:
    await _company(access, lock=True)
    row = await _type(access, type_id)
    values = _non_null(body.model_dump(exclude_unset=True), nullable=frozenset({"days_per_year"}))
    if "name" in values:
        await _unique_name(access, str(values["name"]), except_id=row.id)
    before = _snapshot(row)
    for name, value in values.items():
        setattr(row, name, value)
    after = _snapshot(row)
    if before != after:
        await access.audit(
            "leave.type_updated",
            entity_type="leave_type",
            entity_id=row.id,
            before=before,
            after=after,
        )
    await access.db.commit()
    return LeaveTypeOut.model_validate(row)


@router.delete("/types/{type_id}", status_code=204)
async def archive_type(type_id: uuid.UUID, access: Writes) -> None:
    await _company(access, lock=True)
    row = await _type(access, type_id)
    before = _snapshot(row)
    row.archived_at = datetime.now(UTC)
    await access.audit(
        "leave.type_archived",
        entity_type="leave_type",
        entity_id=row.id,
        before=before,
        after=_snapshot(row),
    )
    await access.db.commit()
