"""Report job state and short-lived artifact links."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel

from app.modules.reports.reference import ReportType  # noqa: TC001


class ReportJobOut(BaseModel):
    id: uuid.UUID
    report_type: ReportType
    status: Literal["queued", "ready", "failed"]
    created_at: datetime
    finished_at: datetime | None
    error_code: str | None
    url: str | None = None
    expires_in: int | None = None
