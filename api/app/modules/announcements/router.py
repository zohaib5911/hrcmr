"""The announcement banners a company sees (T17.5). Any signed-in person in the company can read
the live ones for the company's region; nothing here changes a banner (platform_admin does)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.modules.announcements.models import Announcement
from app.modules.announcements.schemas import CompanyAnnouncementOut, CompanyAnnouncementsOut
from app.modules.companies.models import Company
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["announcements"])
Reader = Annotated[Access, Depends(require("company.overview.read"))]


@router.get("/company/announcements", response_model=CompanyAnnouncementsOut)
async def live_announcements(access: Reader) -> CompanyAnnouncementsOut:
    now = datetime.now(UTC)
    region = await access.db.scalar(select(Company.region).where(Company.id == access.company_id))
    found = (
        (
            await access.db.execute(
                select(Announcement)
                .where(
                    Announcement.region == region,
                    Announcement.starts_at <= now,
                    Announcement.ends_at > now,
                    Announcement.ended_at.is_(None),
                )
                .order_by(Announcement.starts_at.desc())
            )
        )
        .scalars()
        .all()
    )
    items = [
        CompanyAnnouncementOut(id=item.id, title=item.title, body=item.body, ends_at=item.ends_at)
        for item in found
    ]
    return CompanyAnnouncementsOut(items=items)
