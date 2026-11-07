"""The learning report as an .xlsx file (plan 8.14). Styled like the attendance export."""

from __future__ import annotations

import io
from datetime import date, datetime
from typing import TYPE_CHECKING, cast

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from openpyxl.worksheet.worksheet import Worksheet


def xlsx_bytes(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> bytes:
    book = Workbook()
    sheet = cast("Worksheet", book.active)
    sheet.title = "Learning report"
    for number, values in enumerate((headers, *rows), 1):
        for column, value in enumerate(values, 1):
            cell = sheet.cell(number, column)
            cell.value = (
                value
                if value is None or isinstance(value, (str, int, float, bool, date, datetime))
                else str(value)
            )
            if isinstance(cell.value, str):
                cell.data_type = "s"  # Never interpret names or titles as formulae.
            if number == 1:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="005DAA")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column_index in range(1, len(headers) + 1):
        sheet.column_dimensions[get_column_letter(column_index)].width = 24
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()
