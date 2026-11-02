"""Locations, departments and designations (plan.md 8.15): the company's own places and job titles.

Nothing here is deleted: a record that is no longer used is archived, so people and documents that
point at it keep making sense.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, update

from app.core.errors import AppError, ConflictError, NotFoundError
from app.integrations.postcodes import PostcodeError, Postcodes, normalise_postcode
from app.modules.companies.models import Department, Designation, Location
from app.modules.companies.structure_schemas import (
    DepartmentIn,
    DepartmentOut,
    DesignationIn,
    DesignationOut,
    DesignationPatch,
    LocationIn,
    LocationOut,
    LocationPatch,
    PostcodeOut,
)
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["company"])

Reads = Annotated[Access, Depends(require("company.location.read"))]
Writes = Annotated[Access, Depends(require("company.location.write"))]


def _now() -> datetime:
    return datetime.now(UTC)


async def _clear_default(
    db: AsyncSession, company_id: uuid.UUID, *, except_id: uuid.UUID | None = None
) -> None:
    """Take the default away from every other location, just before another is made the default
    (the database allows only one at a time)."""
    query = update(Location).where(
        Location.company_id == company_id,
        Location.is_default.is_(True),
        Location.archived_at.is_(None),
    )
    if except_id is not None:
        query = query.where(Location.id != except_id)
    await db.execute(query.values(is_default=False))


def _location_out(row: Location) -> LocationOut:
    return LocationOut(
        id=row.id,
        name=row.name,
        postcode=row.postcode,
        address_line1=row.address_line1,
        address_line2=row.address_line2,
        address_line3=row.address_line3,
        city=row.city,
        county=row.county,
        country=row.country,
        is_default=row.is_default,
    )


def _snapshot(row: Location) -> dict[str, object]:
    return LocationOut.model_validate(_location_out(row)).model_dump(mode="json", exclude={"id"})


async def _location(access: Access, location_id: uuid.UUID) -> Location:
    row = (
        await access.db.execute(
            select(Location).where(Location.id == location_id, Location.archived_at.is_(None))
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


@router.get("/locations", summary="The company's locations, the default first")
async def list_locations(access: Reads) -> list[LocationOut]:
    rows = (
        await access.db.execute(
            select(Location)
            .where(Location.archived_at.is_(None))
            .order_by(Location.is_default.desc(), func.lower(Location.name))
        )
    ).scalars()
    return [_location_out(row) for row in rows]


@router.get("/locations/lookup/{postcode}", summary="Town and county for a postcode")
async def look_up_postcode(postcode: str, request: Request, _: Writes) -> PostcodeOut:
    normal = normalise_postcode(postcode)
    if normal is None:
        raise AppError(
            "VALIDATION_ERROR",
            "Enter a UK postcode, such as SW1A 1AA.",
            status_code=422,
            field="postcode",
        )
    service: Postcodes = request.app.state.postcodes
    try:
        found = await service.lookup(normal)
    except PostcodeError as exc:
        if not exc.found:
            raise AppError(
                "NOT_FOUND", "We could not find that postcode.", status_code=404, field="postcode"
            ) from None
        raise AppError(
            "SERVICE_UNAVAILABLE",
            "The postcode lookup is not answering. Type the address instead.",
            status_code=503,
        ) from None
    return PostcodeOut(
        postcode=found.postcode, city=found.city, county=found.county, country=found.country
    )


@router.post("/locations", status_code=201, summary="Add a location")
async def create_location(body: LocationIn, access: Writes) -> LocationOut:
    first = (
        await access.db.execute(
            select(func.count()).select_from(Location).where(Location.archived_at.is_(None))
        )
    ).scalar_one() == 0
    row = Location(company_id=access.company_id, **body.model_dump())
    row.is_default = body.is_default or first  # the first one is the default
    if row.is_default:
        await _clear_default(access.db, access.company_id)
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "location.created", entity_type="location", entity_id=row.id, after=_snapshot(row)
    )
    await access.db.commit()
    return _location_out(row)


@router.patch("/locations/{location_id}", summary="Change a location")
async def update_location(
    location_id: uuid.UUID, body: LocationPatch, access: Writes
) -> LocationOut:
    row = await _location(access, location_id)
    before = _snapshot(row)
    changes = body.model_dump(exclude_unset=True)
    for required in ("name", "postcode", "address_line1", "city", "country"):
        if required in changes and changes[required] is None:
            raise AppError(
                "VALIDATION_ERROR", "That cannot be empty.", status_code=422, field=required
            )
    if changes.get("is_default") is False and row.is_default:
        raise ConflictError("Make another location the default instead.", field="is_default")
    if changes.get("is_default") is True and not row.is_default:
        await _clear_default(access.db, access.company_id, except_id=row.id)
    for name, value in changes.items():
        setattr(row, name, value)
    await access.db.flush()
    after = _snapshot(row)
    if before != after:
        await access.audit(
            "location.updated", entity_type="location", entity_id=row.id, before=before, after=after
        )
    await access.db.commit()
    return _location_out(row)


@router.delete("/locations/{location_id}", status_code=204, summary="Archive a location")
async def archive_location(location_id: uuid.UUID, access: Writes) -> None:
    row = await _location(access, location_id)
    others = (
        await access.db.execute(
            select(func.count())
            .select_from(Location)
            .where(Location.archived_at.is_(None), Location.id != row.id)
        )
    ).scalar_one()
    if row.is_default and others > 0:
        raise ConflictError("Make another location the default before archiving this one.")
    row.archived_at = _now()
    row.is_default = False
    await access.audit(
        "location.archived", entity_type="location", entity_id=row.id, summary=row.name
    )
    await access.db.commit()


# --- departments ---------------------------------------------------------------------------------

DeptReads = Annotated[Access, Depends(require("company.department.read"))]
DeptWrites = Annotated[Access, Depends(require("company.department.write"))]


async def _department(access: Access, department_id: uuid.UUID) -> Department:
    row = (
        await access.db.execute(
            select(Department).where(
                Department.id == department_id, Department.archived_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


async def _taken(access: Access, name: str, *, except_id: uuid.UUID | None = None) -> bool:
    query = select(Department.id).where(
        func.lower(Department.name) == name.lower(), Department.archived_at.is_(None)
    )
    if except_id:
        query = query.where(Department.id != except_id)
    return (await access.db.execute(query)).first() is not None


@router.get("/departments", summary="The company's departments")
async def list_departments(access: DeptReads) -> list[DepartmentOut]:
    rows = (
        await access.db.execute(
            select(Department, func.count(Designation.id))
            .outerjoin(
                Designation,
                (Designation.department_id == Department.id) & Designation.archived_at.is_(None),
            )
            .where(Department.archived_at.is_(None))
            .group_by(Department.id)
            .order_by(func.lower(Department.name))
        )
    ).all()
    return [DepartmentOut(id=d.id, name=d.name, designations=count) for d, count in rows]


@router.post("/departments", status_code=201, summary="Add a department")
async def create_department(body: DepartmentIn, access: DeptWrites) -> DepartmentOut:
    if await _taken(access, body.name):
        raise ConflictError("You already have a department with that name.", field="name")
    row = Department(company_id=access.company_id, name=body.name)
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "department.created", entity_type="department", entity_id=row.id, after={"name": row.name}
    )
    await access.db.commit()
    return DepartmentOut(id=row.id, name=row.name, designations=0)


@router.patch("/departments/{department_id}", summary="Rename a department")
async def rename_department(
    department_id: uuid.UUID, body: DepartmentIn, access: DeptWrites
) -> DepartmentOut:
    row = await _department(access, department_id)
    if await _taken(access, body.name, except_id=row.id):
        raise ConflictError("You already have a department with that name.", field="name")
    before = {"name": row.name}
    row.name = body.name
    if before["name"] != row.name:
        await access.audit(
            "department.updated",
            entity_type="department",
            entity_id=row.id,
            before=before,
            after={"name": row.name},
        )
    await access.db.commit()
    count = (
        await access.db.execute(
            select(func.count())
            .select_from(Designation)
            .where(Designation.department_id == row.id, Designation.archived_at.is_(None))
        )
    ).scalar_one()
    return DepartmentOut(id=row.id, name=row.name, designations=count)


@router.delete("/departments/{department_id}", status_code=204, summary="Archive a department")
async def archive_department(department_id: uuid.UUID, access: DeptWrites) -> None:
    row = await _department(access, department_id)
    titles = (
        await access.db.execute(
            select(func.count())
            .select_from(Designation)
            .where(Designation.department_id == row.id, Designation.archived_at.is_(None))
        )
    ).scalar_one()
    if titles:
        raise ConflictError("Archive or move this department's job titles first.")
    row.archived_at = _now()
    await access.audit(
        "department.archived", entity_type="department", entity_id=row.id, summary=row.name
    )
    await access.db.commit()


# --- designations --------------------------------------------------------------------------------

DesReads = Annotated[Access, Depends(require("settings.designation.read"))]
DesWrites = Annotated[Access, Depends(require("settings.designation.write"))]


def _designation_out(row: Designation, department: str) -> DesignationOut:
    return DesignationOut(
        id=row.id,
        title=row.title,
        department_id=row.department_id,
        department_name=department,
        soc_code=row.soc_code,
    )


async def _designation(access: Access, designation_id: uuid.UUID) -> tuple[Designation, str]:
    found = (
        await access.db.execute(
            select(Designation, Department.name)
            .join(Department, Department.id == Designation.department_id)
            .where(Designation.id == designation_id, Designation.archived_at.is_(None))
        )
    ).first()
    if found is None:
        raise NotFoundError
    return found[0], found[1]


async def _check_title_free(
    access: Access, department_id: uuid.UUID, title: str, *, except_id: uuid.UUID | None = None
) -> None:
    query = select(Designation.id).where(
        Designation.department_id == department_id,
        func.lower(Designation.title) == title.lower(),
        Designation.archived_at.is_(None),
    )
    if except_id:
        query = query.where(Designation.id != except_id)
    if (await access.db.execute(query)).first() is not None:
        raise ConflictError(
            "That department already has a job title with that name.", field="title"
        )


@router.get("/designations", summary="Job titles, by department")
async def list_designations(access: DesReads) -> list[DesignationOut]:
    rows = (
        await access.db.execute(
            select(Designation, Department.name)
            .join(Department, Department.id == Designation.department_id)
            .where(Designation.archived_at.is_(None))
            .order_by(func.lower(Department.name), func.lower(Designation.title))
        )
    ).all()
    return [_designation_out(row, department) for row, department in rows]


@router.post("/designations", status_code=201, summary="Add a job title")
async def create_designation(body: DesignationIn, access: DesWrites) -> DesignationOut:
    department = await _department(access, body.department_id)
    await _check_title_free(access, department.id, body.title)
    row = Designation(
        company_id=access.company_id,
        department_id=department.id,
        title=body.title,
        soc_code=body.soc_code,
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "designation.created",
        entity_type="designation",
        entity_id=row.id,
        after={"title": row.title, "department": department.name, "soc_code": row.soc_code},
    )
    await access.db.commit()
    return _designation_out(row, department.name)


@router.patch("/designations/{designation_id}", summary="Change a job title")
async def update_designation(
    designation_id: uuid.UUID, body: DesignationPatch, access: DesWrites
) -> DesignationOut:
    row, department_name = await _designation(access, designation_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("title", "x") is None or changes.get("department_id", "x") is None:
        raise AppError("VALIDATION_ERROR", "That cannot be empty.", status_code=422)
    before = {"title": row.title, "department": department_name, "soc_code": row.soc_code}
    if "department_id" in changes and changes["department_id"] != row.department_id:
        department = await _department(access, changes["department_id"])
        row.department_id, department_name = department.id, department.name
    if "title" in changes:
        row.title = changes["title"]
    if "soc_code" in changes:
        row.soc_code = changes["soc_code"]
    await _check_title_free(access, row.department_id, row.title, except_id=row.id)
    after = {"title": row.title, "department": department_name, "soc_code": row.soc_code}
    if before != after:
        await access.audit(
            "designation.updated",
            entity_type="designation",
            entity_id=row.id,
            before=before,
            after=after,
        )
    await access.db.commit()
    return _designation_out(row, department_name)


@router.delete("/designations/{designation_id}", status_code=204, summary="Archive a job title")
async def archive_designation(designation_id: uuid.UUID, access: DesWrites) -> None:
    row, _ = await _designation(access, designation_id)
    row.archived_at = _now()
    await access.audit(
        "designation.archived", entity_type="designation", entity_id=row.id, summary=row.title
    )
    await access.db.commit()
