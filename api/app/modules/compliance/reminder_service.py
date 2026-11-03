"""Idempotent reminder scheduling; sources are immutable versions and reminders never send here."""

from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Literal

from sqlalchemy import select

from app.db.ids import uuid7
from app.modules.audit.service import record
from app.modules.compliance.reminder_models import Reminder
from app.modules.employees.models import Employee
from app.modules.rtw.models import RTWCheck
from app.modules.sponsor_documents.models import SponsorDocument
from app.modules.sponsor_documents.reference import DOCUMENT_TYPES

if TYPE_CHECKING:
    from app.db.session import TenantSession
    from app.modules.audit.service import AuditContext

THRESHOLDS = (90, 60, 30)
ARCHIVED_REASON = "Employee archived"
SOURCE_REASON = "Source superseded, withdrawn or no longer expiring"
COVERED_REASON = "Covered by a later-threshold reminder"


@dataclass(frozen=True)
class ReminderTarget:
    id: uuid.UUID
    employee_id: uuid.UUID
    kind: Literal["sponsor", "rtw"]
    doc_type: str
    label: str
    expires_on: date | None
    active: bool

    @property
    def key(self) -> tuple[str, uuid.UUID]:
        return self.kind, self.id


def target_key(row: Reminder) -> tuple[str, uuid.UUID]:
    if row.sponsor_document_id:
        return "sponsor", row.sponsor_document_id
    if row.rtw_check_id:
        return "rtw", row.rtw_check_id
    raise ValueError("Reminder target is missing.")


def effective_status(row: Reminder, today: date, now: datetime) -> str:
    if row.status in {"sent", "cancelled"}:
        return row.status
    if row.snoozed_until and row.snoozed_until > now:
        return "snoozed"
    return "due" if row.due_on <= today else "scheduled"


def template_message(target: ReminderTarget) -> str:
    expiry = target.expires_on.strftime("%d %b %Y") if target.expires_on else "the recorded date"
    return (
        f"Your {target.label.lower()} is due for review on {expiry}. "
        "Please check the record and speak with HR about the evidence or next steps needed."
    )


async def targets(db: TenantSession, employee_id: uuid.UUID | None = None) -> list[ReminderTarget]:
    # Only the metadata needed for scheduling is read; encrypted references/codes are not selected.
    docs = select(
        SponsorDocument.id,
        SponsorDocument.employee_id,
        SponsorDocument.doc_type,
        SponsorDocument.expiry_date,
        SponsorDocument.superseded_by,
        SponsorDocument.withdrawn_at,
        Employee.status,
    ).join(Employee, Employee.id == SponsorDocument.employee_id)
    checks = (
        select(
            RTWCheck.id,
            RTWCheck.subject_id,
            RTWCheck.follow_up_due_on,
            RTWCheck.superseded_at,
            Employee.status,
        )
        .join(Employee, Employee.id == RTWCheck.subject_id)
        .where(RTWCheck.subject_type == "employee")
    )
    if employee_id:
        docs = docs.where(SponsorDocument.employee_id == employee_id)
        checks = checks.where(RTWCheck.subject_id == employee_id)
    labels = dict(DOCUMENT_TYPES)
    found = [
        ReminderTarget(
            i,
            e,
            "sponsor",
            t,
            labels[t],
            expiry,
            superseded is None and withdrawn is None and status != "archived",
        )
        for i, e, t, expiry, superseded, withdrawn, status in (await db.execute(docs)).all()
    ]
    found += [
        ReminderTarget(
            i,
            e,
            "rtw",
            "rtw",
            "Right to Work follow-up",
            expiry,
            superseded is None and status != "archived",
        )
        for i, e, expiry, superseded, status in (await db.execute(checks)).all()
    ]
    return found


async def synchronize_employee(
    db: TenantSession,
    employee_id: uuid.UUID,
    audit: AuditContext,
    *,
    today: date,
    now: datetime | None = None,
) -> int:
    """Lock the employee before source/reminder rows; caller commits with the audit."""
    moment = now or datetime.now(UTC)
    employee = (
        await db.execute(select(Employee).where(Employee.id == employee_id).with_for_update())
    ).scalar_one_or_none()
    if employee is None:
        return 0
    source = {
        target.key: target
        for target in await targets(db, employee_id)
        if target.active and target.expires_on
    }
    rows = list(
        (
            await db.execute(
                select(Reminder)
                .where(Reminder.employee_id == employee_id)
                .order_by(Reminder.id)
                .with_for_update()
            )
        ).scalars()
    )
    existing = {(target_key(row), row.threshold_days): row for row in rows}
    changes = []
    for target in source.values():
        if target.expires_on is None:
            continue
        for threshold in THRESHOLDS:
            if (target.key, threshold) in existing:
                continue
            due = target.expires_on - timedelta(days=threshold)
            row = Reminder(
                id=uuid7(),
                company_id=db.company_id,
                employee_id=employee_id,
                sponsor_document_id=target.id if target.kind == "sponsor" else None,
                rtw_check_id=target.id if target.kind == "rtw" else None,
                threshold_days=threshold,
                expires_on=target.expires_on,
                due_on=due,
                status="due" if due <= today else "scheduled",
            )
            db.add(row)
            rows.append(row)
            changes.append({"id": str(row.id), "status": row.status})
    for row in rows:
        if row.status == "sent":
            continue
        active = target_key(row) in source
        if not active:
            if row.status != "cancelled":
                row.status = "cancelled"
                row.cancel_reason = (
                    ARCHIVED_REASON if employee.status == "archived" else SOURCE_REASON
                )
                row.snoozed_until = None
                changes.append({"id": str(row.id), "status": "cancelled"})
            continue
        if row.status == "cancelled":
            if row.cancel_reason != ARCHIVED_REASON:
                continue
            row.status = "due" if row.due_on <= today else "scheduled"
            row.cancel_reason = None
            row.admin_notified_at = None
            changes.append({"id": str(row.id), "status": row.status})
        status = effective_status(row, today, moment)
        if status != row.status:
            if status == "due" and row.status == "snoozed":
                row.admin_notified_at = None
            row.status = status
            if status != "snoozed":
                row.snoozed_until = None
            changes.append({"id": str(row.id), "status": status})
    if changes:
        changed_ids = {change["id"] for change in changes}
        for row in rows:
            if str(row.id) in changed_ids:
                row.updated_by = audit.actor_user_id
        await db.flush()
        await record(
            db,
            audit,
            "employee.reminders_reconciled",
            entity_type="employee",
            entity_id=employee_id,
            after={"changes": changes},
        )
    return len(changes)
