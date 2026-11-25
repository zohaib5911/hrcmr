"""Daily privacy retention (T21.5). Owner-only, tenant-scoped history deletion.

No end date means no inferred expiry. Active employees are never purged. Metadata
removal commits first; the retryable orphan sweep removes unreferenced objects afterwards.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import AiInteraction
from app.db.base import Base
from app.db.purge import mark_purge
from app.modules.audit.service import AuditContext, record
from app.modules.employees.models import Employee, EmployeeDocument
from app.modules.exports.models import DataExport
from app.modules.files.models import File
from app.modules.identity.models import Session
from app.modules.rtw.models import RTWCheck
from app.modules.sponsor_documents.models import SponsorDocument

if TYPE_CHECKING:
    import uuid

    from app.integrations.storage import Storage


def anniversary(day: date, years: int) -> date:
    """Leap-day anniversaries fall on February 28 in a non-leap year."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


async def _remove_file(db: AsyncSession, storage: Storage | None, ident: uuid.UUID) -> int:
    # Every real FK counts, including another evidence purpose or another employee.
    # Lock the file against concurrent FK insertion before checking references.
    row = await db.get(File, ident, with_for_update=True)
    if row is None:
        return 0
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            if fk.column.table.name == "files" and fk.column.name == "id":
                found = await db.scalar(select(fk.parent).where(fk.parent == ident).limit(1))
                if found is not None:
                    return 0
    if storage is None:
        raise RuntimeError("Retention requires object storage")
    # Keep the object until metadata deletion commits. The daily orphan sweep removes it
    # afterwards; a SQL rollback therefore never resurrects a reference to missing bytes.
    await db.delete(row)
    await db.flush()
    return 1


BATCH = 100  # leavers locked and committed per step


def _candidates(today: date) -> Any:
    """Leavers who may be due (ISS-34): left at least a year ago (the shortest window, and an
    anniversary is never less than 365 days on) and who still hold evidence. The exact rules
    are checked per person below; this only keeps recent leavers out of the locks."""
    rtw = select(RTWCheck.id).where(
        RTWCheck.company_id == Employee.company_id,
        RTWCheck.subject_type == "employee",
        RTWCheck.subject_id == Employee.id,
    )
    rtw_docs = select(EmployeeDocument.id).where(
        EmployeeDocument.company_id == Employee.company_id,
        EmployeeDocument.employee_id == Employee.id,
        EmployeeDocument.category == "rtw_evidence",
    )
    sponsor = select(SponsorDocument.id).where(
        SponsorDocument.company_id == Employee.company_id,
        SponsorDocument.employee_id == Employee.id,
    )
    return select(Employee.id).where(
        Employee.status.in_(("leaver", "archived")),
        Employee.leave_date.is_not(None),
        Employee.leave_date <= today - timedelta(days=365),
        or_(rtw.exists(), rtw_docs.exists(), sponsor.exists()),
    )


async def _evidence(db: AsyncSession, storage: Storage | None, now: datetime) -> int:
    """Purge due evidence a bounded batch of leavers at a time, committing each batch, so an
    interrupted run keeps what it finished and the next run resumes with the rest."""
    removed, after = 0, None
    while True:
        query = _candidates(now.date()).order_by(Employee.id).limit(BATCH)
        if after is not None:
            query = query.where(Employee.id > after)
        ids = list((await db.scalars(query)).all())
        if not ids:
            return removed
        after = ids[-1]
        people = (
            await db.scalars(
                select(Employee)
                .where(Employee.id.in_(ids))
                .order_by(Employee.id)
                .with_for_update(skip_locked=True)
            )
        ).all()
        removed += await _purge_people(db, storage, now, people)
        await db.commit()


async def _purge_people(
    db: AsyncSession, storage: Storage | None, now: datetime, people: Any
) -> int:
    removed = 0
    for person in people:
        if person.leave_date is None:
            continue
        await mark_purge(db, person.company_id)
        files: set[uuid.UUID | None] = set()
        counts = {"rtw_checks": 0, "rtw_documents": 0, "sponsor_documents": 0}
        if anniversary(person.leave_date, 2) <= now.date():
            checks = (
                (RTWCheck.company_id == person.company_id)
                & (RTWCheck.subject_type == "employee")
                & (RTWCheck.subject_id == person.id)
            )
            files.update((await db.scalars(select(RTWCheck.evidence_file_id).where(checks))).all())
            result = await db.execute(delete(RTWCheck).where(checks))
            counts["rtw_checks"] = result.rowcount  # type: ignore[attr-defined]
            removed += counts["rtw_checks"]
            docs = (
                (EmployeeDocument.company_id == person.company_id)
                & (EmployeeDocument.employee_id == person.id)
                & (EmployeeDocument.category == "rtw_evidence")
            )
            files.update((await db.scalars(select(EmployeeDocument.file_id).where(docs))).all())
            result = await db.execute(delete(EmployeeDocument).where(docs))
            counts["rtw_documents"] = result.rowcount  # type: ignore[attr-defined]
            removed += counts["rtw_documents"]
        sponsor = (SponsorDocument.company_id == person.company_id) & (
            SponsorDocument.employee_id == person.id
        )
        visa_end = await db.scalar(
            select(func.max(SponsorDocument.expiry_date)).where(
                sponsor, SponsorDocument.doc_type == "visa"
            )
        )
        end = max(person.leave_date, visa_end) if visa_end else person.leave_date
        if anniversary(end, 1) <= now.date():
            files.update(
                (await db.scalars(select(SponsorDocument.evidence_file_id).where(sponsor))).all()
            )
            result = await db.execute(delete(SponsorDocument).where(sponsor))
            counts["sponsor_documents"] = result.rowcount  # type: ignore[attr-defined]
            removed += counts["sponsor_documents"]
        for ident in files:
            if ident is not None:
                removed += await _remove_file(db, storage, ident)
        if any(counts.values()):
            await record(
                db,
                AuditContext(company_id=person.company_id, actor_user_id=None, actor_type="system"),
                "employee.retention_purged",
                entity_type="employee",
                entity_id=person.id,
                after=counts,
                reason="Retention: RTW evidence employment + 2 years / sponsor records + 1 year",
            )
    return removed


async def retention_purge_daily(ctx: dict[str, Any]) -> int:
    owner = ctx.get("owner_engine")
    if owner is None:
        # An enabled scheduler must not silently report success with no purge credentials.
        raise RuntimeError("Retention requires owner_engine")
    now = ctx.get("now") or datetime.now(UTC)
    async with AsyncSession(owner) as db:
        ai = await db.execute(
            delete(AiInteraction).where(AiInteraction.created_at <= now - timedelta(days=30))
        )
        sessions = await db.execute(
            delete(Session).where(
                or_(
                    Session.expires_at <= now - timedelta(days=90),
                    Session.revoked_at <= now - timedelta(days=90),
                )
            )
        )
        removed = ai.rowcount + sessions.rowcount  # type: ignore[attr-defined]
        removed += await _evidence(db, ctx.get("storage"), now)
        exports = (
            await db.scalars(
                select(DataExport)
                .where(DataExport.expires_at <= now, DataExport.file_id.is_not(None))
                .with_for_update(skip_locked=True)
            )
        ).all()
        for export in exports:
            ident, export.file_id = export.file_id, None
            export.status, export.error_code, export.expires_at = "failed", "EXPIRED", None
            await db.flush()
            if ident is not None:
                removed += await _remove_file(db, ctx.get("storage"), ident)
        await db.commit()
        return int(removed)
