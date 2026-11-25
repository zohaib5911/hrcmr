"""What a company's export holds (T16.4): its records as CSV, one file per table, and its documents.

Every table with a ``company_id`` is included, read through the company's own session (so row
security only returns that company's rows), plus the company's own row. Some tables and columns
never leave the system whatever the table: working data (sessions), credentials and share codes,
network details and storage locations. Bank account numbers and sort codes are left out too; the
company can see them in the app. The README in the zip says what is missing.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import tempfile
import zipfile
from datetime import date, datetime
from decimal import Decimal
from typing import IO, TYPE_CHECKING, Any, BinaryIO

from sqlalchemy import or_, select

from app.core.logging import get_logger
from app.db.base import Base
from app.integrations.storage import StorageError
from app.modules.files.models import File

if TYPE_CHECKING:
    import uuid

    from sqlalchemy import Column, Table
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.integrations.storage import Storage

logger = get_logger("app.exports")

ZIP = "application/zip"
# The app's own outputs are not the company's documents (they are regenerated on request).
DERIVED_OWNERS = ("report_result", "data_export")
LEFT_OUT_TABLES = frozenset({"sessions", "checkout_attempts"})
NEVER_EXPORTED = frozenset(
    {
        "token_hash",
        "share_code",
        "preview_token",
        "storage_key",
        "ip",
        "user_agent",
        "request_id",
        "impersonation_session_id",
        "step_up_at",
        "mfa_passed_at",
        "account_number",
        "sort_code",
        "ni_number_index",
        # A deletion request's code is kept only as a hash; even the hash is not exported (C3.1.16).
        "code_hash",
    }
)
_UNSAFE = re.compile(r"[^A-Za-z0-9._ -]")


def sources() -> list[tuple[Table, Column[Any]]]:
    """Each table to export, with the column that holds the company's id (``companies`` is keyed by
    its own id)."""
    out: list[tuple[Table, Column[Any]]] = []
    for table in Base.metadata.sorted_tables:
        if table.name in LEFT_OUT_TABLES:
            continue
        if "company_id" in table.c:
            out.append((table, table.c["company_id"]))
        elif table.name == "companies":
            out.append((table, table.c["id"]))
    return out


def exported_columns(table: Table) -> list[Column[Any]]:
    return [column for column in table.c if column.name not in NEVER_EXPORTED]


def cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict | list):
        return json.dumps(value, default=str, sort_keys=True)
    return str(value)


def spreadsheet_text(value: str) -> str:
    """Force formula-capable cells to text, including control-prefixed spreadsheet input."""
    candidate = value.lstrip(" \t\r\n")
    prefixes = ("=", "+", "-", "@", "\uff1d", "\uff0b", "\uff0d", "\uff20")
    if candidate.startswith(prefixes) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def csv_text(headers: list[str], rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerow([spreadsheet_text(value) for value in headers])
    writer.writerows([spreadsheet_text(value) for value in row] for row in rows)
    return buffer.getvalue().encode("utf-8")


def safe_name(name: str) -> str:
    cleaned = _UNSAFE.sub("_", name).strip(" .")[:120]
    return cleaned or "document"


def readme(company_name: str, when: datetime, missing: int) -> bytes:
    lines = [
        f"Data export for {company_name}",
        f"Made {when:%d %B %Y at %H:%M} UTC.",
        "",
        "tables/   one CSV file per kind of record, for your company only.",
        "documents/   the files you uploaded; documents.csv lists each with its path.",
        "",
        "Not included: bank account numbers and sort codes (you can see them in the app),",
        "sign-in sessions, access tokens and share codes, and technical details such as IP",
        "addresses and storage locations.",
    ]
    if missing:
        lines += ["", f"{missing} document(s) could not be read and are listed as missing."]
    return ("\n".join(lines) + "\n").encode("utf-8")


ROW_BATCH = 1000  # rows read from the database per step
SPOOL_LIMIT = 1 << 20  # the document index stays in memory up to 1 MiB, then goes to disk
INDEX_HEADERS = [
    "id",
    "original_name",
    "mime",
    "size",
    "sha256",
    "category",
    "owner_type",
    "uploaded_at",
    "status",
    "path",
]


def _csv_writer(stream: IO[str]) -> Any:
    writer = csv.writer(stream, quoting=csv.QUOTE_ALL)

    class Safe:
        def row(self, values: list[str]) -> None:
            writer.writerow([spreadsheet_text(value) for value in values])

    return Safe()


async def _write_table(
    db: AsyncSession,
    archive: zipfile.ZipFile,
    table: Table,
    key: Column[Any],
    company_id: uuid.UUID,
) -> None:
    """One table's CSV, written into the zip a batch of rows at a time (ISS-33)."""
    columns = exported_columns(table)
    statement = select(*columns).where(key == company_id)
    if "id" in table.c:
        statement = statement.order_by(table.c["id"])
    with (
        archive.open(f"tables/{table.name}.csv", "w", force_zip64=True) as raw,
        io.TextIOWrapper(raw, encoding="utf-8", newline="") as text,
    ):
        out = _csv_writer(text)
        out.row([c.name for c in columns])
        result = await db.stream(statement.execution_options(yield_per=ROW_BATCH))
        async for batch in result.partitions(ROW_BATCH):
            for row in batch:
                out.row([cell(v) for v in row])


async def _write_document(
    archive: zipfile.ZipFile, storage: Storage, record: File, path: str
) -> bool:
    """Copies one file into the zip piece by piece. False if storage cannot open it."""
    try:
        pieces = await storage.open(record.storage_key)
    except StorageError:
        return False
    with archive.open(path, "w", force_zip64=True) as entry:
        async for piece in pieces:
            entry.write(piece)
    return True


async def write_archive(
    db: AsyncSession,
    storage: Storage,
    company_id: uuid.UUID,
    company_name: str,
    when: datetime,
    target: BinaryIO,
) -> int:
    """Writes the zip to ``target``. Returns how many documents could not be read.

    Nothing is held whole (ISS-33): table rows are read and written in batches, file bodies are
    copied in storage-sized pieces, and the document index is spooled (to disk past 1 MiB)."""
    missing = 0
    with (
        zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive,
        tempfile.SpooledTemporaryFile(max_size=SPOOL_LIMIT, mode="w+b") as spool,
        io.TextIOWrapper(spool, encoding="utf-8", newline="") as index_text,
    ):
        for table, key in sources():
            await _write_table(db, archive, table, key, company_id)

        index = _csv_writer(index_text)
        index.row(INDEX_HEADERS)
        documents = await db.stream(
            select(File)
            .where(
                File.scan_status == "clean",
                or_(File.owner_type.is_(None), File.owner_type.not_in(DERIVED_OWNERS)),
            )
            .order_by(File.created_at, File.id)
            .execution_options(yield_per=ROW_BATCH)
        )
        async for batch in documents.scalars().partitions(ROW_BATCH):
            for record in batch:
                path = f"documents/{record.id}/{safe_name(record.original_name)}"
                status = "included"
                if not await _write_document(archive, storage, record, path):
                    logger.warning("export_document_missing", file_id=str(record.id))
                    missing += 1
                    status, path = "missing", ""
                index.row(
                    [
                        str(record.id),
                        record.original_name,
                        record.mime,
                        str(record.size),
                        record.sha256 or "",
                        record.category or "",
                        record.owner_type or "",
                        cell(record.created_at),
                        status,
                        path,
                    ]
                )
        index_text.flush()
        spool.seek(0)
        with archive.open("documents.csv", "w", force_zip64=True) as entry:
            shutil.copyfileobj(spool, entry, 1 << 16)
        archive.writestr("README.txt", readme(company_name, when, missing))
    return missing


def digest(target: BinaryIO) -> str:
    """SHA-256 of the file from its start; leaves the file at the start."""
    target.seek(0)
    hasher = hashlib.sha256()
    for chunk in iter(lambda: target.read(1 << 20), b""):
        hasher.update(chunk)
    target.seek(0)
    return hasher.hexdigest()
