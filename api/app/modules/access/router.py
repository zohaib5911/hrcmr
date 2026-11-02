"""User Access (plan.md 8.15): who in the company can sign in, with which role. This is the list;
inviting, role changes, suspending and the two-step policy come in T5.2 and T5.3."""

from __future__ import annotations

import uuid  # noqa: TC003  (Pydantic reads the annotations at run time)
from datetime import datetime  # noqa: TC003
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.modules.identity.models import Membership, User
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["access"])

Reads = Annotated[Access, Depends(require("rbac.user.read"))]

Role = Literal[
    "company_admin", "hr_admin", "people_manager", "recruiter", "employee", "read_only_auditor"
]
Status = Literal["active", "suspended"]
LIMIT = 500


class AccessUser(BaseModel):
    id: uuid.UUID = Field(description="The membership: this person's place in this company.")
    user_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    role: Role
    status: Status
    two_step: bool = Field(description="Whether they have set up two-step verification.")
    employee_id: uuid.UUID | None = Field(description="The HR record they are, if linked.")
    last_login_at: datetime | None
    is_you: bool


class AccessList(BaseModel):
    users: list[AccessUser]
    total: int = Field(description="Everyone in the company, whatever the filters.")
    unlinked: int = Field(description="Active users with no linked employee record.")


def _like(text_: str) -> str:
    escaped = text_.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("/users", response_model=AccessList)
async def list_users(
    access: Reads,
    role: Annotated[Role | None, Query()] = None,
    status: Annotated[Status | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100, description="Name or e-mail contains.")] = None,
) -> AccessList:
    query = select(Membership, User).join(User, User.id == Membership.user_id)
    if role:
        query = query.where(Membership.role == role)
    if status:
        query = query.where(Membership.status == status)
    if q and q.strip():
        pattern = _like(q.strip())
        query = query.where(
            or_(
                User.first_name.ilike(pattern, escape="\\"),
                User.last_name.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
                func.concat(User.first_name, " ", User.last_name).ilike(pattern, escape="\\"),
            )
        )
    rows = (
        await access.db.execute(
            query.order_by(func.lower(User.last_name), func.lower(User.first_name)).limit(LIMIT)
        )
    ).all()
    total = (await access.db.execute(select(func.count()).select_from(Membership))).scalar_one()
    unlinked = (
        await access.db.execute(
            select(func.count())
            .select_from(Membership)
            .where(Membership.status == "active", Membership.employee_id.is_(None))
        )
    ).scalar_one()
    return AccessList(
        users=[
            AccessUser(
                id=m.id,
                user_id=u.id,
                first_name=u.first_name,
                last_name=u.last_name,
                email=u.email,
                role=m.role,  # type: ignore[arg-type]
                status=m.status,  # type: ignore[arg-type]
                two_step=u.mfa_enabled,
                employee_id=m.employee_id,
                last_login_at=u.last_login_at,
                is_you=u.id == access.caller.user_id,
            )
            for m, u in rows
        ],
        total=total,
        unlinked=unlinked,
    )
