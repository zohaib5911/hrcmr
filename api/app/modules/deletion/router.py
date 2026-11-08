"""Delete the company account (plan 8.16, API item 22, T16.5).

A Company Admin asks; a 6-digit code goes to their e-mail; entering it schedules the deletion for 7
days later and tells the other Company Admins and support. Any Company Admin can withdraw it until
then. The deletion itself is the worker's (``app/jobs/deletion.py``).
"""

from __future__ import annotations

import hmac
import json
import secrets
import uuid  # noqa: TC003
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.crypto import blind_index, encrypt
from app.core.errors import AppError, NotFoundError
from app.core.schemas import RequestModel
from app.modules.auth.sessions import require_step_up
from app.modules.companies.models import Company
from app.modules.deletion.models import DeletionRequest
from app.modules.email.models import EmailOutbox
from app.modules.email.outbox import PAYLOAD_CONTEXT
from app.modules.email.templates import check
from app.modules.exports.models import DataExport
from app.modules.exports.router import enqueue as enqueue_export
from app.modules.identity.models import Membership, User
from app.modules.notifications.models import Notification
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from app.db.session import TenantSession

router = APIRouter(prefix="/companies/me", tags=["account-lifecycle"])
Deleter = Annotated[Access, Depends(require("company.delete"))]

PAGE = "/company/delete-account"
NOTICE_DAYS = 7
CODE_MINUTES = 15
RESEND_SECONDS = 60
MAX_ATTEMPTS = 5

DeletionStatus = Literal["awaiting_code", "scheduled"]


class DeletionIn(RequestModel):
    export_requested: bool = False


class ConfirmIn(RequestModel):
    code: str = Field(min_length=6, max_length=12)


class DeletionOut(BaseModel):
    id: uuid.UUID
    status: DeletionStatus
    requested_by_name: str | None
    requested_by_me: bool
    created_at: datetime
    code_expires_at: datetime | None
    confirmed_at: datetime | None
    scheduled_for: datetime | None
    export_requested: bool
    export_id: uuid.UUID | None


def _code_hash(row: DeletionRequest, code: str) -> str:
    return blind_index(code, purpose="deletion.code", scope=str(row.id))


async def _open(db: TenantSession, *, lock: bool = False) -> DeletionRequest | None:
    statement = select(DeletionRequest).where(
        DeletionRequest.withdrawn_at.is_(None), DeletionRequest.completed_at.is_(None)
    )
    if lock:
        statement = statement.with_for_update()
    return (await db.execute(statement)).scalar_one_or_none()


async def _out(db: TenantSession, row: DeletionRequest, me: uuid.UUID) -> DeletionOut:
    name = None
    if row.requested_by is not None:
        person = await db.get(User, row.requested_by)
        if person is not None:
            name = f"{person.first_name} {person.last_name}".strip()
    return DeletionOut(
        id=row.id,
        status="scheduled" if row.confirmed_at is not None else "awaiting_code",
        requested_by_name=name,
        requested_by_me=row.requested_by == me,
        created_at=row.created_at,
        code_expires_at=row.code_expires_at if row.confirmed_at is None else None,
        confirmed_at=row.confirmed_at,
        scheduled_for=row.scheduled_for,
        export_requested=row.export_requested,
        export_id=row.export_id,
    )


def _email(db: TenantSession, to: str, template: str, data: dict[str, str]) -> None:
    check(template, data)
    db.add(
        EmailOutbox(
            to_address=to,
            template=template,
            payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
        )
    )


async def _other_admins(db: TenantSession, company_id: uuid.UUID, me: uuid.UUID) -> list[User]:
    return list(
        (
            await db.execute(
                select(User)
                .join(Membership, Membership.user_id == User.id)
                .where(
                    Membership.company_id == company_id,
                    Membership.role == "company_admin",
                    Membership.status == "active",
                    User.is_active.is_(True),
                    User.id != me,
                )
                .order_by(User.id)
            )
        )
        .scalars()
        .all()
    )


def _send_code(db: TenantSession, row: DeletionRequest, user: User, now: datetime) -> None:
    code = f"{secrets.randbelow(10**6):06d}"
    row.code_hash = _code_hash(row, code)
    row.code_expires_at = now + timedelta(minutes=CODE_MINUTES)
    row.code_attempts = 0
    # Sent whatever the e-mail preference: the person asked for it, and it is the only way in.
    _email(
        db,
        user.email,
        "deletion_code",
        {"first_name": user.first_name, "code": f"{code[:3]} {code[3:]}", "minutes": "15"},
    )


@router.get("/deletion-request", response_model=DeletionOut | None)
async def deletion_request(access: Deleter) -> DeletionOut | None:
    row = await _open(access.db)
    return None if row is None else await _out(access.db, row, access.caller.user_id)


@router.post("/deletion-request", status_code=202, response_model=DeletionOut)
async def request_deletion(body: DeletionIn, request: Request, access: Deleter) -> DeletionOut:
    """Starts a request and e-mails its code, or sends a new code for the person's own request."""
    db, me, now = access.db, access.caller.user_id, datetime.now(UTC)
    row = await _open(db, lock=True)
    if row is not None and row.confirmed_at is not None:
        raise AppError(
            "DELETION_SCHEDULED",
            "The deletion is already scheduled. Withdraw it first to start again.",
            status_code=409,
        )
    if row is not None and row.requested_by != me:
        raise AppError(
            "DELETION_IN_PROGRESS",
            "Another Company Admin has started a deletion request. Withdraw it to start your own.",
            status_code=409,
        )
    if row is not None and row.code_expires_at is not None:
        sent_at = row.code_expires_at - timedelta(minutes=CODE_MINUTES)
        if now < sent_at + timedelta(seconds=RESEND_SECONDS):
            raise AppError(
                "CODE_RECENTLY_SENT",
                "We have just sent a code. Wait a minute before asking for another.",
                status_code=429,
            )
    export: DataExport | None = None
    if body.export_requested and (row is None or row.export_id is None):
        # The export is the same as the data export page's, so it needs the same step-up.
        require_step_up(access.caller.session)
        queued = (
            await db.execute(
                select(func.count()).select_from(DataExport).where(DataExport.status == "queued")
            )
        ).scalar_one()
        if not queued:
            export = DataExport(company_id=access.company_id, requested_by=me)
            db.add(export)
    if row is None:
        row = DeletionRequest(company_id=access.company_id, requested_by=me)
        db.add(row)
        await db.flush()
        await access.audit(
            "company.deletion_requested", entity_type="deletion_request", entity_id=row.id
        )
    if export is not None:
        await db.flush()
        row.export_id = export.id
        await access.audit("export.requested", entity_type="data_export", entity_id=export.id)
    row.export_requested = row.export_requested or body.export_requested
    _send_code(db, row, access.caller.user, now)
    await db.commit()
    if export is not None:
        await enqueue_export(request, export)
    return await _out(db, row, me)


@router.post("/deletion-request/confirm", response_model=DeletionOut)
async def confirm_deletion(body: ConfirmIn, request: Request, access: Deleter) -> DeletionOut:
    db, me, now = access.db, access.caller.user_id, datetime.now(UTC)
    row = await _open(db, lock=True)
    if row is None or row.requested_by != me:
        raise NotFoundError
    if row.confirmed_at is not None:
        return await _out(db, row, me)
    if row.code_hash is None or row.code_expires_at is None or now >= row.code_expires_at:
        raise AppError("CODE_EXPIRED", "This code has expired. Ask for a new one.", status_code=400)
    code = "".join(body.code.split())
    if not hmac.compare_digest(row.code_hash, _code_hash(row, code)):
        row.code_attempts += 1
        if row.code_attempts >= MAX_ATTEMPTS:
            row.code_hash, row.code_expires_at = None, None
        await db.commit()
        if row.code_hash is None:
            raise AppError(
                "CODE_EXPIRED", "Too many wrong codes. Ask for a new one.", status_code=400
            )
        raise AppError(
            "INVALID_CODE", "That code is not right. Check it and try again.", status_code=400
        )

    row.code_hash, row.code_expires_at = None, None
    row.confirmed_at = now
    row.scheduled_for = now + timedelta(days=NOTICE_DAYS)
    await access.audit(
        "company.deletion_scheduled",
        entity_type="deletion_request",
        entity_id=row.id,
        after={"scheduled_for": row.scheduled_for.isoformat()},
    )
    company = await db.get(Company, access.company_id)
    settings = request.app.state.settings
    when = f"{row.scheduled_for:%-d %B %Y}"
    me_user = access.caller.user
    requester = f"{me_user.first_name} {me_user.last_name}".strip()
    company_name = company.name if company is not None else ""
    for admin in await _other_admins(db, access.company_id, me):
        db.add(
            Notification(
                company_id=access.company_id,
                user_id=admin.id,
                kind="account.deletion_scheduled",
                title="The company account is due to be deleted",
                body=f"{requester} asked to delete the account on {when}. You can withdraw it.",
                link=PAGE,
            )
        )
        _email(
            db,
            admin.email,
            "deletion_scheduled",
            {
                "first_name": admin.first_name,
                "requester": requester,
                "company_name": company_name,
                "deletion_date": when,
                "link": f"{settings.web_origin}{PAGE}",
            },
        )
    _email(
        db,
        settings.support_email or f"support@{settings.domain}",
        "deletion_scheduled_support",
        {"company_name": company_name, "company_id": str(access.company_id), "deletion_date": when},
    )
    await db.commit()
    return await _out(db, row, me)


@router.delete("/deletion-request", status_code=204)
async def withdraw_deletion(access: Deleter) -> Response:
    db, me, now = access.db, access.caller.user_id, datetime.now(UTC)
    row = await _open(db, lock=True)
    if row is None:
        raise NotFoundError
    was_scheduled = row.confirmed_at is not None
    row.withdrawn_at, row.withdrawn_by = now, me
    row.code_hash, row.code_expires_at = None, None
    await access.audit(
        "company.deletion_withdrawn", entity_type="deletion_request", entity_id=row.id
    )
    if was_scheduled:
        company = await db.get(Company, access.company_id)
        actor = f"{access.caller.user.first_name} {access.caller.user.last_name}".strip()
        for admin in await _other_admins(db, access.company_id, me):
            db.add(
                Notification(
                    company_id=access.company_id,
                    user_id=admin.id,
                    kind="account.deletion_withdrawn",
                    title="The account deletion was withdrawn",
                    body=f"{actor} withdrew the request. Nothing will be deleted.",
                    link=PAGE,
                )
            )
            _email(
                db,
                admin.email,
                "deletion_withdrawn",
                {
                    "first_name": admin.first_name,
                    "actor": actor,
                    "company_name": company.name if company is not None else "",
                },
            )
    await db.commit()
    return Response(status_code=204)
