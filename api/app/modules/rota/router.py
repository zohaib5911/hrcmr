"""Permission-scoped, audited rota settings with tenant-safe prerequisites (T9.4)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.errors import ConflictError, NotFoundError
from app.modules.companies.models import Company, Department, Designation
from app.modules.rbac.deps import Access, require
from app.modules.rota.models import DayOffPattern, LatePolicy, ShiftType
from app.modules.rota.schemas import (
    DayOffPatternIn,
    DayOffPatternOut,
    LatePolicyIn,
    LatePolicyOut,
    SettingScope,
    ShiftTypeIn,
    ShiftTypeOut,
)

router = APIRouter(prefix="/rota", tags=["rota"])
ShiftReads = Annotated[Access, Depends(require("rota.shift.read"))]
ShiftWrites = Annotated[Access, Depends(require("rota.shift.write"))]
LateReads = Annotated[Access, Depends(require("rota.late_policy.read"))]
LateWrites = Annotated[Access, Depends(require("rota.late_policy.write"))]
DayReads = Annotated[Access, Depends(require("rota.day_off.read"))]
DayWrites = Annotated[Access, Depends(require("rota.day_off.write"))]


async def _serialize(access: Access) -> None:
    # Settings have unique names/combinations. Serialize validation and save, including archives.
    await access.db.execute(
        select(Company.id).where(Company.id == access.company_id).with_for_update()
    )


async def _live[T: (ShiftType, LatePolicy, DayOffPattern)](
    access: Access, model: type[T], ident: uuid.UUID
) -> T:
    row = (
        await access.db.execute(
            select(model).where(model.id == ident, model.archived_at.is_(None)).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


async def _scope(
    access: Access,
    body: SettingScope,
    model: type[LatePolicy] | type[DayOffPattern],
    ident: uuid.UUID | None = None,
) -> None:
    department = (
        await access.db.execute(
            select(Department)
            .where(Department.id == body.department_id, Department.archived_at.is_(None))
            .with_for_update()
        )
    ).scalar_one_or_none()
    designation = (
        await access.db.execute(
            select(Designation)
            .where(Designation.id == body.designation_id, Designation.archived_at.is_(None))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if department is None or designation is None or designation.department_id != department.id:
        raise NotFoundError
    await _live(access, ShiftType, body.shift_type_id)
    duplicate = select(model.id).where(
        model.department_id == body.department_id,
        model.designation_id == body.designation_id,
        model.shift_type_id == body.shift_type_id,
        model.archived_at.is_(None),
    )
    if ident is not None:
        duplicate = duplicate.where(model.id != ident)
    if (await access.db.execute(duplicate)).first() is not None:
        raise ConflictError("A setting already exists for this department, designation and shift.")


async def _shift_name(access: Access, name: str, ident: uuid.UUID | None = None) -> None:
    query = select(ShiftType.id).where(
        func.lower(ShiftType.name) == name.lower(), ShiftType.archived_at.is_(None)
    )
    if ident is not None:
        query = query.where(ShiftType.id != ident)
    if (await access.db.execute(query)).first() is not None:
        raise ConflictError("A shift type already uses that name.", field="name")


@router.get("/shift-types", response_model=list[ShiftTypeOut])
async def shift_types(access: ShiftReads) -> list[ShiftTypeOut]:
    rows = (
        await access.db.execute(
            select(ShiftType)
            .where(ShiftType.archived_at.is_(None))
            .order_by(func.lower(ShiftType.name), ShiftType.id)
        )
    ).scalars()
    return [ShiftTypeOut.model_validate(r) for r in rows]


@router.post("/shift-types", status_code=201, response_model=ShiftTypeOut)
async def create_shift(body: ShiftTypeIn, access: ShiftWrites) -> ShiftTypeOut:
    await _serialize(access)
    await _shift_name(access, body.name)
    row = ShiftType(company_id=access.company_id, **body.model_dump())
    access.db.add(row)
    await access.db.flush()
    result = ShiftTypeOut.model_validate(row)
    await access.audit(
        "rota.shift_type_created",
        entity_type="shift_type",
        entity_id=row.id,
        after=result.model_dump(mode="json"),
    )
    await access.db.commit()
    return result


@router.put("/shift-types/{setting_id}", response_model=ShiftTypeOut)
async def update_shift(
    setting_id: uuid.UUID, body: ShiftTypeIn, access: ShiftWrites
) -> ShiftTypeOut:
    await _serialize(access)
    row = await _live(access, ShiftType, setting_id)
    await _shift_name(access, body.name, row.id)
    before = ShiftTypeOut.model_validate(row).model_dump(mode="json")
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    await access.db.flush()
    result = ShiftTypeOut.model_validate(row)
    if before != result.model_dump(mode="json"):
        await access.audit(
            "rota.shift_type_updated",
            entity_type="shift_type",
            entity_id=row.id,
            before=before,
            after=result.model_dump(mode="json"),
        )
    await access.db.commit()
    return result


@router.delete("/shift-types/{setting_id}", status_code=204)
async def archive_shift(setting_id: uuid.UUID, access: ShiftWrites) -> None:
    await _serialize(access)
    row = await _live(access, ShiftType, setting_id)
    for model in (LatePolicy, DayOffPattern):
        if (
            await access.db.execute(
                select(model.id)
                .where(model.shift_type_id == row.id, model.archived_at.is_(None))
                .limit(1)
            )
        ).first() is not None:
            raise ConflictError("Archive this shift's late policies and day off patterns first.")
    row.archived_at = datetime.now(UTC)
    await access.audit(
        "rota.shift_type_archived", entity_type="shift_type", entity_id=row.id, summary=row.name
    )
    await access.db.commit()


@router.get("/late-policies", response_model=list[LatePolicyOut])
async def late_policies(access: LateReads) -> list[LatePolicyOut]:
    rows = (
        await access.db.execute(
            select(LatePolicy).where(LatePolicy.archived_at.is_(None)).order_by(LatePolicy.id)
        )
    ).scalars()
    return [LatePolicyOut.model_validate(r) for r in rows]


@router.post("/late-policies", status_code=201, response_model=LatePolicyOut)
async def create_late(body: LatePolicyIn, access: LateWrites) -> LatePolicyOut:
    await _serialize(access)
    await _scope(access, body, LatePolicy)
    row = LatePolicy(company_id=access.company_id, **body.model_dump())
    access.db.add(row)
    await access.db.flush()
    result = LatePolicyOut.model_validate(row)
    await access.audit(
        "rota.late_policy_created",
        entity_type="late_policy",
        entity_id=row.id,
        after=result.model_dump(mode="json"),
    )
    await access.db.commit()
    return result


@router.put("/late-policies/{setting_id}", response_model=LatePolicyOut)
async def update_late(
    setting_id: uuid.UUID, body: LatePolicyIn, access: LateWrites
) -> LatePolicyOut:
    await _serialize(access)
    row = await _live(access, LatePolicy, setting_id)
    await _scope(access, body, LatePolicy, row.id)
    before = LatePolicyOut.model_validate(row).model_dump(mode="json")
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    await access.db.flush()
    result = LatePolicyOut.model_validate(row)
    if before != result.model_dump(mode="json"):
        await access.audit(
            "rota.late_policy_updated",
            entity_type="late_policy",
            entity_id=row.id,
            before=before,
            after=result.model_dump(mode="json"),
        )
    await access.db.commit()
    return result


@router.delete("/late-policies/{setting_id}", status_code=204)
async def archive_late(setting_id: uuid.UUID, access: LateWrites) -> None:
    await _serialize(access)
    row = await _live(access, LatePolicy, setting_id)
    row.archived_at = datetime.now(UTC)
    await access.audit("rota.late_policy_archived", entity_type="late_policy", entity_id=row.id)
    await access.db.commit()


@router.get("/day-off-patterns", response_model=list[DayOffPatternOut])
async def day_off_patterns(access: DayReads) -> list[DayOffPatternOut]:
    rows = (
        await access.db.execute(
            select(DayOffPattern)
            .where(DayOffPattern.archived_at.is_(None))
            .order_by(DayOffPattern.id)
        )
    ).scalars()
    return [DayOffPatternOut.model_validate(r) for r in rows]


@router.post("/day-off-patterns", status_code=201, response_model=DayOffPatternOut)
async def create_day_off(body: DayOffPatternIn, access: DayWrites) -> DayOffPatternOut:
    await _serialize(access)
    await _scope(access, body, DayOffPattern)
    row = DayOffPattern(company_id=access.company_id, **body.model_dump())
    access.db.add(row)
    await access.db.flush()
    result = DayOffPatternOut.model_validate(row)
    await access.audit(
        "rota.day_off_pattern_created",
        entity_type="day_off_pattern",
        entity_id=row.id,
        after=result.model_dump(mode="json"),
    )
    await access.db.commit()
    return result


@router.put("/day-off-patterns/{setting_id}", response_model=DayOffPatternOut)
async def update_day_off(
    setting_id: uuid.UUID, body: DayOffPatternIn, access: DayWrites
) -> DayOffPatternOut:
    await _serialize(access)
    row = await _live(access, DayOffPattern, setting_id)
    await _scope(access, body, DayOffPattern, row.id)
    before = DayOffPatternOut.model_validate(row).model_dump(mode="json")
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    await access.db.flush()
    result = DayOffPatternOut.model_validate(row)
    if before != result.model_dump(mode="json"):
        await access.audit(
            "rota.day_off_pattern_updated",
            entity_type="day_off_pattern",
            entity_id=row.id,
            before=before,
            after=result.model_dump(mode="json"),
        )
    await access.db.commit()
    return result


@router.delete("/day-off-patterns/{setting_id}", status_code=204)
async def archive_day_off(setting_id: uuid.UUID, access: DayWrites) -> None:
    await _serialize(access)
    row = await _live(access, DayOffPattern, setting_id)
    row.archived_at = datetime.now(UTC)
    await access.audit(
        "rota.day_off_pattern_archived", entity_type="day_off_pattern", entity_id=row.id
    )
    await access.db.commit()
