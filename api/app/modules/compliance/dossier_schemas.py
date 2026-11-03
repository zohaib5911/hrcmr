"""Editable official link presentation; the server never fetches submitted URLs."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, date, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from app.core.schemas import RequestModel


class DossierLinkIn(RequestModel):
    section: Literal["licence", "rtw", "sms"]
    title: str = Field(min_length=1, max_length=160)
    url: str = Field(min_length=1, max_length=1000)
    checked_on: date
    position: int = Field(ge=0, le=10000)
    active: bool = True

    @field_validator("title", "url", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("url")
    @classmethod
    def official_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if (
            parts.scheme != "https"
            or parts.netloc != "www.gov.uk"
            or not parts.path.startswith("/")
            or any(char.isspace() for char in value)
        ):
            raise ValueError("Use a full https://www.gov.uk/ link.")
        return value

    @field_validator("checked_on")
    @classmethod
    def checked_date(cls, value: date) -> date:
        if value > datetime.now(UTC).date():
            raise ValueError("The date checked cannot be in the future.")
        return value


class DossierLinkOut(DossierLinkIn):
    id: uuid.UUID


class DossierOut(BaseModel):
    links: list[DossierLinkOut]
    checklist_url: str = "/compliance/rtw-checklist.pdf"
