"""Explicit report columns: never load employee pay, encrypted IDs or free entry notes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import distinct_on

from app.core.errors import AppError
from app.db.rtw import employee_rtw_status
from app.modules.companies.models import (
    Company,
    ComplianceDocument,
    Department,
    Designation,
    KeyPerson,
    Location,
    TradingHoursDay,
)
from app.modules.employees.models import Employee, EmployeeAssignment, EmployeeTrainingRecord
from app.modules.files.models import File
from app.modules.leave.models import LeaveType
from app.modules.leave.request_models import LeaveRequest
from app.modules.reports.reference import REPORT_LABELS
from app.modules.sponsor_documents.models import SponsorDocument
from app.modules.sponsor_documents.reference import SPONSORED_ROUTES

if TYPE_CHECKING:
    from sqlalchemy import Select

    from app.db.session import TenantSession

MAX_ROWS = 50_000


@dataclass(frozen=True)
class SheetData:
    headers: tuple[str, ...]
    rows: list[tuple[object, ...]]


async def _rows(db: TenantSession, query: Select[*tuple[Any, ...]]) -> list[tuple[object, ...]]:
    rows = (await db.execute(query.limit(MAX_ROWS + 1))).all()
    if len(rows) > MAX_ROWS:
        raise AppError(
            "REPORT_TOO_LARGE", "This report exceeds the supported size.", status_code=422
        )
    return [tuple(row) for row in rows]


async def project(
    db: TenantSession, report_type: str, generated_at: datetime
) -> dict[str, SheetData]:
    company = (await db.execute(select(Company).where(Company.id == db.company_id))).scalar_one()
    today = generated_at.astimezone(ZoneInfo(company.timezone)).date()
    sheets = {
        "About this report": SheetData(
            ("Field", "Value"),
            [
                ("Report", REPORT_LABELS[report_type]),
                ("Company", company.name),
                ("As of company date", today),
                ("Time zone", company.timezone),
                ("Generated at (UTC)", generated_at.isoformat()),
            ],
        )
    }
    if report_type in {"employee_directory", "employee_detail", "archived_employees"}:
        assignment = (
            select(
                EmployeeAssignment.employee_id,
                EmployeeAssignment.department_id,
                EmployeeAssignment.designation_id,
                EmployeeAssignment.location_id,
            )
            .where(
                EmployeeAssignment.effective_from <= today,
                or_(EmployeeAssignment.ended_at.is_(None), EmployeeAssignment.ended_at > today),
            )
            .ext(distinct_on(EmployeeAssignment.employee_id))
            .order_by(
                EmployeeAssignment.employee_id,
                EmployeeAssignment.effective_from.desc(),
                EmployeeAssignment.id.desc(),
            )
            .subquery()
        )
        columns = [
            Employee.employee_number,
            Employee.first_name,
            Employee.last_name,
            Department.name,
            Employee.status,
            Employee.hire_date,
        ]
        headers: tuple[str, ...] = (
            "Employee number",
            "First name",
            "Last name",
            "Department",
            "Status",
            "Hire date",
        )
        query: Select[*tuple[Any, ...]] = (
            select(*columns)
            .outerjoin(assignment, assignment.c.employee_id == Employee.id)
            .outerjoin(Department, Department.id == assignment.c.department_id)
        )
        if report_type == "employee_detail":
            query = (
                query.add_columns(
                    Designation.title,
                    Location.name,
                    Employee.leave_date,
                    employee_rtw_status.c.status,
                )
                .outerjoin(Designation, Designation.id == assignment.c.designation_id)
                .outerjoin(Location, Location.id == assignment.c.location_id)
                .outerjoin(
                    employee_rtw_status,
                    (employee_rtw_status.c.employee_id == Employee.id)
                    & (employee_rtw_status.c.company_id == db.company_id),
                )
            )
            headers += ("Designation", "Location", "Leave date", "Right to Work status")
        query = query.where(
            Employee.status == "archived"
            if report_type == "archived_employees"
            else Employee.status != "archived"
        ).order_by(Employee.employee_number, Employee.id)
        sheets[REPORT_LABELS[report_type]] = SheetData(headers, await _rows(db, query))
    elif report_type == "company":
        sheets.update(await _company_sheets(db, company))
    elif report_type == "sponsor_workers":
        query = (
            select(
                Employee.employee_number,
                Employee.first_name,
                Employee.last_name,
                Employee.status,
                SponsorDocument.visa_route,
                SponsorDocument.soc_code,
                SponsorDocument.issue_date,
                SponsorDocument.expiry_date,
                SponsorDocument.review_date,
            )
            .join(SponsorDocument, SponsorDocument.employee_id == Employee.id)
            .where(
                Employee.status != "archived",
                SponsorDocument.doc_type == "visa",
                SponsorDocument.visa_route.in_(SPONSORED_ROUTES),
                SponsorDocument.withdrawn_at.is_(None),
                SponsorDocument.superseded_by.is_(None),
            )
            .order_by(Employee.employee_number, Employee.id)
        )
        sheets["Sponsor workers"] = SheetData(
            (
                "Employee number",
                "First name",
                "Last name",
                "Status",
                "Visa route",
                "SOC code",
                "Issue date",
                "Expiry date",
                "Review date",
            ),
            await _rows(db, query),
        )
    elif report_type == "leave_taken":
        # Dated snapshots preserve the approved personal-pattern charge. Future days are not taken.
        query = (
            select(
                Employee.employee_number,
                Employee.first_name,
                Employee.last_name,
                LeaveType.name,
                LeaveRequest.working_dates,
            )
            .join(LeaveRequest, LeaveRequest.employee_id == Employee.id)
            .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
            .where(LeaveRequest.status == "approved", LeaveRequest.start_date <= today)
            .order_by(Employee.employee_number, LeaveRequest.start_date, LeaveRequest.id)
        )
        taken: list[tuple[object, ...]] = []
        for number, first, last, kind, snapshot in await _rows(db, query):
            if not isinstance(snapshot, dict):
                raise ValueError("Invalid leave snapshot")
            for day, quantity in sorted(snapshot.items()):
                if str(day) > today.isoformat():
                    continue
                fraction = Fraction(str(quantity))
                days = Decimal(fraction.numerator) / Decimal(fraction.denominator)
                taken.append(
                    (
                        number,
                        first,
                        last,
                        kind,
                        date.fromisoformat(str(day)),
                        days.quantize(Decimal("0.01")),
                    )
                )
                if len(taken) > MAX_ROWS:
                    raise AppError(
                        "REPORT_TOO_LARGE",
                        "This report exceeds the supported size.",
                        status_code=422,
                    )
        sheets["Leave taken"] = SheetData(
            ("Employee number", "First name", "Last name", "Leave type", "Date", "Days"), taken
        )
    elif report_type == "training_completion":
        query = (
            select(
                Employee.employee_number,
                Employee.first_name,
                Employee.last_name,
                EmployeeTrainingRecord.title,
                EmployeeTrainingRecord.started_on,
                EmployeeTrainingRecord.ended_on,
            )
            .join(EmployeeTrainingRecord, EmployeeTrainingRecord.employee_id == Employee.id)
            .where(EmployeeTrainingRecord.ended_on <= today)
            .order_by(
                Employee.employee_number, EmployeeTrainingRecord.ended_on, EmployeeTrainingRecord.id
            )
        )
        sheets["Training completion"] = SheetData(
            (
                "Employee number",
                "First name",
                "Last name",
                "Training",
                "Started on",
                "Completed on",
            ),
            await _rows(db, query),
        )
    else:
        raise ValueError("Unknown report type")
    if sum(len(sheet.rows) for sheet in sheets.values()) > MAX_ROWS:
        raise AppError(
            "REPORT_TOO_LARGE", "This report exceeds the supported size.", status_code=422
        )
    return sheets


async def _company_sheets(db: TenantSession, company: Company) -> dict[str, SheetData]:
    fields: list[tuple[object, ...]] = [
        ("Name", company.name),
        ("Registered number", company.registered_number),
        ("Organisation type", company.type_of_organisation),
        ("Contact email", company.contact_email),
        ("Contact phone", company.contact_phone),
        ("Website", company.website),
        ("Country", company.country),
        ("Region", company.region),
        ("Time zone", company.timezone),
        ("Currency", company.default_currency),
        ("Week starts on", company.week_starts_on),
        ("Leave year starts", company.leave_year_start_month_day),
        ("Allow negative leave balance", company.allow_negative_leave_balance),
        ("Bank holidays non-working", company.bank_holidays_non_working),
        ("Bank holiday region", company.bank_holiday_region),
    ]
    return {
        "Company": SheetData(("Field", "Value"), fields),
        "Locations and addresses": SheetData(
            (
                "Location",
                "Address line 1",
                "Address line 2",
                "Address line 3",
                "City",
                "County",
                "Postcode",
                "Country",
                "Default",
                "Archived at",
            ),
            await _rows(
                db,
                select(
                    Location.name,
                    Location.address_line1,
                    Location.address_line2,
                    Location.address_line3,
                    Location.city,
                    Location.county,
                    Location.postcode,
                    Location.country,
                    Location.is_default,
                    Location.archived_at,
                ).order_by(Location.name, Location.id),
            ),
        ),
        "Departments": SheetData(
            ("Department", "Archived at"),
            await _rows(
                db,
                select(Department.name, Department.archived_at).order_by(
                    Department.name, Department.id
                ),
            ),
        ),
        "Key personnel": SheetData(
            ("Role", "First name", "Last name", "Designation", "Email", "Phone", "Archived at"),
            await _rows(
                db,
                select(
                    KeyPerson.role,
                    KeyPerson.first_name,
                    KeyPerson.last_name,
                    KeyPerson.designation,
                    KeyPerson.email,
                    KeyPerson.phone,
                    KeyPerson.archived_at,
                ).order_by(KeyPerson.role, KeyPerson.id),
            ),
        ),
        "Trading hours": SheetData(
            ("Weekday", "Open", "Opens at", "Closes at"),
            await _rows(
                db,
                select(
                    TradingHoursDay.weekday,
                    TradingHoursDay.is_open,
                    TradingHoursDay.opens_at,
                    TradingHoursDay.closes_at,
                ).order_by(TradingHoursDay.weekday),
            ),
        ),
        "Compliance documents": SheetData(
            ("Document type", "File name", "Expires on", "Archived at"),
            await _rows(
                db,
                select(
                    ComplianceDocument.doc_type,
                    File.original_name,
                    ComplianceDocument.expires_on,
                    ComplianceDocument.archived_at,
                )
                .join(File, File.id == ComplianceDocument.file_id)
                .order_by(ComplianceDocument.doc_type, ComplianceDocument.created_at),
            ),
        ),
    }
