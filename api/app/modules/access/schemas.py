from __future__ import annotations

import uuid  # noqa: TC003  (Pydantic reads the annotations at run time)
from datetime import datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.schemas import RequestModel

Role = Literal[
    "company_admin", "hr_admin", "people_manager", "recruiter", "employee", "read_only_auditor"
]
Status = Literal["active", "suspended", "invited"]


class AccessUser(BaseModel):
    id: uuid.UUID = Field(description="The membership, or the invitation while it is pending.")
    user_id: uuid.UUID | None = Field(description="Empty until the invitation is accepted.")
    first_name: str
    last_name: str
    email: str
    role: Role
    status: Status
    two_step: bool = Field(description="Whether they have set up two-step verification.")
    employee_id: uuid.UUID | None = Field(description="The HR record they are, if linked.")
    last_login_at: datetime | None
    invite_expires_at: datetime | None = Field(description="While invited: when the link ends.")
    is_you: bool


class AccessList(BaseModel):
    users: list[AccessUser]
    total: int = Field(description="Everyone in the company, whatever the filters.")
    unlinked: int = Field(description="Active users with no linked employee record.")


class InviteIn(RequestModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    role: Role


class RoleIn(RequestModel):
    role: Role
