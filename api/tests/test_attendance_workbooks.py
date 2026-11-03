"""T9.2 workbook values, status dropdown, bounded parsing and safe spreadsheet output."""

from __future__ import annotations

import io
import zipfile
from datetime import date, time

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.xml import DEFUSEDXML

from app.core.errors import AppError
from app.modules.attendance.workbooks import HEADERS, MAX_ROWS, csv_bytes, parse_rows, xlsx_bytes


def test_template_has_status_dropdown_and_typed_values_are_read() -> None:
    assert DEFUSEDXML
    template = load_workbook(io.BytesIO(xlsx_bytes(HEADERS, [], template=True)))
    sheet = template.active
    assert sheet is not None
    assert [c.value for c in sheet[1]] == list(HEADERS)
    assert str(sheet.data_validations.dataValidation[0].sqref) == f"C2:C{MAX_ROWS + 1}"
    assert "Half day" in sheet.data_validations.dataValidation[0].formula1
    sheet.append(["001", date(2026, 11, 3), "Present", time(9), time(17), "Desk"])
    stream = io.BytesIO()
    template.save(stream)
    template.close()
    row = parse_rows(stream.getvalue(), xlsx=True)[0]
    assert row.values["employee_number"] == "001"
    assert row.values["date"] == "2026-11-03"
    assert row.values["clock_in"] == "09:00"


def test_csv_quotes_and_unicode_are_retained_and_export_formulae_are_text() -> None:
    raw = 'employee_number,date,status,clock_in,clock_out,note\r\nE1,2026-11-03,Sick,,,"Amélie,\nreview"\r\n'.encode()
    row = parse_rows(raw, xlsx=False)[0]
    assert row.values["note"] == "Amélie,\nreview"
    assert b"'=1+1" in csv_bytes(["note"], [["=1+1"]])
    book = load_workbook(io.BytesIO(xlsx_bytes(["note"], [["=1+1"]])))
    assert book.active is not None
    assert book.active["A2"].data_type == "s"
    assert book.active["A2"].value == "=1+1"
    book.close()


def test_formula_and_error_cells_are_flagged_per_row() -> None:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(HEADERS)
    sheet.append(["E1", "2026-11-03", "Present", "09:00", "17:00", "=1+1"])
    stream = io.BytesIO()
    book.save(stream)
    book.close()
    assert "formula" in (parse_rows(stream.getvalue(), xlsx=True)[0].error or "")


@pytest.mark.parametrize(
    "content",
    [
        b"employee_number,date,status,clock_in,clock_out,status\nE1,2026-11-03,Sick,,,\n",
        b"employee_number,date,status,clock_in,clock_out,note,unknown\nE1,2026-11-03,Sick,,,,\n",
        b"employee_number,date,status,clock_in,clock_out,note\n",
        b"not a workbook",
    ],
)
def test_bad_headers_empty_and_unreadable_files_fail(content: bytes) -> None:
    with pytest.raises(AppError):
        parse_rows(content, xlsx=False)


def test_row_limit_and_zip_expansion_limit_are_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.modules.attendance.workbooks.MAX_ROWS", 1)
    raw = b"employee_number,date,status,clock_in,clock_out,note\nE1,2026-11-03,Sick,,,\nE2,2026-11-03,Sick,,,\n"
    with pytest.raises(AppError, match="at most"):
        parse_rows(raw, xlsx=False)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/sharedStrings.xml", b"x" * (21 * 1024 * 1024))
    with pytest.raises(AppError, match="expands"):
        parse_rows(buffer.getvalue(), xlsx=True)
