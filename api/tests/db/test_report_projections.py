"""T10.2: safe explicit report columns, tenant boundaries and company-local as-of projections."""

from __future__ import annotations

import io
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from openpyxl import load_workbook
from sqlalchemy import text

from app.core.errors import AppError
from app.db.session import TenantSession
from app.modules.companies.models import Department
from app.modules.employees.models import Employee, EmployeeAssignment, EmployeeTrainingRecord
from app.modules.leave.models import LeaveType
from app.modules.leave.request_models import LeaveRequest
from app.modules.reports import projections
from app.modules.reports.projections import project
from app.modules.reports.reference import REPORT_TYPES
from app.modules.reports.workbooks import workbook_bytes
from app.modules.sponsor_documents.models import SponsorDocument
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig

AS_OF = datetime(2026, 1, 10, 12, tzinfo=UTC)


@pytest.fixture
async def records(rig: dict[str, Any]) -> dict[str, Any]:
    async with TenantSession(rig["app"].state.engine, company_id=rig["a"]) as db:
        employee = Employee(
            company_id=rig["a"],
            employee_number="001",
            first_name="=2+3",
            last_name="Report",
            email="r@example.com",
            hire_date=date(2025, 1, 1),
        )
        archived = Employee(
            company_id=rig["a"],
            employee_number="002",
            first_name="Archived",
            last_name="Report",
            email="a@example.com",
            hire_date=date(2025, 1, 1),
            status="archived",
        )
        department = Department(company_id=rig["a"], name="Current department")
        future = Department(company_id=rig["a"], name="Future department")
        kind = LeaveType(company_id=rig["a"], name="Annual")
        db.add_all([employee, archived, department, future, kind])
        await db.flush()
        db.add_all(
            [
                EmployeeAssignment(
                    company_id=rig["a"],
                    employee_id=employee.id,
                    department_id=department.id,
                    employment_type="full_time",
                    effective_from=date(2025, 1, 1),
                    ended_at=date(2027, 1, 1),
                ),
                EmployeeAssignment(
                    company_id=rig["a"],
                    employee_id=employee.id,
                    department_id=future.id,
                    employment_type="full_time",
                    effective_from=date(2027, 1, 1),
                ),
                SponsorDocument(
                    company_id=rig["a"],
                    employee_id=employee.id,
                    doc_type="visa",
                    visa_route="skilled_worker",
                    version=1,
                    expiry_date=date(2026, 12, 1),
                    soc_code="2134",
                ),
                LeaveRequest(
                    company_id=rig["a"],
                    employee_id=employee.id,
                    leave_type_id=kind.id,
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 1, 20),
                    working_days=Decimal("1.5"),
                    working_dates={"2026-01-01": "1/2", "2026-01-20": "1"},
                    status="approved",
                ),
                LeaveRequest(
                    company_id=rig["a"],
                    employee_id=employee.id,
                    leave_type_id=kind.id,
                    start_date=date(2026, 1, 2),
                    end_date=date(2026, 1, 2),
                    working_days=Decimal("1"),
                    working_dates={"2026-01-02": "1"},
                    status="pending",
                ),
                EmployeeTrainingRecord(
                    company_id=rig["a"],
                    employee_id=employee.id,
                    title="Completed training",
                    ended_on=date(2026, 1, 5),
                ),
                EmployeeTrainingRecord(
                    company_id=rig["a"],
                    employee_id=employee.id,
                    title="Future training",
                    ended_on=date(2026, 2, 1),
                ),
                EmployeeTrainingRecord(
                    company_id=rig["a"], employee_id=employee.id, title="Not yet completed"
                ),
            ]
        )
        await db.commit()
    # Invalid ciphertext proves report projections never load/decrypt the sensitive employee fields.
    async with rig["owner"].begin() as connection:
        await connection.execute(
            text(
                "update employees set ni_number='opaque-test-ciphertext', passport_number='opaque-test-ciphertext' where company_id=:c"
            ),
            {"c": rig["a"]},
        )
    return rig


async def test_seven_reports_keep_tenants_and_sensitive_fields_out(records: dict[str, Any]) -> None:
    for kind in REPORT_TYPES:
        async with TenantSession(records["app"].state.engine, company_id=records["a"]) as db:
            sheets = await project(db, kind, AS_OF)
        content = workbook_bytes(sheets)
        book = load_workbook(io.BytesIO(content))
        assert "About this report" in book.sheetnames
        for sheet in book:
            assert sheet.freeze_panes == "A2"
            for row in sheet:
                for cell in row:
                    assert cell.data_type != "f"
                    assert cell.hyperlink is None
                    assert cell.value != "opaque-test-ciphertext"
        if kind in {"employee_directory", "employee_detail"}:
            report = book[
                "Employee Directory" if kind == "employee_directory" else "Employee Detail"
            ]
            assert report["A2"].value == "001"
            assert report["B2"].value == "=2+3"
            assert report["B2"].data_type == "s"
            assert report["D2"].value == "Current department"
            assert report.max_row == 2
            headers = [cell.value for cell in report[1]]
            assert not {"NI number", "Passport number", "Salary", "Date of birth"} & set(headers)
            if kind == "employee_detail":
                assert "Right to Work status" in headers
        if kind == "archived_employees":
            assert book["Archived Employees"]["A2"].value == "002"
        if kind == "sponsor_workers":
            assert book["Sponsor workers"]["E2"].value == "skilled_worker"
            assert book["Sponsor workers"]["F2"].value == "2134"
        if kind == "leave_taken":
            assert book["Leave taken"].max_row == 2
            assert book["Leave taken"]["F2"].value == 0.5
        if kind == "training_completion":
            assert book["Training completion"].max_row == 2
            assert book["Training completion"]["D2"].value == "Completed training"
        if kind == "company":
            assert {
                "Company",
                "Locations and addresses",
                "Departments",
                "Key personnel",
                "Trading hours",
                "Compliance documents",
            } <= set(book.sheetnames)
        book.close()
        async with TenantSession(records["app"].state.engine, company_id=records["b"]) as db:
            other = await project(db, kind, AS_OF)
        assert not any(
            "=2+3" in str(row) or "Current department" in str(row)
            for data in other.values()
            for row in data.rows
        )


async def test_row_limit_refuses_instead_of_truncating(
    records: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(projections, "MAX_ROWS", 1)
    async with TenantSession(records["app"].state.engine, company_id=records["a"]) as db:
        with pytest.raises(AppError, match="supported size"):
            await project(db, "company", AS_OF)
