"""Bounded, value-only CSV/XLSX attendance input and spreadsheet-safe output."""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import TYPE_CHECKING, cast

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.cell import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from app.core.errors import AppError
from app.modules.audit.router import csv_cell

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from openpyxl.worksheet.worksheet import Worksheet

MAX_ROWS = 1000
MAX_BYTES = 5 * 1024 * 1024
HEADERS = ("employee_number", "date", "status", "clock_in", "clock_out", "note")
OPTIONAL = frozenset({"unpaid_break_minutes", "clock_in_occurrence", "clock_out_occurrence"})
STATUS_LABELS = ("Present", "Absent", "Late", "Half day", "On leave", "Sick")


@dataclass(frozen=True)
class ParsedRow:
    number: int
    values: dict[str, str]
    error: str | None = None


def _bad(message: str) -> AppError:
    return AppError("INVALID_IMPORT", message, status_code=422)


def _text(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, time):
        return (
            value.isoformat(timespec="minutes")
            if not value.second and not value.microsecond
            else value.isoformat()
        )
    if isinstance(value, date):
        return value.isoformat()
    return "" if value is None else str(value)


def _header(values: list[str]) -> list[str]:
    columns = [v.strip().lower() for v in values]
    if (
        len(columns) != len(set(columns))
        or not set(HEADERS) <= set(columns)
        or set(columns) - set(HEADERS) - OPTIONAL
    ):
        raise _bad("Use the template's six columns, without duplicate or unknown headings.")
    return columns


def _row(number: int, columns: list[str], values: list[str], error: str | None = None) -> ParsedRow:
    if len(values) > len(columns):
        error = "This row has more cells than the header."
    padded = (values + [""] * len(columns))[: len(columns)]
    return ParsedRow(number, dict(zip(columns, padded, strict=True)), error)


def parse_rows(content: bytes, *, xlsx: bool) -> list[ParsedRow]:
    if len(content) > MAX_BYTES:
        raise _bad("Use an import file no larger than 5 MB.")
    rows: list[ParsedRow] = []
    try:
        if not xlsx:
            reader = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""))
            columns = _header(next(reader, []))
            for number, values in enumerate(reader, 2):
                if not any(v.strip() for v in values):
                    continue
                rows.append(_row(number, columns, values))
                if len(rows) > MAX_ROWS:
                    raise _bad(f"Use at most {MAX_ROWS} attendance rows per import.")
        else:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(e.file_size for e in entries) > 20 * 1024 * 1024:
                    raise _bad("The workbook expands beyond the import size limit.")
                if any(
                    "vbaProject" in e.filename or e.filename.startswith("xl/externalLinks/")
                    for e in entries
                ):
                    raise _bad("Use a workbook without macros or external workbook links.")
            book = load_workbook(
                io.BytesIO(content), read_only=True, data_only=False, keep_links=False
            )
            try:
                if len(book.worksheets) != 1:
                    raise _bad("Use one worksheet containing the attendance template.")
                sheet = book.worksheets[0]
                if (
                    sheet.max_row is None
                    or sheet.max_row > MAX_ROWS + 1
                    or (sheet.max_column or 0) > len(HEADERS) + len(OPTIONAL)
                ):
                    raise _bad(f"Use at most {MAX_ROWS} data rows and the template columns.")
                cells = iter(sheet.iter_rows())
                columns = _header([_text(c.value) for c in next(cells, ())])
                for number, line in enumerate(cells, 2):
                    values = [_text(c.value) for c in line]
                    if not any(v.strip() for v in values):
                        continue
                    error = (
                        "Replace formula or error cells with values."
                        if any(c.data_type in ("f", "e") for c in line)
                        else None
                    )
                    rows.append(_row(number, columns, values, error))
            finally:
                book.close()
    except AppError:
        raise
    except Exception:
        raise _bad("We could not read this file. Use a UTF-8 CSV or the XLSX template.") from None
    if not rows:
        raise _bad("Add at least one attendance row before uploading the template.")
    return rows


def csv_bytes(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows([csv_cell(v) for v in row] for row in rows)
    return stream.getvalue().encode("utf-8-sig")


def xlsx_bytes(
    headers: Sequence[str], rows: Iterable[Sequence[object]], *, template: bool = False
) -> bytes:
    book = Workbook()
    sheet = cast("Worksheet", book.active)
    sheet.title = "Attendance"
    for number, values in enumerate((headers, *rows), 1):
        for column, value in enumerate(values, 1):
            cell = sheet.cell(number, column)
            cell.value = (
                value
                if value is None or isinstance(value, (str, int, float, bool, datetime, date, time))
                else str(value)
            )
            if isinstance(cell.value, str):
                cell.data_type = "s"  # Never interpret user-controlled names/notes as formulae.
            if number == 1:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="005DAA")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column_index in range(1, len(headers) + 1):
        sheet.column_dimensions[get_column_letter(column_index)].width = 24
    if template:
        validation = DataValidation(
            type="list", formula1='"' + ",".join(STATUS_LABELS) + '"', allow_blank=False
        )
        validation.errorTitle = "Choose a status"
        validation.error = "Choose a status from the dropdown."
        validation.showErrorMessage = True
        sheet.add_data_validation(validation)
        validation.add(f"C2:C{MAX_ROWS + 1}")
        for cell in sheet["A"]:
            cell.number_format = "@"
    buffer = io.BytesIO()
    try:
        book.save(buffer)
        return buffer.getvalue()
    finally:
        book.close()
