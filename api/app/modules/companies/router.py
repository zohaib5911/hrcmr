"""The company's own details (plan.md 8.15): ``/company``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, Request, Response, UploadFile
from sqlalchemy import func, select

from app.core.errors import AppError, NotFoundError
from app.integrations.companies_house import CompaniesHouse, CompaniesHouseError, normalise_number
from app.modules.companies.models import (
    Company,
    ComplianceDocument,
    Department,
    Designation,
    KeyPerson,
    Location,
)
from app.modules.companies.reference import (
    BANK_HOLIDAY_REGION_LABELS,
    LEGAL_STRUCTURES,
    SECTORS,
    TRADING_PERIODS,
)
from app.modules.companies.schemas import (
    AddressOut,
    CompaniesHouseRecord,
    CompanyDetails,
    CompanyOptions,
    CompanyOverview,
    CompanyUpdate,
    Features,
    Option,
)
from app.modules.files.models import File
from app.modules.identity.models import Membership
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from app.modules.files.service import FileService

router = APIRouter(tags=["company"])

LOGO_KINDS = frozenset({"jpg", "png"})
LOGO_MAX_BYTES = 2 * 1024 * 1024
# What an audit event may say about each field (never the logo's bytes, only that it changed).
_FIELDS = tuple(CompanyUpdate.model_fields)


def _details(company: Company) -> CompanyDetails:
    return CompanyDetails(
        id=company.id,
        name=company.name,
        trading_name=company.trading_name,
        registered_number=company.registered_number,
        type_of_organisation=company.type_of_organisation,
        trading_period=company.trading_period,
        sector=company.sector,
        contact_email=company.contact_email,
        contact_phone=company.contact_phone,
        website=company.website,
        has_logo=company.logo_file_id is not None,
        bank_holiday_region=company.bank_holiday_region,  # type: ignore[arg-type]
        timezone=company.timezone,
        changed_name_last_5_years=company.changed_name_last_5_years,
        previous_company_name=company.previous_company_name,
        penalty_illegal_working_last_3_years=company.penalty_illegal_working_last_3_years,
        penalty_illegal_working_status=company.penalty_illegal_working_status,
        ai_features_enabled=company.ai_features_enabled,
        status=company.status,  # type: ignore[arg-type]
        plan=company.plan,  # type: ignore[arg-type]
    )


def _features(request: Request) -> Features:
    return Features(
        companies_house_lookup=request.app.state.companies_house is not None,
        ai=request.app.state.settings.anthropic_api_key is not None,
    )


async def _company(access: Access) -> Company:
    company = (
        await access.db.execute(select(Company).where(Company.id == access.company_id))
    ).scalar_one_or_none()
    if company is None:
        raise NotFoundError
    return company


def _snapshot(company: Company) -> dict[str, object]:
    return {name: getattr(company, name) for name in _FIELDS}


@router.get("/company", summary="The company's details")
async def get_company(
    request: Request, access: Annotated[Access, Depends(require("company.overview.read"))]
) -> CompanyOverview:
    company = await _company(access)
    users = (
        await access.db.execute(
            select(func.count())
            .select_from(Membership)
            .where(Membership.company_id == access.company_id, Membership.status == "active")
        )
    ).scalar_one()

    async def count(model: type[Location] | type[Department] | type[Designation]) -> int:
        return (
            await access.db.execute(
                select(func.count()).select_from(model).where(model.archived_at.is_(None))
            )
        ).scalar_one()

    return CompanyOverview(
        company=_details(company),
        features=_features(request),
        users=users,
        locations=await count(Location),
        departments=await count(Department),
        designations=await count(Designation),
        compliance_documents=(
            await access.db.execute(
                select(func.count())
                .select_from(ComplianceDocument)
                .where(ComplianceDocument.archived_at.is_(None))
            )
        ).scalar_one(),
        key_personnel_roles=(
            await access.db.execute(
                select(func.count(KeyPerson.role.distinct())).where(KeyPerson.archived_at.is_(None))
            )
        ).scalar_one(),
    )


@router.patch("/company", summary="Change the company's details")
async def update_company(
    body: CompanyUpdate,
    access: Annotated[Access, Depends(require("company.profile.write"))],
) -> CompanyDetails:
    company = await _company(access)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise AppError("VALIDATION_ERROR", "A company needs a name.", status_code=422, field="name")
    before = _snapshot(company)
    for name, value in changes.items():
        setattr(company, name, value)
    # A "no" answer clears what only a "yes" needs.
    if company.changed_name_last_5_years is False:
        company.previous_company_name = None
    if company.penalty_illegal_working_last_3_years is False:
        company.penalty_illegal_working_status = None
    after = _snapshot(company)
    if before != after:
        await access.audit(
            "company.updated",
            entity_type="company",
            entity_id=company.id,
            before=before,
            after=after,
        )
    await access.db.commit()
    return _details(company)


@router.get("/company/options", summary="The lists the details are chosen from")
async def company_options(
    _: Annotated[Access, Depends(require("company.profile.read"))],
) -> CompanyOptions:
    def options(values: dict[str, str]) -> list[Option]:
        return [Option(value=value, label=label) for value, label in values.items()]

    return CompanyOptions(
        legal_structures=options(LEGAL_STRUCTURES),
        trading_periods=options(TRADING_PERIODS),
        sectors=options(SECTORS),
        bank_holiday_regions=options(BANK_HOLIDAY_REGION_LABELS),
        timezones=sorted(zone for zone in available_timezones() if "/" in zone or zone == "UTC"),
    )


@router.get("/company/companies-house/{number}", summary="Look a company up at Companies House")
async def companies_house_lookup(
    number: str,
    request: Request,
    _: Annotated[Access, Depends(require("company.profile.write"))],
) -> CompaniesHouseRecord:
    service: CompaniesHouse | None = request.app.state.companies_house
    if service is None:
        raise AppError("FEATURE_UNAVAILABLE", "Company lookup is not switched on.", status_code=404)
    normal = normalise_number(number)
    if normal is None:
        raise AppError(
            "VALIDATION_ERROR",
            "A Companies House number is 8 letters or digits, such as 01234567.",
            status_code=422,
            field="number",
        )
    try:
        found = await service.lookup(normal)
    except CompaniesHouseError as exc:
        if not exc.found:
            raise AppError(
                "NOT_FOUND", "Companies House has no company with that number.", status_code=404
            ) from None
        raise AppError(
            "SERVICE_UNAVAILABLE",
            "We could not reach Companies House just now. Try again soon.",
            status_code=503,
        ) from None
    return CompaniesHouseRecord(
        number=found.number,
        name=found.name,
        status=found.status,
        legal_structure=found.legal_structure,
        address=AddressOut(
            line1=found.address.line1,
            line2=found.address.line2,
            city=found.address.city,
            county=found.address.county,
            postcode=found.address.postcode,
            country=found.address.country,
        ),
    )


def _files(request: Request) -> FileService:
    service: FileService = request.app.state.files
    return service


@router.post("/company/logo", status_code=204, summary="Upload the company logo")
async def upload_logo(
    request: Request,
    file: UploadFile,
    access: Annotated[Access, Depends(require("company.profile.write"))],
) -> None:
    company = await _company(access)
    record = await _files(request).upload(
        access,
        file.file,
        filename=file.filename,
        owner_type="company",
        owner_id=access.company_id,
        category="logo",
        kinds=LOGO_KINDS,
        max_bytes=LOGO_MAX_BYTES,
        commit=False,
    )
    before = company.logo_file_id
    company.logo_file_id = record.id
    await access.audit(
        "company.logo_changed",
        entity_type="company",
        entity_id=company.id,
        before={"logo_file_id": before},
        after={"logo_file_id": record.id},
    )
    await access.db.commit()


@router.delete("/company/logo", status_code=204, summary="Remove the company logo")
async def remove_logo(access: Annotated[Access, Depends(require("company.profile.write"))]) -> None:
    company = await _company(access)
    if company.logo_file_id is None:
        return
    before = company.logo_file_id
    company.logo_file_id = None
    await access.audit(
        "company.logo_removed",
        entity_type="company",
        entity_id=company.id,
        before={"logo_file_id": before},
    )
    await access.db.commit()


@router.get(
    "/company/logo",
    summary="The company logo",
    response_class=Response,
    responses={200: {"content": {"image/png": {}, "image/jpeg": {}}}},
)
async def get_logo(
    request: Request, access: Annotated[Access, Depends(require("company.overview.read"))]
) -> Response:
    company = await _company(access)
    service = _files(request)
    if company.logo_file_id is None or service.storage is None:
        raise NotFoundError
    record = (
        await access.db.execute(select(File).where(File.id == company.logo_file_id))
    ).scalar_one_or_none()
    if record is None or record.scan_status != "clean":
        raise NotFoundError
    body = await service.storage.read(record.storage_key)
    return Response(
        content=body,
        media_type=record.mime,
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )
