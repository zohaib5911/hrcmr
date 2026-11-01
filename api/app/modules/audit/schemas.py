from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Any, Literal

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    action: str
    actor_type: Literal["user", "platform_admin", "system"]
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    entity_type: str | None
    entity_id: uuid.UUID | None
    summary: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    reason: str | None
    ip: str | None
    user_agent: str | None
    request_id: str | None


class AuditPage(BaseModel):
    items: list[AuditEventOut]
    next_cursor: str | None
