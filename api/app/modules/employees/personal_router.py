"""The Personal tab (plan 8.3): details, address, emergency contacts, identity and bank.

National Insurance, passport and bank details are shown masked. Showing them in full needs the
caller to have confirmed their password or a code in the last 10 minutes, and every reveal is
audited. The audit trail never holds the values themselves.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (FastAPI reads the annotations at run time)
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update

from app.core.crypto import blind_index, mask_tail
from app.core.errors import ConflictError, NotFoundError
from app.core.rbac_matrix import Scope, scope_for
from app.modules.auth.sessions import require_step_up
from app.modules.companies.structure_router import postcode_town
from app.modules.companies.structure_schemas import PostcodeOut  # noqa: TC001  (FastAPI reads it)
from app.modules.employees.models import (
    EmergencyContact,
    Employee,
    EmployeeAddress,
    EmployeeBankDetail,
)
from app.modules.employees.personal_schemas import (
    AddressIn,
    AddressOut,
    BankIn,
    BankMasked,
    BankRevealed,
    ContactIn,
    ContactOut,
    IdentityIn,
    IdentityMasked,
    IdentityRevealed,
    PersonalDetails,
    PersonalDetailsIn,
    PersonalTab,
    Revealed,
    RevealIn,
)
from app.modules.employees.router import _employee as reachable_employee
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["employees"])

Reads = Annotated[Access, Depends(require("employee.profile.read"))]
Writes = Annotated[Access, Depends(require("employee.profile.write"))]
SeesSensitive = Annotated[Access, Depends(require("employee.sensitive_data.read"))]
EditsSensitive = Annotated[Access, Depends(require("employee.sensitive_data.write"))]


def _ni_display(value: str) -> str:
    return f"{value[:2]} {value[2:4]} {value[4:6]} {value[6:8]} {value[8:]}"


async def _may_see_sensitive(access: Access, employee_id: uuid.UUID) -> bool:
    scope = scope_for(access.role, "employee.sensitive_data.read")
    if scope is None:
        return False
    if scope is Scope.ALL or access.employee_id == employee_id:
        return True
    return (
        scope is Scope.REPORTS
        and access.employee_id is not None
        and await access.reports.is_report(access.employee_id, employee_id, "reporting")
    )


def _details(e: Employee) -> PersonalDetails:
    return PersonalDetails(
        first_name=e.first_name,
        last_name=e.last_name,
        email=e.email,
        phone=e.phone,
        alt_phone=e.alt_phone,
        date_of_birth=e.date_of_birth,
        gender=e.gender or "not_specified",  # type: ignore[arg-type]
        marital_status=e.marital_status or "not_specified",  # type: ignore[arg-type]
        nationality=e.nationality,
    )


def _address(a: EmployeeAddress) -> AddressOut:
    return AddressOut(
        postcode=a.postcode,
        line1=a.line1,
        line2=a.line2,
        line3=a.line3,
        city_county=a.city_county,
        country=a.country,
    )


def _contact(c: EmergencyContact) -> ContactOut:
    return ContactOut(
        id=c.id,
        name=c.name,
        relationship=c.relationship,  # type: ignore[arg-type]
        phone=c.phone,
        email=c.email,
        address=c.address,
        details=c.details,
    )


def _identity(e: Employee) -> IdentityMasked:
    return IdentityMasked(
        ni_number=mask_tail(_ni_display(e.ni_number)) if e.ni_number else None,
        passport_number=mask_tail(e.passport_number) if e.passport_number else None,
        passport_country=e.passport_country,
        passport_expiry=e.passport_expiry,
    )


def _bank_masked(b: EmployeeBankDetail) -> BankMasked:
    return BankMasked(
        account_holder=b.account_holder,
        bank_name=b.bank_name,
        sort_code=mask_tail(b.sort_code, 2),
        account_number=mask_tail(b.account_number, 4),
    )


async def _current_address(access: Access, employee_id: uuid.UUID) -> EmployeeAddress | None:
    return (
        await access.db.execute(
            select(EmployeeAddress).where(
                EmployeeAddress.employee_id == employee_id, EmployeeAddress.is_current.is_(True)
            )
        )
    ).scalar_one_or_none()


async def _current_bank(access: Access, employee_id: uuid.UUID) -> EmployeeBankDetail | None:
    return (
        await access.db.execute(
            select(EmployeeBankDetail).where(
                EmployeeBankDetail.employee_id == employee_id,
                EmployeeBankDetail.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()


async def _contacts(access: Access, employee_id: uuid.UUID) -> list[EmergencyContact]:
    rows = await access.db.execute(
        select(EmergencyContact)
        .where(EmergencyContact.employee_id == employee_id)
        .order_by(EmergencyContact.created_at, EmergencyContact.id)
    )
    return list(rows.scalars())


async def _tab(access: Access, employee: Employee) -> PersonalTab:
    address = await _current_address(access, employee.id)
    visible = await _may_see_sensitive(access, employee.id)
    bank = await _current_bank(access, employee.id) if visible else None
    return PersonalTab(
        details=_details(employee),
        address=_address(address) if address else None,
        contacts=[_contact(c) for c in await _contacts(access, employee.id)],
        sensitive_visible=visible,
        identity=_identity(employee) if visible else None,
        bank=_bank_masked(bank) if bank else None,
    )


@router.get("/employees/{employee_id}/personal", response_model=PersonalTab)
async def get_personal(employee_id: uuid.UUID, access: Reads) -> PersonalTab:
    return await _tab(access, await reachable_employee(access, employee_id))


@router.put("/employees/{employee_id}/personal", response_model=PersonalTab)
async def save_personal(
    employee_id: uuid.UUID, body: PersonalDetailsIn, access: Writes
) -> PersonalTab:
    employee = await reachable_employee(access, employee_id)
    before = _details(employee).model_dump(mode="json")
    employee.first_name, employee.last_name = body.first_name, body.last_name
    employee.email = str(body.email).lower()
    employee.phone, employee.alt_phone = body.phone, body.alt_phone
    employee.date_of_birth = body.date_of_birth
    employee.gender = None if body.gender == "not_specified" else body.gender
    employee.marital_status = (
        None if body.marital_status == "not_specified" else body.marital_status
    )
    employee.nationality = body.nationality
    after = _details(employee).model_dump(mode="json")
    if before != after:
        changed = [k for k in after if before[k] != after[k]]
        await access.audit(
            "employee.personal_details_changed",
            entity_type="employee",
            entity_id=employee.id,
            before={k: before[k] for k in changed},
            after={k: after[k] for k in changed},
        )
    await access.db.commit()
    return await _tab(access, employee)


@router.get("/employee-lookups/postcode/{postcode}", summary="Town and county for a postcode")
async def look_up_postcode(postcode: str, request: Request, _: Writes) -> PostcodeOut:
    return await postcode_town(postcode, request)


@router.put("/employees/{employee_id}/address", response_model=AddressOut)
async def save_address(employee_id: uuid.UUID, body: AddressIn, access: Writes) -> AddressOut:
    employee = await reachable_employee(access, employee_id)
    row = await _current_address(access, employee.id)
    before = _address(row).model_dump() if row else None
    if row is None:
        row = EmployeeAddress(company_id=access.company_id, employee_id=employee.id)
        access.db.add(row)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    after = _address(row).model_dump()
    if before != after:
        await access.audit(
            "employee.address_changed",
            entity_type="employee",
            entity_id=employee.id,
            before=before,
            after=after,
        )
    await access.db.commit()
    return _address(row)


async def _contact_row(
    access: Access, employee_id: uuid.UUID, contact_id: uuid.UUID
) -> EmergencyContact:
    row = (
        await access.db.execute(
            select(EmergencyContact).where(
                EmergencyContact.id == contact_id, EmergencyContact.employee_id == employee_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


@router.post("/employees/{employee_id}/contacts", status_code=201, response_model=ContactOut)
async def add_contact(employee_id: uuid.UUID, body: ContactIn, access: Writes) -> ContactOut:
    employee = await reachable_employee(access, employee_id)
    row = EmergencyContact(
        company_id=access.company_id,
        employee_id=employee.id,
        **{**body.model_dump(), "email": str(body.email) if body.email else None},
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "employee.emergency_contact_added",
        entity_type="employee",
        entity_id=employee.id,
        after={"name": row.name, "relationship": row.relationship},
    )
    await access.db.commit()
    return _contact(row)


@router.put("/employees/{employee_id}/contacts/{contact_id}", response_model=ContactOut)
async def change_contact(
    employee_id: uuid.UUID, contact_id: uuid.UUID, body: ContactIn, access: Writes
) -> ContactOut:
    employee = await reachable_employee(access, employee_id)
    row = await _contact_row(access, employee.id, contact_id)
    for key, value in {
        **body.model_dump(),
        "email": str(body.email) if body.email else None,
    }.items():
        setattr(row, key, value)
    await access.audit(
        "employee.emergency_contact_changed",
        entity_type="employee",
        entity_id=employee.id,
        after={"name": row.name, "relationship": row.relationship},
    )
    await access.db.commit()
    return _contact(row)


@router.delete("/employees/{employee_id}/contacts/{contact_id}", status_code=204)
async def remove_contact(employee_id: uuid.UUID, contact_id: uuid.UUID, access: Writes) -> None:
    employee = await reachable_employee(access, employee_id)
    row = await _contact_row(access, employee.id, contact_id)
    await access.audit(
        "employee.emergency_contact_removed",
        entity_type="employee",
        entity_id=employee.id,
        before={"name": row.name, "relationship": row.relationship},
    )
    await access.db.delete(row)
    await access.db.commit()


@router.put("/employees/{employee_id}/identity", response_model=IdentityMasked)
async def save_identity(
    employee_id: uuid.UUID, body: IdentityIn, access: EditsSensitive
) -> IdentityMasked:
    employee = await reachable_employee(access, employee_id)
    if body.ni_number:
        index = blind_index(
            body.ni_number, purpose="employee.ni_number", scope=str(access.company_id)
        )
        clash = (
            await access.db.execute(
                select(Employee.id).where(
                    Employee.ni_number_index == index, Employee.id != employee.id
                )
            )
        ).first()
        if clash is not None:
            raise ConflictError(
                "Another employee already has this National Insurance number.", field="ni_number"
            )
        employee.ni_number_index = index
    else:
        employee.ni_number_index = None
    changed = [
        name
        for name, new in (
            ("ni_number", body.ni_number),
            ("passport_number", body.passport_number),
            ("passport_country", body.passport_country),
            ("passport_expiry", body.passport_expiry),
        )
        if getattr(employee, name) != new
    ]
    employee.ni_number = body.ni_number
    employee.passport_number = body.passport_number
    employee.passport_country = body.passport_country
    employee.passport_expiry = body.passport_expiry
    if changed:
        await access.audit(  # which fields, never the values
            "employee.identity_changed",
            entity_type="employee",
            entity_id=employee.id,
            after={"fields": changed},
        )
    await access.db.commit()
    return _identity(employee)


@router.put("/employees/{employee_id}/bank", response_model=BankMasked)
async def save_bank(employee_id: uuid.UUID, body: BankIn, access: EditsSensitive) -> BankMasked:
    """A new account replaces the current one, which is kept as history."""
    employee = await reachable_employee(access, employee_id)
    await access.db.execute(
        update(EmployeeBankDetail)
        .where(EmployeeBankDetail.employee_id == employee.id, EmployeeBankDetail.is_current)
        .values(is_current=False)
    )
    row = EmployeeBankDetail(
        company_id=access.company_id, employee_id=employee.id, **body.model_dump()
    )
    access.db.add(row)
    await access.audit(
        "employee.bank_details_changed",
        entity_type="employee",
        entity_id=employee.id,
        after={"bank_name": body.bank_name},
    )
    await access.db.commit()
    return _bank_masked(row)


@router.post("/employees/{employee_id}/reveal", response_model=Revealed)
async def reveal(employee_id: uuid.UUID, body: RevealIn, access: SeesSensitive) -> Revealed:
    """Show the full values. Needs a recent password or code check, and is recorded."""
    require_step_up(access.caller.session)
    employee = await reachable_employee(access, employee_id)
    await access.audit(
        "employee.sensitive_revealed",
        entity_type="employee",
        entity_id=employee.id,
        after={"field": body.field},
    )
    if body.field == "identity":
        result = Revealed(
            identity=IdentityRevealed(
                ni_number=_ni_display(employee.ni_number) if employee.ni_number else None,
                passport_number=employee.passport_number,
            )
        )
    else:
        bank = await _current_bank(access, employee.id)
        if bank is None:
            raise NotFoundError
        result = Revealed(
            bank=BankRevealed(sort_code=bank.sort_code, account_number=bank.account_number)
        )
    await access.db.commit()
    return result
