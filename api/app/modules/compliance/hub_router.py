"""Company-wide compliance overview derived from the current source records (T7.5)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.db.rtw import employee_rtw_status
from app.modules.companies.compliance_documents import _today
from app.modules.companies.models import ComplianceDocument, KeyPerson, Location
from app.modules.companies.reference import COMPLIANCE_DOCUMENT_TYPES
from app.modules.companies.router import _company
from app.modules.compliance.hub_schemas import (
    AttentionItem,
    ComplianceOverview,
    Coverage,
    CoverageCount,
    ExpiringItem,
    ReadinessCheck,
)
from app.modules.compliance.models import ChangeOfCircumstances, OrgChange
from app.modules.compliance.reminder_service import targets
from app.modules.employees.models import Employee
from app.modules.files.models import File
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["compliance-hub"])
Reads = Annotated[Access, Depends(require("compliance.overview.read"))]

# The Expired employee filter also includes failed checks, matching the directory's existing rules.
STATUSES = (
    ("verified", "Verified", "Verified"),
    ("expiring", "Expiring", "Expiring"),
    ("expired", "Expired", "Expired"),
    ("failed", "Failed", "Expired"),
    ("pending", "Pending", "Pending"),
    ("evidence_missing", "Evidence missing", "EvidenceMissing"),
    ("not_recorded", "Not recorded", "NotRecorded"),
)
RTW_ACTIONS = {
    "expired": (0, "Right to Work expired", "Record a follow-up check"),
    "failed": (0, "Right to Work check failed", "Review the check outcome"),
    "evidence_missing": (2, "Right to Work evidence missing", "Add clean check evidence"),
    "pending": (2, "Right to Work check pending", "Complete the check"),
    "not_recorded": (2, "No Right to Work check on file", "Record a check"),
    "expiring": (3, "Right to Work expiring", "Arrange the follow-up check"),
}


def _expiry(
    ident: str, name: str, kind: str, label: str, expiry: date, href: str, today: date
) -> ExpiringItem:
    days = (expiry - today).days
    return ExpiringItem(
        id=ident,
        employee_name=name,
        document_type=kind,
        document_label=label,
        expires_on=expiry,
        days_left=days,
        bucket="overdue"
        if days < 0
        else "next_30"
        if days <= 30
        else "31_60"
        if days <= 60
        else "61_90",
        href=href,
    )


@router.get("/compliance/overview", response_model=ComplianceOverview)
async def overview(access: Reads) -> ComplianceOverview:
    company = await _company(access)
    today = await _today(access)
    people = (
        await access.db.execute(
            select(
                Employee.id,
                Employee.first_name,
                Employee.last_name,
                employee_rtw_status.c.status,
                employee_rtw_status.c.current_check_id,
                employee_rtw_status.c.follow_up_due_on,
            )
            .join(employee_rtw_status, employee_rtw_status.c.employee_id == Employee.id)
            .where(
                Employee.status != "archived",
                employee_rtw_status.c.company_id == access.company_id,
            )
        )
    ).all()
    names = {ident: f"{first} {last}" for ident, first, last, *_ in people}
    counts = dict.fromkeys((status for status, _, _ in STATUSES), 0)
    attention = []
    expiring = []
    for ident, first, last, status, _, due in people:
        counts[status] += 1
        if status in RTW_ACTIONS:
            priority, title, action = RTW_ACTIONS[status]
            attention.append(
                AttentionItem(
                    id=f"rtw-{ident}",
                    priority=priority,
                    title=title,
                    detail=f"{first} {last}",
                    action=action,
                    href=f"/employees/{ident}?tab=rtw",
                    due_on=due,
                )
            )
    for target in await targets(access.db):
        if (
            not target.active
            or not target.expires_on
            or target.expires_on > today + timedelta(days=90)
        ):
            continue
        href = f"/employees/{target.employee_id}?tab={'rtw' if target.kind == 'rtw' else 'sponsor'}"
        expiry = _expiry(
            str(target.id),
            names[target.employee_id],
            target.doc_type,
            target.label,
            target.expires_on,
            href,
            today,
        )
        expiring.append(expiry)
        if target.kind != "rtw":
            attention.append(
                AttentionItem(
                    id=f"document-{target.id}",
                    priority=1 if expiry.days_left < 0 else 4,
                    title=f"{target.label} {'expired' if expiry.days_left < 0 else 'expiring'}",
                    detail=expiry.employee_name,
                    action="Review the document and plan renewal",
                    href=href,
                    due_on=expiry.expires_on,
                )
            )
    company_docs = (
        await access.db.execute(
            select(ComplianceDocument, File.scan_status)
            .join(File, File.id == ComplianceDocument.file_id)
            .where(ComplianceDocument.archived_at.is_(None))
        )
    ).all()
    for doc, _ in company_docs:
        if doc.expires_on and doc.expires_on <= today + timedelta(days=90):
            expiry = _expiry(
                str(doc.id),
                company.name,
                "company",
                COMPLIANCE_DOCUMENT_TYPES[doc.doc_type],
                doc.expires_on,
                "/company/compliance-documents",
                today,
            )
            expiring.append(expiry)
            attention.append(
                AttentionItem(
                    id=f"company-document-{doc.id}",
                    priority=1 if expiry.days_left < 0 else 4,
                    title=expiry.document_label
                    + (" expired" if expiry.days_left < 0 else " expiring"),
                    detail=company.name,
                    action="Update the company document",
                    href=expiry.href,
                    due_on=expiry.expires_on,
                )
            )
    # Worker obligations remain relevant after an employee leaves or is archived.
    changes = list((await access.db.execute(select(ChangeOfCircumstances))).scalars())
    org_changes = list(
        (
            await access.db.execute(select(OrgChange).where(OrgChange.archived_at.is_(None)))
        ).scalars()
    )
    all_changes: list[ChangeOfCircumstances | OrgChange] = [*changes, *org_changes]
    for change in all_changes:
        if change.reported_at:
            continue
        overdue = change.deadline_date is not None and change.deadline_date < today
        prompt = change.deadline_date is None
        attention.append(
            AttentionItem(
                id=f"change-{change.id}",
                priority=0 if overdue else 1 if prompt else 3,
                title="Change past reporting deadline"
                if overdue
                else "Replacement needs prompt reporting"
                if prompt
                else "Change still to report",
                detail="Worker change"
                if isinstance(change, ChangeOfCircumstances)
                else "Organisation change",
                action="Open the change log and record the report",
                href="/sponsor-compliance/change-of-circumstances?"
                + (
                    "kind=worker"
                    if isinstance(change, ChangeOfCircumstances)
                    else "kind=organisation"
                ),
                due_on=change.deadline_date,
            )
        )
    roles = set(
        (
            await access.db.execute(select(KeyPerson.role).where(KeyPerson.archived_at.is_(None)))
        ).scalars()
    )
    address = (
        await access.db.execute(
            select(Location.id).where(Location.is_default.is_(True), Location.archived_at.is_(None))
        )
    ).first()
    profile_complete = (
        all(
            (
                company.name,
                company.type_of_organisation,
                company.sector,
                company.contact_email,
                company.contact_phone,
                address,
            )
        )
        and (not company.changed_name_last_5_years or bool(company.previous_company_name))
        and (
            not company.penalty_illegal_working_last_3_years
            or bool(company.penalty_illegal_working_status)
        )
    )
    zone = ZoneInfo(company.timezone)
    on_time = all(
        c.reported_at is not None
        and (c.deadline_date is None or c.reported_at.astimezone(zone).date() <= c.deadline_date)
        for c in all_changes
    )

    def check(
        ident: str, title: str, complete: bool, detail: str, href: str, *, applicable: bool = True
    ) -> ReadinessCheck:
        return ReadinessCheck(
            id=ident,
            title=title,
            status="not_applicable" if not applicable else "complete" if complete else "incomplete",
            detail=detail,
            href=href,
        )

    readiness = [
        check(
            "profile",
            "Company profile complete",
            bool(profile_complete),
            "Legal structure, sector, contact details, main address "
            "and applicable sponsor history.",
            "/company",
        ),
        check(
            "key_personnel",
            "Key personnel recorded",
            {"authorising_officer", "key_contact", "level1_user"} <= roles,
            "Authorising Officer, Key Contact and Level 1 User.",
            "/company/key-personnel",
        ),
        check(
            "documents",
            "Company compliance documents uploaded",
            any(scan == "clean" for _, scan in company_docs),
            "At least one current, clean upload for the documents applicable to your company.",
            "/company/compliance-documents",
        ),
        check(
            "rtw",
            "Every current employee has an RTW check",
            all(row[4] is not None for row in people),
            "A recorded check for each unarchived employee; "
            "validity and evidence are shown in coverage.",
            "/employees?rtw=NotRecorded",
            applicable=bool(people),
        ),
        check(
            "changes",
            "Every reportable change reported on time",
            on_time,
            "All recorded changes reported by their deadline; replacements without a fixed "
            "deadline must be reported. No changes recorded is not applicable.",
            "/sponsor-compliance/change-of-circumstances",
            applicable=bool(all_changes),
        ),
    ]
    return ComplianceOverview(
        today=today,
        attention=sorted(
            attention, key=lambda item: (item.priority, item.due_on or today, item.detail, item.id)
        ),
        coverage=Coverage(
            valid=counts["verified"] + counts["expiring"],
            total=len(people),
            counts=[
                CoverageCount(
                    status=status,
                    label=label,
                    count=counts[status],
                    href=f"/employees?rtw={filter_}",
                )
                for status, label, filter_ in STATUSES
            ],
        ),
        readiness=readiness,
        expiring=sorted(expiring, key=lambda item: (item.expires_on, item.employee_name, item.id)),
    )
