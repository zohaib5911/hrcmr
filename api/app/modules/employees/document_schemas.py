"""Employee document metadata (T6.7)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel

DocumentCategory = Literal[
    "employment_contract",
    "letter",
    "hr_record",
    "id_document",
    "rtw_evidence",
    "certificate",
    "payslip",
    "other",
]


class EmployeeDocumentOut(BaseModel):
    id: uuid.UUID
    file_id: uuid.UUID
    file_name: str
    category: DocumentCategory
    notes: str | None
    size: int
    scan_status: Literal["pending", "clean", "infected", "error"]
    uploaded_at: datetime
