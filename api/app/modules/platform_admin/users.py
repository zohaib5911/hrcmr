"""Users for the platform admins (T17.2): search by e-mail, lock and unlock.

A lock sets ``users.is_active`` to false. That is the existing "account is off" flag: sign-in
refuses an inactive user, and every request with a live session is refused too (``_caller`` in
auth/deps.py), so the lock takes effect at once and the unlock restores access.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy and pydantic read the types at runtime)

from sqlalchemy import select

from app.core.errors import AppError, NotFoundError
from app.db.session import GlobalSession  # noqa: TC001
from app.modules.audit.service import AuditContext, record
from app.modules.companies.models import Company
from app.modules.identity.models import Membership, User
from app.modules.platform_admin.companies import like
from app.modules.platform_admin.schemas import UserCompanyOut, UserRow, UsersOut

SEARCH_MIN = 3
SEARCH_LIMIT = 25


async def search(db: GlobalSession, q: str) -> UsersOut:
    users = list(
        (
            await db.execute(
                select(User)
                .where(User.email.ilike(like(q.strip())))
                .order_by(User.email)
                .limit(SEARCH_LIMIT)
            )
        ).scalars()
    )
    companies = await _companies(db, [user.id for user in users])
    return UsersOut(items=[_row(user, companies.get(user.id, [])) for user in users])


async def row(db: GlobalSession, user: User) -> UserRow:
    companies = await _companies(db, [user.id])
    return _row(user, companies.get(user.id, []))


async def _companies(
    db: GlobalSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[UserCompanyOut]]:
    found: dict[uuid.UUID, list[UserCompanyOut]] = {}
    if not user_ids:
        return found
    rows = await db.execute(
        select(Membership, Company)
        .join(Company, Company.id == Membership.company_id)
        .where(Membership.user_id.in_(user_ids))
        .order_by(Company.name)
    )
    for membership, company in rows.all():
        found.setdefault(membership.user_id, []).append(
            UserCompanyOut(
                id=company.id, name=company.name, role=membership.role, status=membership.status
            )
        )
    return found


def _row(user: User, companies: list[UserCompanyOut]) -> UserRow:
    return UserRow(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        locked=not user.is_active,
        mfa_enabled=user.mfa_enabled,
        email_verified=user.email_verified_at is not None,
        last_login_at=user.last_login_at,
        companies=companies,
    )


async def user_or_404(db: GlobalSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("We could not find that user.")
    return user


async def lock(db: GlobalSession, context: AuditContext, user: User, reason: str | None) -> None:
    if user.id == context.actor_user_id:
        raise AppError("SELF_LOCK", "You cannot lock your own account.", status_code=409)
    if not user.is_active:
        raise AppError("ALREADY_LOCKED", "This user is already locked.", status_code=409)
    user.is_active = False
    await record(
        db,
        context,
        "platform.user_locked",
        entity_type="user",
        entity_id=user.id,
        before={"is_active": True},
        after={"is_active": False},
        reason=reason,
    )


async def unlock(db: GlobalSession, context: AuditContext, user: User, reason: str | None) -> None:
    if user.is_active:
        raise AppError("NOT_LOCKED", "This user is not locked.", status_code=409)
    user.is_active = True
    await record(
        db,
        context,
        "platform.user_unlocked",
        entity_type="user",
        entity_id=user.id,
        before={"is_active": False},
        after={"is_active": True},
        reason=reason,
    )
