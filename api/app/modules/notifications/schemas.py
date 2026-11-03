"""Compliance notifications for the bell; personal content belongs only to its recipient."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel

from app.core.schemas import RequestModel
from app.modules.compliance.hub_schemas import AttentionItem  # noqa: TC001


class NotificationOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str | None
    link: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    next_cursor: str | None
    unread: int
    needs_attention: list[AttentionItem]
    attention_count: int


class NotificationReadIn(RequestModel):
    read: Literal[True] = True


class NotificationsReadOut(BaseModel):
    marked: int
