"""Reviewed reminder delivery: scoped records and atomic notification/outbox/audit writes."""

from __future__ import annotations

import json
import uuid  # noqa: TC003
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal, cast
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app.core.config import Settings  # noqa: TC001
from app.core.crypto import encrypt
from app.core.errors import ConflictError, NotFoundError
from app.core.rbac_matrix import scope_for
from app.db.ids import uuid7
from app.modules.companies.models import Company
from app.modules.compliance.reminder_models import Reminder
from app.modules.compliance.reminder_schemas import (
    ReceivedReminder,
    ReminderDocumentType,
    ReminderMessageIn,
    ReminderOut,
    ReminderSlot,
    ReminderStatus,
)
from app.modules.compliance.reminder_service import (
    COVERED_REASON,
    SOURCE_REASON,
    ReminderTarget,
    effective_status,
    synchronize_employee,
    target_key,
    targets,
    template_message,
)
from app.modules.email.models import EmailOutbox
from app.modules.email.outbox import PAYLOAD_CONTEXT
from app.modules.email.templates import check
from app.modules.employees.employment_router import _locked_employee
from app.modules.employees.models import Employee
from app.modules.identity.models import Membership, User
from app.modules.notifications.models import Notification
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["reminders"])
Reads = Annotated[Access, Depends(require("compliance.overview.read"))]
Sends = Annotated[Access, Depends(require("compliance.reminder.send"))]
OwnReads = Annotated[Access, Depends(require("employee.rtw.read"))]


@dataclass
class View:
    now: datetime
    today: date
    zone: ZoneInfo
    sources: dict[tuple[str, uuid.UUID], ReminderTarget]
    people: dict[uuid.UUID, tuple[str, str]]
    senders: dict[uuid.UUID, str]
    recipients: dict[uuid.UUID, User]
    emails: dict[uuid.UUID, str]


async def _view(access: Access, rows: list[Reminder], employee_id: uuid.UUID | None = None) -> View:
    zone = ZoneInfo(
        (
            await access.db.execute(select(Company.timezone).where(Company.id == access.company_id))
        ).scalar_one()
    )
    now = datetime.now(UTC)
    people = select(Employee.id, Employee.first_name, Employee.last_name, Employee.employee_number)
    if employee_id:
        people = people.where(Employee.id == employee_id)
    names = {
        i: (f"{first} {last}", number)
        for i, first, last, number in (await access.db.execute(people)).all()
    }
    sender_ids = {r.sent_by_user_id for r in rows if r.sent_by_user_id}
    senders = (
        {
            i: f"{first} {last}"
            for i, first, last in (
                await access.db.execute(
                    select(User.id, User.first_name, User.last_name).where(User.id.in_(sender_ids))
                )
            ).all()
        }
        if sender_ids
        else {}
    )
    recipient_query = (
        select(Membership.employee_id, User)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.company_id == access.company_id,
            Membership.employee_id.is_not(None),
            Membership.status == "active",
            User.is_active.is_(True),
            User.email_verified_at.is_not(None),
        )
    )
    if employee_id:
        recipient_query = recipient_query.where(Membership.employee_id == employee_id)
    recipients = {
        ident: user
        for ident, user in (await access.db.execute(recipient_query)).all()
        if ident is not None
    }
    email_ids = {r.email_outbox_id for r in rows if r.email_outbox_id}
    emails = (
        dict(
            (
                await access.db.execute(
                    select(EmailOutbox.id, EmailOutbox.status).where(EmailOutbox.id.in_(email_ids))
                )
            ).all()
        )
        if email_ids
        else {}
    )
    return View(
        now,
        now.astimezone(zone).date(),
        zone,
        {target.key: target for target in await targets(access.db, employee_id)},
        names,
        senders,
        recipients,
        emails,
    )


def _out(access: Access, row: Reminder, view: View) -> ReminderOut:
    target = view.sources.get(target_key(row))
    if target is None or row.employee_id not in view.people:
        raise NotFoundError
    status = effective_status(row, view.today, view.now)
    if not target.active and status != "sent":
        status = "cancelled"
    name, number = view.people[row.employee_id]
    recipient = row.employee_id in view.recipients
    return ReminderOut(
        id=row.id,
        employee_id=row.employee_id,
        employee_name=name,
        employee_number=number,
        source_id=target.id,
        kind=target.kind,
        doc_type=cast("ReminderDocumentType", target.doc_type),
        document_label=target.label,
        threshold_days=row.threshold_days,
        expires_on=row.expires_on,
        due_on=row.due_on,
        status=cast("ReminderStatus", status),
        message_draft=row.message_draft or template_message(target),
        sent_at=row.sent_at,
        sent_by_user_id=row.sent_by_user_id,
        sender_name=view.senders.get(row.sent_by_user_id) if row.sent_by_user_id else None,
        snoozed_until=row.snoozed_until,
        cancel_reason=row.cancel_reason or (SOURCE_REASON if status == "cancelled" else None),
        recipient_available=recipient,
        can_send=status in {"due", "snoozed"}
        and recipient
        and target.active
        and scope_for(access.role, "compliance.reminder.send") is not None,
        email_status=cast(
            "Literal['pending', 'sent', 'failed'] | None",
            view.emails.get(row.email_outbox_id) if row.email_outbox_id else None,
        ),
    )


async def _rows(access: Access, employee_id: uuid.UUID | None = None) -> list[Reminder]:
    query = select(Reminder).order_by(Reminder.due_on, Reminder.id)
    if employee_id:
        query = query.where(Reminder.employee_id == employee_id)
    return list((await access.db.execute(query)).scalars())


@router.get("/compliance/reminders", response_model=list[ReminderSlot])
async def reminder_register(access: Reads) -> list[ReminderSlot]:
    rows = await _rows(access)
    view = await _view(access, rows)
    result = []
    for target in view.sources.values():
        if not target.active:
            continue
        name, number = view.people[target.employee_id]
        result.append(
            ReminderSlot(
                employee_id=target.employee_id,
                employee_name=name,
                employee_number=number,
                source_id=target.id,
                kind=target.kind,
                doc_type=cast("ReminderDocumentType", target.doc_type),
                document_label=target.label,
                expires_on=target.expires_on,
                reminders=sorted(
                    (_out(access, row, view) for row in rows if target_key(row) == target.key),
                    key=lambda r: r.threshold_days,
                    reverse=True,
                ),
            )
        )
    return sorted(result, key=lambda r: (r.employee_name.lower(), r.document_label))


@router.get("/compliance/reminders/due", response_model=list[ReminderOut])
async def due_reminders(access: Reads) -> list[ReminderOut]:
    rows = await _rows(access)
    view = await _view(access, rows)
    closest: dict[tuple[str, uuid.UUID], ReminderOut] = {}
    for row in rows:
        out = _out(access, row, view)
        key = target_key(row)
        if out.status in {"due", "snoozed"} and (
            key not in closest or out.threshold_days < closest[key].threshold_days
        ):
            closest[key] = out
    return sorted(
        (row for row in closest.values() if row.status == "due"),
        key=lambda r: (r.expires_on, r.employee_name.lower()),
    )


@router.get("/compliance/reminders/history", response_model=list[ReminderOut])
async def reminder_history(access: Reads) -> list[ReminderOut]:
    rows = [row for row in await _rows(access) if row.status == "sent"]
    view = await _view(access, rows)
    return [
        _out(access, row, view)
        for row in sorted(rows, key=lambda r: r.sent_at or r.created_at, reverse=True)
    ]


async def _locked(access: Access, ident: uuid.UUID) -> tuple[Reminder, View]:
    row = (
        await access.db.execute(select(Reminder).where(Reminder.id == ident))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    await _locked_employee(access, row.employee_id)
    zone = ZoneInfo(
        (
            await access.db.execute(select(Company.timezone).where(Company.id == access.company_id))
        ).scalar_one()
    )
    await synchronize_employee(
        access.db,
        row.employee_id,
        access.audit_context,
        today=datetime.now(UTC).astimezone(zone).date(),
    )
    await access.db.refresh(row, with_for_update=True)
    view = await _view(access, [row], row.employee_id)
    if _out(access, row, view).status in {"sent", "cancelled"}:
        raise ConflictError("This reminder is already sent or no longer current.")
    return row, view


@router.get("/reminders/{reminder_id}", response_model=ReminderOut)
async def reminder(reminder_id: uuid.UUID, access: Reads) -> ReminderOut:
    row = (
        await access.db.execute(select(Reminder).where(Reminder.id == reminder_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return _out(access, row, await _view(access, [row], row.employee_id))


@router.patch("/reminders/{reminder_id}", response_model=ReminderOut)
async def edit_reminder(
    reminder_id: uuid.UUID, body: ReminderMessageIn, access: Sends
) -> ReminderOut:
    row, view = await _locked(access, reminder_id)
    row.message_draft = body.message
    await access.audit(
        "employee.reminder_draft_updated",
        entity_type="employee",
        entity_id=row.employee_id,
        after={"reminder_id": str(row.id)},
    )
    await access.db.commit()
    return _out(access, row, view)


@router.post("/reminders/{reminder_id}/snooze", response_model=ReminderOut)
async def snooze_reminder(reminder_id: uuid.UUID, access: Sends) -> ReminderOut:
    row, view = await _locked(access, reminder_id)
    if _out(access, row, view).status not in {"due", "snoozed"}:
        raise ConflictError("This reminder is not due yet.")
    row.status = "snoozed"
    row.snoozed_until = (view.now.astimezone(view.zone) + timedelta(days=7)).astimezone(UTC)
    await access.audit(
        "employee.reminder_snoozed",
        entity_type="employee",
        entity_id=row.employee_id,
        after={"reminder_id": str(row.id), "until": row.snoozed_until.isoformat()},
    )
    await access.db.commit()
    return _out(access, row, view)


def _queue_email(
    access: Access, settings: Settings, row: Reminder, recipient: User, sender: str
) -> EmailOutbox:
    data = {
        "first_name": " ".join(recipient.first_name.split()),
        "sender_name": " ".join(sender.split()),
        "link": f"{settings.web_origin}/my-documents?reminder={row.id}",
    }
    check("reminder_nudge", data)
    email = EmailOutbox(
        id=uuid7(),
        to_address=recipient.email,
        template="reminder_nudge",
        payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
    )
    access.db.add(email)
    return email


@router.post("/reminders/{reminder_id}/send", response_model=ReminderOut)
async def send_reminder(
    reminder_id: uuid.UUID, body: ReminderMessageIn, request: Request, access: Sends
) -> ReminderOut:
    row, view = await _locked(access, reminder_id)
    out = _out(access, row, view)
    if out.status not in {"due", "snoozed"}:
        raise ConflictError("This reminder is not due yet.")
    recipient = view.recipients.get(row.employee_id)
    if recipient is None:
        raise ConflictError(
            "Link an active, verified user account to this employee before sending a reminder."
        )
    actor = (
        await access.db.execute(select(User).where(User.id == access.caller.user_id))
    ).scalar_one()
    sender = f"{actor.first_name} {actor.last_name}"
    settings: Settings = request.app.state.settings
    email = _queue_email(access, settings, row, recipient, sender)
    await access.db.flush()
    access.db.add(
        Notification(
            company_id=access.company_id,
            user_id=recipient.id,
            kind="compliance.reminder_received",
            title=out.document_label + " reminder",
            body=body.message,
            link=f"/my-documents?reminder={row.id}",
        )
    )
    row.status = "sent"
    row.sent_at = view.now
    row.sent_by_user_id = access.caller.user_id
    row.message_draft = body.message
    row.snoozed_until = None
    row.email_outbox_id = email.id
    # A later-threshold message covers older unsent thresholds; future thresholds stay scheduled.
    for older in (
        await access.db.execute(
            select(Reminder)
            .where(
                Reminder.employee_id == row.employee_id,
                Reminder.id != row.id,
                Reminder.threshold_days > row.threshold_days,
                Reminder.status.in_(("due", "scheduled", "snoozed")),
            )
            .with_for_update()
        )
    ).scalars():
        if target_key(older) == target_key(row):
            older.status = "cancelled"
            older.cancel_reason = COVERED_REASON
            older.snoozed_until = None
    await access.audit(
        "employee.reminder_sent",
        entity_type="employee",
        entity_id=row.employee_id,
        after={
            "reminder_id": str(row.id),
            "threshold_days": row.threshold_days,
            "sent_by": str(access.caller.user_id),
            "email_outbox_id": str(email.id),
        },
    )
    await access.db.commit()
    view.senders[access.caller.user_id] = sender
    view.emails[email.id] = "pending"
    return _out(access, row, view)


@router.get("/me/document-reminders", response_model=list[ReceivedReminder])
async def received_reminders(access: OwnReads) -> list[ReceivedReminder]:
    if access.employee_id is None:
        return []
    rows = [row for row in await _rows(access, access.employee_id) if row.status == "sent"]
    view = await _view(access, rows, access.employee_id)
    result = []
    for row in sorted(rows, key=lambda r: r.sent_at or r.created_at, reverse=True):
        if row.sent_at is None or row.message_draft is None or row.sent_by_user_id is None:
            raise ValueError("Sent reminder is incomplete.")
        result.append(
            ReceivedReminder(
                id=row.id,
                title=view.sources[target_key(row)].label + " reminder",
                message=row.message_draft,
                expires_on=row.expires_on,
                sent_at=row.sent_at,
                sender_name=view.senders.get(row.sent_by_user_id, "HR"),
            )
        )
    return result
