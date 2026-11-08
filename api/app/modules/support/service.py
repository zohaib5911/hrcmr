"""Support mode (T17.3, plan 8.18): start, turn writes on or off, end.

Each step is recorded twice: once in the company's own audit trail (``support.session.*``, with the
company, so the company sees who looked and why), and once in the platform's trail
(``platform.support_*``, with no company, shown on the company detail page).
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.errors import AppError, NotFoundError
from app.modules.audit.service import AuditContext, record
from app.modules.companies.models import Company
from app.modules.support.models import ImpersonationSession
from app.modules.support.schemas import SupportSessionOut

if TYPE_CHECKING:
    from app.db.session import GlobalSession
    from app.modules.auth.sessions import SessionStore

SUPPORT_LIFETIME = timedelta(minutes=30)
WRITES_ON = "Support mode can now make changes"
WRITES_OFF = "Support mode is read-only again"


def now() -> datetime:
    return datetime.now(UTC)


def is_live(row: ImpersonationSession, at: datetime) -> bool:
    return row.ended_at is None and row.expires_at > at


def out(row: ImpersonationSession, company_name: str) -> SupportSessionOut:
    return SupportSessionOut(
        id=row.id,
        company_id=row.company_id,
        company_name=company_name,
        ticket_ref=row.ticket_ref,
        expires_at=row.expires_at,
        write_enabled=row.write_enabled_at is not None,
        ended_at=row.ended_at,
    )


async def _record_both(
    db: GlobalSession,
    context: AuditContext,
    row: ImpersonationSession,
    *,
    company_action: str,
    platform_action: str,
    summary: str,
    reason: str | None = None,
) -> None:
    await db.company_for_this_transaction(row.company_id)
    company_context = replace(context, company_id=row.company_id, impersonation_session_id=row.id)
    await record(
        db,
        company_context,
        company_action,
        entity_type="impersonation_session",
        entity_id=row.id,
        summary=summary,
        reason=reason,
    )
    await record(
        db,
        replace(context, company_id=None, impersonation_session_id=row.id),
        platform_action,
        entity_type="company",
        entity_id=row.company_id,
        summary=summary,
        reason=reason,
    )


async def start(
    db: GlobalSession,
    sessions: SessionStore,
    context: AuditContext,
    *,
    company_id: uuid.UUID,
    admin_id: uuid.UUID,
    reason: str,
    ticket_ref: str,
    ip: str | None,
    user_agent: str | None,
) -> tuple[str, ImpersonationSession, Company]:
    """Open a read-only support session on an active company. Returns the cookie token.

    An admin has one support session at a time: any other live one of theirs is ended first."""
    company = (
        await db.execute(select(Company).where(Company.id == company_id))
    ).scalar_one_or_none()
    if company is None:
        raise NotFoundError
    if company.status != "active":
        raise AppError("NOT_ACTIVE", "Support mode is only for an active company.", status_code=409)
    at = now()
    open_rows = (
        await db.execute(
            select(ImpersonationSession).where(
                ImpersonationSession.started_by == admin_id,
                ImpersonationSession.ended_at.is_(None),
                ImpersonationSession.expires_at > at,
            )
        )
    ).scalars()
    for previous in open_rows.all():
        await end(db, sessions, context, previous, admin_id=admin_id, why="replaced")
    row = ImpersonationSession(
        company_id=company.id,
        started_by=admin_id,
        reason=reason,
        ticket_ref=ticket_ref,
        expires_at=at + SUPPORT_LIFETIME,
    )
    await db.company_for_this_transaction(company.id)
    db.add(row)
    await db.flush()
    token, data = await sessions.create(
        db,
        user_id=admin_id,
        company_id=company.id,
        ip=ip,
        user_agent=user_agent,
        mfa_passed=True,
        absolute_expiry=row.expires_at,
        support_id=row.id,
    )
    row.session_id = uuid.UUID(data.session_id)
    await _record_both(
        db,
        context,
        row,
        company_action="support.session.started",
        platform_action="platform.support_started",
        summary=f"Support mode started (read-only), ticket {ticket_ref}",
        reason=reason,
    )
    return token, row, company


async def set_writes(
    db: GlobalSession,
    context: AuditContext,
    row: ImpersonationSession,
    *,
    admin_id: uuid.UUID,
    enabled: bool,
) -> None:
    if not is_live(row, now()):
        raise AppError("SUPPORT_SESSION_ENDED", "That support session has ended.", status_code=409)
    if enabled == (row.write_enabled_at is not None):
        return
    row.write_enabled_at = now() if enabled else None
    row.write_enabled_by = admin_id if enabled else None
    await _record_both(
        db,
        context,
        row,
        company_action="support.session.writes_changed",
        platform_action="platform.support_writes_changed",
        summary=WRITES_ON if enabled else WRITES_OFF,
    )


async def end(
    db: GlobalSession,
    sessions: SessionStore,
    context: AuditContext,
    row: ImpersonationSession,
    *,
    admin_id: uuid.UUID,
    why: str = "ended",
) -> None:
    """End a support session (idempotent) and its server-side session."""
    if row.ended_at is not None:
        return
    row.ended_at = now()
    row.ended_by = admin_id
    if row.session_id is not None:
        await sessions.revoke_id(db, row.session_id)
    await _record_both(
        db,
        context,
        row,
        company_action="support.session.ended",
        platform_action="platform.support_ended",
        summary="Support mode replaced by a new one" if why == "replaced" else "Support mode ended",
    )


async def row_or_404(db: GlobalSession, support_id: uuid.UUID) -> ImpersonationSession:
    row = (
        await db.execute(select(ImpersonationSession).where(ImpersonationSession.id == support_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


async def company_name(db: GlobalSession, company_id: uuid.UUID) -> str:
    return str(
        (await db.execute(select(Company.name).where(Company.id == company_id))).scalar_one()
    )
