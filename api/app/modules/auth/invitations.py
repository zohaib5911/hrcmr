"""Invitations (plan.md 4.2): a single-use link, valid for 72 hours, that lets someone set their
own password. The administrator never sees or chooses it. Only the token's hash is stored."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.errors import AppError
from app.modules.auth.tokens import hash_token, new_token
from app.modules.identity.models import Invitation

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INVITATION_TTL = timedelta(hours=72)


class InvitationInvalidError(AppError):
    """One answer for unknown, expired and used links, so nothing is learned by guessing."""

    def __init__(self) -> None:
        super().__init__(
            "INVITATION_INVALID",
            "This invitation link is no longer valid. Ask for a new one.",
            status_code=410,
        )


async def create_invitation(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    email: str,
    role: str,
    invited_by: uuid.UUID | None,
    first_name: str | None = None,
    last_name: str | None = None,
    now: datetime | None = None,
) -> tuple[str, Invitation]:
    """Returns the token for the e-mailed link (shown once, never stored) and the invitation."""
    token = new_token()
    invitation = Invitation(
        company_id=company_id,
        email=email,
        role=role,
        first_name=first_name,
        last_name=last_name,
        token_hash=hash_token(token),
        expires_at=(now or datetime.now(UTC)) + INVITATION_TTL,
        invited_by=invited_by,
    )
    db.add(invitation)
    await db.flush()
    return token, invitation


async def find_valid_invitation(
    db: AsyncSession, token: str, *, now: datetime | None = None
) -> Invitation:
    invitation = (
        await db.execute(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    ).scalar_one_or_none()
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.expires_at <= (now or datetime.now(UTC))
    ):
        raise InvitationInvalidError
    return invitation


async def accept_invitation(
    db: AsyncSession, token: str, *, now: datetime | None = None
) -> Invitation:
    """Use the link up. A second use fails, as does one made after the 72 hours."""
    moment = now or datetime.now(UTC)
    invitation = await find_valid_invitation(db, token, now=moment)
    invitation.accepted_at = moment
    await db.flush()
    return invitation


async def renew_invitation(
    db: AsyncSession, invitation: Invitation, *, now: datetime | None = None
) -> str:
    """A fresh link and a fresh 72 hours for the same invitation; the old link stops working."""
    token = new_token()
    invitation.token_hash = hash_token(token)
    invitation.expires_at = (now or datetime.now(UTC)) + INVITATION_TTL
    await db.flush()
    return token
