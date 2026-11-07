"""The upload pipeline and the clean-up job (plan.md 4.5).

    stream to a temporary file  ->  size  ->  extension  ->  magic bytes  ->  virus scan
        ->  store in the bucket under a random key  ->  ``files`` row

Every step can refuse, and a refusal is recorded in the audit trail. Nothing is stored, and no row
exists, until every check has passed, and a file is only ever served when its row says ``clean``.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, BinaryIO

from sqlalchemy import select

from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.rbac_matrix import Scope, scope_for
from app.modules.audit.service import record as record_event
from app.modules.files.models import File
from app.modules.files.validation import (
    ALLOWED,
    MAX_BYTES,
    extension_of,
    safe_filename,
    sniff,
)
from app.modules.policies.models import PolicyAcceptance, PolicyDocument

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.db.session import TenantSession
    from app.integrations.clamav import ClamAV
    from app.integrations.storage import Storage
    from app.modules.audit.service import AuditContext
    from app.modules.rbac.deps import Access

logger = get_logger("app.files")

KEY_PREFIX = "company/"
ORPHAN_GRACE = timedelta(hours=24)
_HASH_CHUNK = 1024 * 1024
_OWNER_TYPE = re.compile(r"[a-z][a-z_]{0,39}")


@dataclass(frozen=True)
class Rejection:
    """Why an upload was refused: a stable code for the client and an audit record."""

    code: str
    message: str
    status_code: int


NOT_CONFIGURED = Rejection(
    "STORAGE_NOT_CONFIGURED", "File storage is not set up on this server.", 503
)
EMPTY = Rejection("FILE_EMPTY", "That file is empty.", 422)
TOO_LARGE = Rejection(
    "PAYLOAD_TOO_LARGE", f"That file is larger than {MAX_BYTES // (1024 * 1024)} MB.", 413
)
BAD_TYPE = Rejection(
    "FILE_TYPE_NOT_ALLOWED",
    "That kind of file is not accepted. Use PDF, JPG, PNG, DOC, DOCX, XLSX or CSV.",
    415,
)
MISMATCH = Rejection(
    "FILE_TYPE_MISMATCH", "The file is not what its name says it is, so it was not accepted.", 415
)
INFECTED = Rejection(
    "FILE_INFECTED", "A virus was found in that file, so it was not accepted.", 422
)
SCAN_DOWN = Rejection(
    "SCAN_UNAVAILABLE",
    "We could not check that file for viruses just now, so it was not accepted. Try again soon.",
    503,
)
STORE_DOWN = Rejection(
    "STORAGE_UNAVAILABLE", "We could not save that file just now. Try again soon.", 503
)


def _too_large(limit: int) -> Rejection:
    return Rejection(
        "PAYLOAD_TOO_LARGE", f"That file is larger than {limit // (1024 * 1024)} MB.", 413
    )


def _digest(stream: BinaryIO) -> str:
    stream.seek(0)
    sha = hashlib.sha256()
    while chunk := stream.read(_HASH_CHUNK):
        sha.update(chunk)
    stream.seek(0)
    return sha.hexdigest()


def _size(stream: BinaryIO) -> int:
    return stream.seek(0, 2)


class FileService:
    def __init__(self, storage: Storage | None, scanner: ClamAV) -> None:
        self.storage = storage
        self.scanner = scanner

    async def _refuse(
        self,
        access: Access,
        rejection: Rejection,
        *,
        name: str,
        size: int,
        detail: str | None = None,
    ) -> AppError:
        """Record the refusal (and keep it, even though the request fails) and build the error."""
        await access.audit(
            "file.upload.rejected",
            entity_type="file",
            summary=f"{rejection.code}: {name}",
            after={"reason": rejection.code, "name": name, "size": size, "detail": detail},
        )
        await access.db.commit()
        return AppError(rejection.code, rejection.message, status_code=rejection.status_code)

    async def _vet(
        self, stream: BinaryIO, name: str, kinds: frozenset[str] | None, max_bytes: int
    ) -> tuple[int, str, Rejection | None, str | None]:
        """Size, type, real content and virus scan, in that order.

        Returns (size, mime, refusal, detail); ``refusal`` is None when the file may be kept."""
        size = await asyncio.to_thread(_size, stream)
        if size == 0:
            return size, "", EMPTY, None
        if size > max_bytes:
            return size, "", _too_large(max_bytes) if max_bytes != MAX_BYTES else TOO_LARGE, None
        extension = extension_of(name)
        if extension not in ALLOWED or (kinds is not None and ALLOWED[extension][0] not in kinds):
            return size, "", BAD_TYPE, extension[:10]
        kind, mime = ALLOWED[extension]
        if await asyncio.to_thread(sniff, stream) != kind:
            return size, mime, MISMATCH, extension
        stream.seek(0)
        verdict = await self.scanner.scan(stream)
        if verdict.status == "infected":
            return size, mime, INFECTED, verdict.signature
        if verdict.status != "clean":
            return size, mime, SCAN_DOWN, None
        return size, mime, None, None

    async def store_public(
        self,
        db: TenantSession,
        context: AuditContext,
        stream: BinaryIO,
        *,
        filename: str | None,
        owner_type: str,
        owner_id: uuid.UUID,
        kinds: frozenset[str],
        max_bytes: int,
    ) -> File:
        """A file sent by a visitor who is not signed in (a CV on the careers form).

        The same checks as ``upload``. A refusal is not recorded (nobody is signed in, and the
        request writes nothing). The caller owns the transaction and must commit it."""
        if self.storage is None:
            raise AppError(NOT_CONFIGURED.code, NOT_CONFIGURED.message, status_code=503)
        name = safe_filename(filename)
        size, mime, refusal, _detail = await self._vet(stream, name, kinds, max_bytes)
        if refusal is not None:
            raise AppError(
                refusal.code, refusal.message, status_code=refusal.status_code, field="cv"
            )
        sha256 = await asyncio.to_thread(_digest, stream)
        key = f"{KEY_PREFIX}{context.company_id}/{uuid.uuid4().hex}"
        record = File(
            company_id=context.company_id,
            storage_key=key,
            original_name=name,
            mime=mime,
            size=size,
            sha256=sha256,
            scan_status="clean",
            scanned_at=datetime.now(UTC),
            owner_type=owner_type,
            owner_id=owner_id,
            uploaded_by=None,
        )
        db.add(record)
        await db.flush()
        await record_event(
            db,
            context,
            "file.uploaded",
            entity_type="file",
            entity_id=record.id,
            after={"name": name, "mime": mime, "size": size, "owner_type": owner_type},
        )
        try:
            await self.storage.put(key, stream, content_type=mime, size=size)
        except Exception:
            await db.rollback()
            raise AppError(STORE_DOWN.code, STORE_DOWN.message, status_code=503) from None
        return record

    async def upload(
        self,
        access: Access,
        stream: BinaryIO,
        *,
        filename: str | None,
        owner_type: str | None = None,
        owner_id: uuid.UUID | None = None,
        category: str | None = None,
        kinds: frozenset[str] | None = None,
        max_bytes: int = MAX_BYTES,
        commit: bool = True,
    ) -> File:
        """Check ``stream`` and, if it passes everything, store it. Commits on success.

        ``kinds`` narrows what is accepted (a logo is a picture) and ``max_bytes`` lowers the size
        limit. With ``commit=False`` the caller finishes the transaction (to change another row
        together with the file), and must commit it."""
        if self.storage is None:
            raise AppError(NOT_CONFIGURED.code, NOT_CONFIGURED.message, status_code=503)
        await self._check_owner(access, owner_type, owner_id)
        name = safe_filename(filename)
        audit_name = "Attendance import" if owner_type == "attendance_import" else name
        size, mime, refusal, detail = await self._vet(stream, name, kinds, max_bytes)
        if refusal is not None:
            raise await self._refuse(access, refusal, name=audit_name, size=size, detail=detail)

        sha256 = await asyncio.to_thread(_digest, stream)
        key = f"{KEY_PREFIX}{access.company_id}/{uuid.uuid4().hex}"
        record = File(
            company_id=access.company_id,
            storage_key=key,
            original_name=name,
            mime=mime,
            size=size,
            sha256=sha256,
            scan_status="clean",
            scanned_at=datetime.now(UTC),
            owner_type=owner_type,
            owner_id=owner_id,
            category=category,
            uploaded_by=access.caller.user_id,
        )
        access.db.add(record)
        await access.db.flush()
        await access.audit(
            "file.uploaded",
            entity_type="file",
            entity_id=record.id,
            after={"name": audit_name, "mime": mime, "size": size, "owner_type": owner_type},
        )
        try:
            # The bytes go in before the commit: if this fails nothing is kept, and if the commit
            # fails afterwards the object is an orphan that the clean-up job removes.
            await self.storage.put(key, stream, content_type=mime, size=size)
        except Exception:
            await access.db.rollback()
            raise AppError(STORE_DOWN.code, STORE_DOWN.message, status_code=503) from None
        if commit:
            await access.db.commit()
        return record

    async def download_url(self, access: Access, file_id: uuid.UUID) -> tuple[str, File]:
        """A 60-second link for a file this person may read, after recording that they asked."""
        if self.storage is None:
            raise AppError(NOT_CONFIGURED.code, NOT_CONFIGURED.message, status_code=503)
        record = await self.get(access, file_id)
        if record.scan_status != "clean":
            raise NotFoundError
        await access.audit(
            "file.downloaded", entity_type="file", entity_id=record.id, summary=record.original_name
        )
        await access.db.commit()
        return self.storage.presign_get(record.storage_key, filename=record.original_name), record

    async def get(self, access: Access, file_id: uuid.UUID) -> File:
        """A file of this company that the person's permission reaches, else 404."""
        record = (
            await access.db.execute(
                select(File).where(File.id == file_id, File.company_id == access.company_id)
            )
        ).scalar_one_or_none()
        if record is None or not await self._reaches(access, record):
            raise NotFoundError
        return record

    @staticmethod
    async def _check_owner(
        access: Access, owner_type: str | None, owner_id: uuid.UUID | None
    ) -> None:
        """What the file is attached to must be well formed, and within the person's reach."""
        if (
            owner_type == "attendance_import"
            and scope_for(access.role, "attendance.record.write") is not Scope.ALL
        ):
            raise ForbiddenError
        if owner_type is None and owner_id is None:
            if access.scope is not Scope.ALL:
                raise ForbiddenError
            return
        if owner_type is None or owner_id is None or not _OWNER_TYPE.fullmatch(owner_type):
            raise AppError(
                "VALIDATION_ERROR",
                "Say what the file belongs to (a type and an id).",
                status_code=422,
                field="owner_type",
            )
        if owner_type == "candidate":
            from app.modules.recruitment.models import Candidate

            found = (
                await access.db.execute(select(Candidate.id).where(Candidate.id == owner_id))
            ).first()
            if found is None:
                raise NotFoundError
        if access.scope is not Scope.ALL and (
            owner_type != "employee" or not await access.can_reach(owner_id)
        ):
            raise ForbiddenError

    @staticmethod
    async def _reaches(access: Access, record: File) -> bool:
        """Everyone with full scope; otherwise what the person uploaded or that is within reach."""
        if record.owner_type == "policy_document":
            policy = (
                await access.db.execute(
                    select(PolicyDocument).where(PolicyDocument.id == record.owner_id)
                )
            ).scalar_one_or_none()
            if policy is None:
                return False
            if scope_for(access.role, "policy.document.read") is Scope.ALL:
                return True
            if (
                scope_for(access.role, "policy.acceptance.read") is None
                or access.employee_id is None
                or policy.file_id != record.id
                or policy.status == "draft"
            ):
                return False
            assigned = select(PolicyAcceptance.id).where(
                PolicyAcceptance.policy_document_id == policy.id,
                PolicyAcceptance.employee_id == access.employee_id,
            )
            if policy.status == "archived":
                assigned = assigned.where(PolicyAcceptance.accepted_at.is_not(None))
            return (await access.db.execute(assigned)).first() is not None
        if record.owner_type == "report_result":
            return (
                scope_for(access.role, "document.report.generate") is Scope.ALL
                and record.uploaded_by == access.caller.user_id
            )
        if record.owner_type == "company_document":
            return scope_for(access.role, "document.file.read") is Scope.ALL
        if record.owner_type == "attendance_import":
            return scope_for(access.role, "attendance.record.read") is Scope.ALL
        if access.scope is Scope.ALL or record.uploaded_by == access.caller.user_id:
            return True
        return (
            record.owner_type == "employee"
            and record.owner_id is not None
            and await access.can_reach(record.owner_id)
        )


async def remove_orphans(
    storage: Storage,
    owner_engine: AsyncEngine,
    *,
    older_than: timedelta = ORPHAN_GRACE,
    now: datetime | None = None,
) -> int:
    """Delete objects in the bucket that no ``files`` row points to; returns how many.

    An upload that failed between storing the bytes and committing the row leaves one behind. The
    grace period keeps this from racing an upload that is still in progress. It runs as the table
    owner (outside any company), so it sees every company's rows.
    """
    from sqlalchemy import column, table

    cutoff = (now or datetime.now(UTC)) - older_than
    objects = [o for o in await storage.list_objects(KEY_PREFIX) if o.last_modified < cutoff]
    if not objects:
        return 0
    files = table("files", column("storage_key"))
    known: set[str] = set()
    async with owner_engine.connect() as connection:
        keys = [o.key for o in objects]
        for start in range(0, len(keys), 1000):
            result = await connection.execute(
                select(files.c.storage_key).where(
                    files.c.storage_key.in_(keys[start : start + 1000])
                )
            )
            known.update(row[0] for row in result)
    removed = 0
    for stored in objects:
        if stored.key not in known:
            await storage.delete(stored.key)
            removed += 1
    if removed:
        logger.info("orphans_removed", count=removed)
    return removed
