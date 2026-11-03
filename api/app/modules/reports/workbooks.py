"""Internally generated XLSX: untrusted text is always text, never a formula or external link."""

from __future__ import annotations

import io
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core.errors import AppError

if TYPE_CHECKING:
    from app.modules.reports.projections import SheetData

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_BYTES = 25 * 1024 * 1024


def workbook_bytes(sheets: dict[str, SheetData]) -> bytes:
    book = Workbook(write_only=True)
    try:
        for name, data in sheets.items():
            sheet = book.create_sheet(name)
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = f"A1:{get_column_letter(len(data.headers))}{len(data.rows) + 1}"
            for column in range(1, len(data.headers) + 1):
                sheet.column_dimensions[get_column_letter(column)].width = 24
            for index, values in enumerate([data.headers, *data.rows]):
                cells = []
                for value in values:
                    if isinstance(value, datetime) and value.tzinfo is not None:
                        value = value.isoformat()
                    if not (
                        value is None
                        or isinstance(value, (str, int, float, bool, date, time, Decimal))
                    ):
                        value = str(value)
                    if isinstance(value, str):
                        value = ILLEGAL_CHARACTERS_RE.sub(" ", value)
                    if isinstance(value, Decimal):
                        value = float(value)
                    if isinstance(value, time):
                        value = value.isoformat()
                    if isinstance(value, date) and not isinstance(value, datetime):
                        value = datetime.combine(value, time.min)
                    cell = WriteOnlyCell(sheet, value=value)
                    if isinstance(value, str):
                        cell.data_type = "s"
                    if isinstance(value, date):
                        cell.number_format = "dd mmm yyyy"
                    if index == 0:
                        cell.font = Font(bold=True, color="FFFFFF")
                        cell.fill = PatternFill("solid", fgColor="005DAA")
                    cells.append(cell)
                sheet.append(cells)
        buffer = io.BytesIO()
        book.save(buffer)
        content = buffer.getvalue()
        if len(content) > MAX_BYTES:
            raise AppError(
                "REPORT_TOO_LARGE", "This report exceeds the supported size.", status_code=422
            )
        return content
    finally:
        book.close()
