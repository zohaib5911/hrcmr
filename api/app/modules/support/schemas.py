"""Request and response shapes for support mode (T17.3)."""

from __future__ import annotations

import uuid  # noqa: TC003  (pydantic reads the field types at runtime)
from datetime import datetime  # noqa: TC003  (pydantic reads the field types at runtime)

from pydantic import BaseModel, Field

from app.core.schemas import RequestModel
from app.modules.platform_admin.schemas import REASON_MAX, REASON_MIN


class SupportStartIn(RequestModel):
    reason: str = Field(min_length=REASON_MIN, max_length=REASON_MAX)
    ticket_ref: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9#._/-]*$")


class SupportWritesIn(RequestModel):
    enabled: bool
    confirm: bool = Field(
        default=False,
        description="The second confirmation: must be true to turn writes on.",
    )


class SupportSessionOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str
    ticket_ref: str
    expires_at: datetime
    write_enabled: bool
    ended_at: datetime | None
