"""Company document metadata and review projections."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.core.schemas import RequestModel
from app.modules.documents.reference import DocumentCategory  # noqa: TC001

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class CompanyDocumentEdit(RequestModel):
    title: Title
    category: DocumentCategory
    next_review_date: date | None = None


class CompanyDocumentOut(BaseModel):
    id: uuid.UUID
    file_id: uuid.UUID
    title: str
    category: DocumentCategory
    next_review_date: date | None
    review_status: Literal["no_review_date", "current", "review_due", "overdue"]
    file_name: str
    size: int
    scan_status: Literal["pending", "clean", "infected", "error"]
    uploaded_at: datetime
    archived_at: datetime | None


class CompanyDocuments(BaseModel):
    items: list[CompanyDocumentOut]
    total: int
    today: date
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
