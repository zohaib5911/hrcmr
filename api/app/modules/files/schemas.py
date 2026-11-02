from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel


class FileOut(BaseModel):
    id: uuid.UUID
    original_name: str
    mime: str
    size: int
    sha256: str
    scan_status: Literal["pending", "clean", "infected", "error"]
    category: str | None
    owner_type: str | None
    owner_id: uuid.UUID | None
    created_at: datetime


class DownloadOut(BaseModel):
    """A link that works for ``expires_in`` seconds, then stops."""

    url: str
    expires_in: int
