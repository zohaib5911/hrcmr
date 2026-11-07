"""The super-admin course editor (plan 8.14): courses are our content, edited only here."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.errors import ConflictError, NotFoundError
from app.modules.audit.service import record
from app.modules.learning import service
from app.modules.learning.models import Course
from app.modules.learning.schemas import CourseAdminOut, CourseIn
from app.modules.rbac.platform import PlatformAccess, require_platform

router = APIRouter(tags=["learning-admin"])
Content = Annotated[PlatformAccess, Depends(require_platform("platform.content.write"))]


async def _slug_taken(access: PlatformAccess, slug: str, *, except_id: uuid.UUID | None) -> bool:
    query = select(Course.id).where(Course.slug == slug)
    if except_id is not None:
        query = query.where(Course.id != except_id)
    return (await access.db.execute(query.limit(1))).first() is not None


@router.get("/admin/courses", response_model=list[CourseAdminOut])
async def admin_courses(access: Content) -> list[CourseAdminOut]:
    rows = (await access.db.execute(select(Course).order_by(Course.title))).scalars().all()
    return [service.admin_out(row) for row in rows]


@router.post("/admin/courses", status_code=201, response_model=CourseAdminOut)
async def create_course(body: CourseIn, access: Content) -> CourseAdminOut:
    if await _slug_taken(access, body.slug, except_id=None):
        raise ConflictError("A course with this slug already exists.", field="slug")
    row = Course(
        **body.model_dump(),
        version=1,
        created_by=access.caller.user_id,
        updated_by=access.caller.user_id,
    )
    access.db.add(row)
    await access.db.flush()
    await access.db.refresh(row)
    await record(
        access.db,
        access.audit_context,
        "platform.course_created",
        entity_type="course",
        entity_id=row.id,
        after={"slug": body.slug, "published": body.published},
    )
    await access.db.commit()
    return service.admin_out(row)


@router.put("/admin/courses/{course_id}", response_model=CourseAdminOut)
async def update_course(course_id: uuid.UUID, body: CourseIn, access: Content) -> CourseAdminOut:
    row = (
        await access.db.execute(select(Course).where(Course.id == course_id).with_for_update())
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    if await _slug_taken(access, body.slug, except_id=row.id):
        raise ConflictError("A course with this slug already exists.", field="slug")
    before = service.admin_out(row).model_dump(mode="json")
    values = body.model_dump()
    changed = any(getattr(row, key) != value for key, value in values.items())
    for key, value in values.items():
        setattr(row, key, value)
    if changed:
        row.version += 1
    row.updated_by = access.caller.user_id
    await record(
        access.db,
        access.audit_context,
        "platform.course_updated",
        entity_type="course",
        entity_id=row.id,
        before={"version": before["version"], "published": before["published"]},
        after={"version": row.version, "published": row.published},
    )
    await access.db.commit()
    return service.admin_out(row)
