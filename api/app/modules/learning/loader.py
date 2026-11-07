"""Loads course files (one JSON course per file) into the ``courses`` table (plan 8.14).

Every file goes through the same validation as the super-admin editor. One bad file stops the whole
load, so a half-loaded set of courses never reaches the database. A course is matched by its slug;
its version goes up only when its content changes.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.learning.models import Course
from app.modules.learning.schemas import CourseIn

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession


def _read_courses(directory: Path) -> list[CourseIn]:
    return [
        CourseIn.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


async def load_courses(db: AsyncSession, directory: Path) -> int:
    # The files are read in a thread: reading them is blocking I/O.
    courses = await asyncio.to_thread(_read_courses, directory)
    for data in courses:
        values = data.model_dump()
        row = (
            await db.execute(select(Course).where(Course.slug == data.slug))
        ).scalar_one_or_none()
        if row is None:
            db.add(Course(**values, version=1))
            continue
        changed = any(getattr(row, key) != value for key, value in values.items())
        for key, value in values.items():
            setattr(row, key, value)
        if changed:
            row.version += 1
    await db.flush()
    return len(courses)
