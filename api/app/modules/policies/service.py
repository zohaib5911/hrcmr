"""Tenant policy audiences, version serialization and atomic employee notifications."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_, select

from app.core.crypto import encrypt
from app.core.errors import AppError, NotFoundError
from app.core.rbac_matrix import scope_for
from app.db.ids import uuid7
from app.modules.audit.service import record
from app.modules.companies.models import Company, Department, Location
from app.modules.email.models import EmailOutbox
from app.modules.email.outbox import PAYLOAD_CONTEXT
from app.modules.email.templates import check
from app.modules.employees.models import Employee, EmployeeAssignment
from app.modules.files.models import File
from app.modules.identity.models import Membership, User
from app.modules.notifications.models import Notification
from app.modules.notifications.preferences import email_modes
from app.modules.policies.models import PolicyAcceptance, PolicyDocument
from app.modules.policies.schemas import PolicyDraft, PolicyOut, PolicyRecipient
from app.modules.sponsor_documents.models import SponsorDocument

if TYPE_CHECKING:
    import uuid

    from sqlalchemy import Select

    from app.db.session import TenantSession
    from app.modules.audit.service import AuditContext
    from app.modules.policies.reference import (
        AcceptanceStatus,
        AudienceType,
        ConfirmationMode,
        PolicyCategory,
        PolicyStatus,
    )

MAX_RECIPIENTS = 5000
CATCH_UP_BATCH = 1000  # the daily job's assignments per step for one policy


def now() -> datetime:
    return datetime.now(UTC)


async def company_day(db: TenantSession) -> date:
    zone = (
        await db.execute(select(Company.timezone).where(Company.id == db.company_id))
    ).scalar_one()
    return now().astimezone(ZoneInfo(zone)).date()


async def policy(db: TenantSession, ident: uuid.UUID, *, lock: bool = False) -> PolicyDocument:
    row = (
        await db.execute(select(PolicyDocument).where(PolicyDocument.id == ident))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    if lock:
        # Every version mutation, acceptance and scheduled assignment locks the root first.
        await db.execute(
            select(PolicyDocument.id).where(PolicyDocument.id == row.group_id).with_for_update()
        )
        row = (
            await db.execute(
                select(PolicyDocument)
                .where(PolicyDocument.id == ident)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
    return row


def draft_only(row: PolicyDocument) -> None:
    if row.status != "draft":
        raise AppError(
            "POLICY_FROZEN", "Create a new version to change a sent policy.", status_code=409
        )


async def validate_audience(db: TenantSession, body: PolicyDraft) -> None:
    ids = body.audience_ids
    if not ids:
        return
    if body.audience_type == "named":
        query = select(Employee.id).where(
            Employee.id.in_(ids), Employee.status.in_(("active", "on_leave"))
        )
    elif body.audience_type == "departments":
        query = select(Department.id).where(
            Department.id.in_(ids), Department.archived_at.is_(None)
        )
    else:
        query = select(Location.id).where(Location.id.in_(ids), Location.archived_at.is_(None))
    found = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    if found != len(ids):
        raise AppError(
            "POLICY_AUDIENCE_CHANGED",
            "Choose current employees, departments or locations from this company.",
            status_code=422,
            field="audience_ids",
        )


@dataclass(frozen=True)
class Candidate:
    id: uuid.UUID
    first_name: str
    last_name: str
    number: str

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


def _audience_query(
    row: PolicyDocument, today: date, only: list[uuid.UUID] | None
) -> Select[uuid.UUID, str, str, str]:
    """Everyone the policy's audience names today (no limit, no order)."""
    query = select(
        Employee.id, Employee.first_name, Employee.last_name, Employee.employee_number
    ).where(Employee.status.in_(("active", "on_leave")))
    if row.audience_type == "named":
        query = query.where(Employee.id.in_(row.audience_ids))
    if row.audience_type in {"departments", "locations"}:
        scope = (
            EmployeeAssignment.department_id
            if row.audience_type == "departments"
            else EmployeeAssignment.location_id
        )
        query = query.where(
            select(EmployeeAssignment.id)
            .where(
                EmployeeAssignment.employee_id == Employee.id,
                scope.in_(row.audience_ids),
                EmployeeAssignment.effective_from <= today,
                or_(EmployeeAssignment.ended_at.is_(None), EmployeeAssignment.ended_at > today),
            )
            .exists()
        )
    if row.audience_type == "visa_holders":
        query = query.where(
            select(SponsorDocument.id)
            .where(
                SponsorDocument.employee_id == Employee.id,
                SponsorDocument.doc_type == "visa",
                SponsorDocument.withdrawn_at.is_(None),
                SponsorDocument.superseded_by.is_(None),
            )
            .exists()
        )
    if only is not None:
        query = query.where(Employee.id.in_(only))
    return query


async def audience(
    db: TenantSession,
    row: PolicyDocument,
    today: date,
    *,
    lock: bool = False,
    only: list[uuid.UUID] | None = None,
) -> list[Candidate]:
    """The audience for an interactive send: refused above MAX_RECIPIENTS people."""
    query = _audience_query(row, today, only).order_by(Employee.id).limit(MAX_RECIPIENTS + 1)
    if lock:
        query = query.with_for_update(of=Employee)
    rows = (await db.execute(query)).all()
    if len(rows) > MAX_RECIPIENTS:
        raise AppError(
            "POLICY_AUDIENCE_TOO_LARGE",
            "Choose an audience of up to 5,000 people.",
            status_code=422,
        )
    return [Candidate(ident, first, last, number) for ident, first, last, number in rows]


def preview_token(row: PolicyDocument, people: list[Candidate], today: date) -> str:
    data = {
        "policy_id": str(row.id),
        "company_id": str(row.company_id),
        "today": today.isoformat(),
        "file_id": str(row.file_id),
        "title": row.title,
        "category": row.category,
        "mode": row.confirmation_mode,
        "days": row.accept_within_days,
        "auto": row.auto_send_new_starters,
        "audience": row.audience_type,
        "audience_ids": sorted(map(str, row.audience_ids)),
        "people": sorted(str(p.id) for p in people),
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def recipient_status(row: PolicyAcceptance, today: date) -> AcceptanceStatus:
    if row.accepted_at is None:
        return "overdue" if row.status == "overdue" or row.due_on < today else "pending"
    return cast("AcceptanceStatus", row.status)


async def recipients(db: TenantSession, row: PolicyDocument, today: date) -> list[PolicyRecipient]:
    if row.status == "draft":
        return [
            PolicyRecipient(
                id=None,
                employee_id=p.id,
                employee_name=p.name,
                employee_number=p.number,
                due_on=today + timedelta(days=row.accept_within_days),
                status="pending",
                accepted_at=None,
            )
            for p in await audience(db, row, today)
        ]
    rows = (
        await db.execute(
            select(
                PolicyAcceptance, Employee.first_name, Employee.last_name, Employee.employee_number
            )
            .join(Employee, Employee.id == PolicyAcceptance.employee_id)
            .where(PolicyAcceptance.policy_document_id == row.id)
            .order_by(Employee.employee_number, Employee.id)
        )
    ).all()
    return [
        PolicyRecipient(
            id=receipt.id,
            employee_id=receipt.employee_id,
            employee_name=f"{first} {last}".strip(),
            employee_number=number,
            due_on=receipt.due_on,
            status=recipient_status(receipt, today),
            accepted_at=receipt.accepted_at,
        )
        for receipt, first, last, number in rows
    ]


async def out(db: TenantSession, row: PolicyDocument, today: date) -> PolicyOut:
    file = await db.get(File, row.file_id) if row.file_id else None
    counts = (
        await db.execute(
            select(
                func.count(PolicyAcceptance.id),
                func.sum(case((PolicyAcceptance.accepted_at.is_not(None), 1), else_=0)),
                func.sum(
                    case(
                        (
                            PolicyAcceptance.accepted_at.is_(None)
                            & (
                                (PolicyAcceptance.status == "overdue")
                                | (PolicyAcceptance.due_on < today)
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
            ).where(PolicyAcceptance.policy_document_id == row.id)
        )
    ).one()
    return PolicyOut(
        id=row.id,
        group_id=row.group_id,
        previous_version_id=row.previous_version_id,
        version=row.version,
        title=row.title,
        category=cast("PolicyCategory", row.category),
        confirmation_mode=cast("ConfirmationMode", row.confirmation_mode),
        audience_type=cast("AudienceType", row.audience_type),
        audience_ids=row.audience_ids,
        accept_within_days=row.accept_within_days,
        auto_send_new_starters=row.auto_send_new_starters,
        status=cast("PolicyStatus", row.status),
        sent_at=row.sent_at,
        archived_at=row.archived_at,
        file_id=row.file_id,
        file_name=file.original_name if file else None,
        file_mime=file.mime if file else None,
        scan_status=file.scan_status if file else None,
        recipients=counts[0],
        completed=counts[1] or 0,
        overdue=counts[2] or 0,
    )


def metadata(row: PolicyDocument) -> dict[str, Any]:
    return {
        "title": row.title,
        "category": row.category,
        "confirmation_mode": row.confirmation_mode,
        "audience_type": row.audience_type,
        "audience_ids": list(map(str, row.audience_ids)),
        "accept_within_days": row.accept_within_days,
        "auto_send_new_starters": row.auto_send_new_starters,
        "version": row.version,
    }


NOTICE_TITLES = {
    "policy.assigned": "Please read a policy",
    "policy.reminder": "Policy reminder",
    "policy.overdue": "Policy overdue",
}


async def notify(
    db: TenantSession,
    row: PolicyDocument,
    assignments: list[PolicyAcceptance],
    web_origin: str,
    *,
    kind: str = "policy.assigned",
) -> int:
    by_employee = {a.employee_id: a for a in assignments}
    if not by_employee:
        return 0
    targets = (
        await db.execute(
            select(User.id, User.email, User.first_name, Membership.employee_id, Membership.role)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.employee_id.in_(by_employee),
                Membership.status == "active",
                User.is_active.is_(True),
                User.email_verified_at.is_not(None),
            )
        )
    ).all()
    count = 0
    # Only people on immediate e-mail get this message now; daily digest and off people do not.
    modes = await email_modes(db, [target[0] for target in targets])
    for user_id, email, first, employee_id, role in targets:
        if employee_id is None or scope_for(role, "policy.acceptance.read") is None:
            continue
        link = f"/my-documents?policy={row.id}"
        data = {
            "first_name": " ".join(first.split()) or "there",
            "policy_title": row.title,
            "link": web_origin + link,
        }
        check("policy_request", data)
        db.add(
            Notification(
                company_id=db.company_id,
                user_id=user_id,
                kind=kind,
                title=NOTICE_TITLES[kind],
                body=f"{row.title} · Due {by_employee[employee_id].due_on}",
                link=link,
            )
        )
        if modes.get(user_id, "immediate") == "immediate":
            db.add(
                EmailOutbox(
                    to_address=email,
                    template="policy_request",
                    payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
                )
            )
        count += 1
    return count


async def send(
    db: TenantSession,
    row: PolicyDocument,
    token: str,
    actor: uuid.UUID,
    audit: AuditContext,
    web_origin: str,
) -> None:
    draft_only(row)
    today = await company_day(db)
    people = await audience(db, row, today, lock=True)
    if token != preview_token(row, people, today):
        raise AppError(
            "POLICY_PREVIEW_CHANGED",
            "The policy or recipients changed. Review the audience again.",
            status_code=409,
        )
    if not people:
        raise AppError(
            "POLICY_NO_RECIPIENTS",
            "Choose an audience with at least one current employee.",
            status_code=422,
        )
    file = await db.get(File, row.file_id) if row.file_id else None
    if file is None or file.scan_status != "clean":
        raise AppError(
            "POLICY_FILE_REQUIRED",
            "Upload a file that passes its scan before sending.",
            status_code=422,
        )
    moment = now()
    previous = (
        (
            await db.execute(
                select(PolicyDocument).where(
                    PolicyDocument.group_id == row.group_id, PolicyDocument.status == "sent"
                )
            )
        )
        .scalars()
        .all()
    )
    for old in previous:
        old.status, old.archived_at = "archived", moment
    await db.flush()
    row.status, row.sent_at, row.sent_by = "sent", moment, actor
    await db.flush()
    assignments = [
        PolicyAcceptance(
            company_id=db.company_id,
            policy_document_id=row.id,
            employee_id=p.id,
            due_on=today + timedelta(days=row.accept_within_days),
        )
        for p in people
    ]
    db.add_all(assignments)
    await db.flush()
    await notify(db, row, assignments, web_origin)
    await record(
        db,
        audit,
        "policy.sent",
        entity_type="policy_document",
        entity_id=row.id,
        after={"version": row.version, "recipients": len(assignments)},
    )


async def new_version(
    db: TenantSession, row: PolicyDocument, audit: AuditContext
) -> PolicyDocument:
    if row.status == "draft":
        raise AppError(
            "POLICY_IS_DRAFT", "Finish the draft before creating a new version.", status_code=409
        )
    existing = (
        await db.execute(
            select(PolicyDocument).where(
                PolicyDocument.group_id == row.group_id, PolicyDocument.status == "draft"
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    latest = (
        await db.execute(
            select(func.max(PolicyDocument.version)).where(PolicyDocument.group_id == row.group_id)
        )
    ).scalar_one()
    if latest != row.version:
        raise AppError(
            "POLICY_VERSION_CHANGED",
            "Open the latest policy version to create its next version.",
            status_code=409,
        )
    new = PolicyDocument(
        id=uuid7(),
        company_id=db.company_id,
        group_id=row.group_id,
        previous_version_id=row.id,
        version=row.version + 1,
        title=row.title,
        category=cast("PolicyCategory", row.category),
        confirmation_mode=cast("ConfirmationMode", row.confirmation_mode),
        audience_type=cast("AudienceType", row.audience_type),
        audience_ids=list(row.audience_ids),
        accept_within_days=row.accept_within_days,
        auto_send_new_starters=row.auto_send_new_starters,
    )
    db.add(new)
    await db.flush()
    await record(
        db,
        audit,
        "policy.version_created",
        entity_type="policy_document",
        entity_id=new.id,
        after={"previous_version_id": str(row.id), "version": new.version},
    )
    return new


async def remind(
    db: TenantSession, row: PolicyDocument, audit: AuditContext, web_origin: str
) -> int:
    """Nudge everyone who has not yet accepted or signed this sent version."""
    if row.status != "sent":
        raise AppError(
            "POLICY_NOT_SENT", "Send this version before reminding people.", status_code=409
        )
    outstanding = list(
        (
            await db.execute(
                select(PolicyAcceptance)
                .where(
                    PolicyAcceptance.policy_document_id == row.id,
                    PolicyAcceptance.accepted_at.is_(None),
                )
                .with_for_update()
            )
        ).scalars()
    )
    if not outstanding:
        return 0
    moment = now()
    for receipt in outstanding:
        receipt.last_reminded_at = moment
    await notify(db, row, outstanding, web_origin, kind="policy.reminder")
    await record(
        db,
        audit,
        "policy.reminded",
        entity_type="policy_document",
        entity_id=row.id,
        after={"version": row.version, "recipients": len(outstanding)},
    )
    return len(outstanding)


async def mark_overdue(db: TenantSession, audit: AuditContext, today: date, web_origin: str) -> int:
    """Flip outstanding acceptances past their due day to overdue (once), and tell each employee."""
    rows = (
        await db.execute(
            select(PolicyAcceptance, PolicyDocument)
            .join(PolicyDocument, PolicyDocument.id == PolicyAcceptance.policy_document_id)
            .where(
                PolicyDocument.status == "sent",
                PolicyAcceptance.status == "pending",
                PolicyAcceptance.accepted_at.is_(None),
                PolicyAcceptance.due_on < today,
            )
            .with_for_update(of=PolicyAcceptance, skip_locked=True)
        )
    ).all()
    by_document: dict[uuid.UUID, tuple[PolicyDocument, list[PolicyAcceptance]]] = {}
    for receipt, document in rows:
        receipt.status = "overdue"
        by_document.setdefault(document.id, (document, []))[1].append(receipt)
    for document, receipts in by_document.values():
        await notify(db, document, receipts, web_origin, kind="policy.overdue")
        await record(
            db,
            audit,
            "policy.overdue_marked",
            entity_type="policy_document",
            entity_id=document.id,
            after={"version": document.version, "overdue": len(receipts)},
        )
    return len(rows)


async def assign_new_starters(
    db: TenantSession,
    audit: AuditContext,
    today: date,
    web_origin: str,
    *,
    only: list[uuid.UUID] | None = None,
) -> int:
    """Give each sent policy marked for new starters to the people now in its audience.

    The hire hook passes the new employee's id; the daily job passes nothing and catches up on
    everyone. Existing acceptances are never duplicated, so running this twice is safe.
    """
    sent = (
        (
            await db.execute(
                select(PolicyDocument).where(
                    PolicyDocument.status == "sent",
                    PolicyDocument.auto_send_new_starters.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    created = 0
    for row in sent:
        # Only people without an acceptance yet, a bounded batch at a time (ISS-31): an audience
        # that grew past the interactive send limit still gets its catch-up assignments.
        while True:
            people = (
                await db.execute(
                    _audience_query(row, today, only)
                    .where(
                        ~select(PolicyAcceptance.id)
                        .where(
                            PolicyAcceptance.policy_document_id == row.id,
                            PolicyAcceptance.employee_id == Employee.id,
                        )
                        .exists()
                    )
                    .order_by(Employee.id)
                    .limit(CATCH_UP_BATCH)
                )
            ).all()
            if not people:
                break
            fresh = [
                PolicyAcceptance(
                    company_id=db.company_id,
                    policy_document_id=row.id,
                    employee_id=ident,
                    due_on=today + timedelta(days=row.accept_within_days),
                )
                for ident, *_ in people
            ]
            db.add_all(fresh)
            await db.flush()
            await notify(db, row, fresh, web_origin)
            await record(
                db,
                audit,
                "policy.assigned_new_starters",
                entity_type="policy_document",
                entity_id=row.id,
                after={"version": row.version, "recipients": len(fresh)},
            )
            created += len(fresh)
            if len(people) < CATCH_UP_BATCH:
                break
    return created
