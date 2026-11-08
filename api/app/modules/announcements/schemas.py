"""What a company sees of the announcement banners (T17.5): the live ones for its region."""

from __future__ import annotations

import uuid  # noqa: TC003  (pydantic reads the field types at runtime)
from datetime import datetime  # noqa: TC003  (same)

from pydantic import BaseModel


class CompanyAnnouncementOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    ends_at: datetime


class CompanyAnnouncementsOut(BaseModel):
    items: list[CompanyAnnouncementOut]
