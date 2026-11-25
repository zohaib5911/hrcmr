"""Pay settings (plan.md 8.15): bank accounts, tax codes, payment types, pay bands and pay
schedules. Each can be listed, added, changed and archived; every change is audited. Bank account
numbers are stored encrypted and only ever leave the API masked."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.errors import AppError, ConflictError, NotFoundError
from app.modules.pay.models import BankAccount, PayBand, PaymentType, PaySchedule, TaxCode
from app.modules.pay.schemas import (
    BankAccountIn,
    BankAccountOut,
    BankAccountPatch,
    PayBandIn,
    PayBandOut,
    PaymentTypeIn,
    PaymentTypeOut,
    PayScheduleIn,
    PayScheduleOut,
    TaxCodeIn,
    TaxCodeOut,
)
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from sqlalchemy.orm import InstrumentedAttribute

router = APIRouter(tags=["pay"])

BankReads = Annotated[Access, Depends(require("company.profile.read"))]
BankWrites = Annotated[Access, Depends(require("company.profile.write"))]
TaxReads = Annotated[Access, Depends(require("settings.tax_code.read"))]
TaxWrites = Annotated[Access, Depends(require("settings.tax_code.write"))]
TypeReads = Annotated[Access, Depends(require("settings.payment_type.read"))]
TypeWrites = Annotated[Access, Depends(require("settings.payment_type.write"))]
BandReads = Annotated[Access, Depends(require("settings.pay_band.read"))]
BandWrites = Annotated[Access, Depends(require("settings.pay_band.write"))]
ScheduleReads = Annotated[Access, Depends(require("settings.pay_schedule.read"))]
ScheduleWrites = Annotated[Access, Depends(require("settings.pay_schedule.write"))]


def _now() -> datetime:
    return datetime.now(UTC)


async def _live(access: Access, model: Any, row_id: uuid.UUID) -> Any:
    row = (
        await access.db.execute(
            select(model).where(model.id == row_id, model.archived_at.is_(None))
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


async def _free(
    access: Access,
    model: Any,
    column: InstrumentedAttribute[str],
    value: str,
    field: str,
    *,
    except_id: uuid.UUID | None = None,
) -> None:
    query = select(model.id).where(func.lower(column) == value.lower(), model.archived_at.is_(None))
    if except_id:
        query = query.where(model.id != except_id)
    if (await access.db.execute(query)).first() is not None:
        raise ConflictError(f"That {field} is already in use.", field=field)


def _q(value: Decimal) -> Decimal:
    """Two decimal places, as the database will hold it, even before the row is read back."""
    return value.quantize(Decimal("0.01"))


def _money(value: Decimal) -> str:
    return f"{_q(value)}"


# --- bank accounts -------------------------------------------------------------------------------


def _bank_out(row: BankAccount) -> BankAccountOut:
    return BankAccountOut(
        id=row.id,
        label=row.label,
        bank_name=row.bank_name,
        account_holder=row.account_holder,
        sort_code_masked=f"••-••-{row.sort_code[-2:]}",
        account_number_masked=f"••••{row.account_number[-4:]}",
        is_primary=row.is_primary,
    )


def _bank_audit(row: BankAccount) -> dict[str, object]:
    """Never the numbers themselves, not even in the audit trail."""
    out = _bank_out(row)
    return {
        "label": out.label,
        "bank_name": out.bank_name,
        "account_holder": out.account_holder,
        "sort_code": out.sort_code_masked,
        "account_number": out.account_number_masked,
        "is_primary": out.is_primary,
    }


async def _make_only_primary(access: Access, keep: uuid.UUID) -> None:
    others = (
        await access.db.execute(
            select(BankAccount).where(
                BankAccount.is_primary.is_(True),
                BankAccount.archived_at.is_(None),
                BankAccount.id != keep,
            )
        )
    ).scalars()
    for other in others:
        other.is_primary = False


@router.get("/bank-accounts", summary="The company's bank accounts, masked")
async def list_bank_accounts(access: BankReads) -> list[BankAccountOut]:
    rows = (
        await access.db.execute(
            select(BankAccount)
            .where(BankAccount.archived_at.is_(None))
            .order_by(BankAccount.is_primary.desc(), func.lower(BankAccount.label))
        )
    ).scalars()
    return [_bank_out(row) for row in rows]


@router.post("/bank-accounts", status_code=201, summary="Add a bank account")
async def create_bank_account(body: BankAccountIn, access: BankWrites) -> BankAccountOut:
    await _free(
        access,
        BankAccount,
        BankAccount.label,
        body.label,
        "label",
    )
    first = (
        await access.db.execute(
            select(func.count()).select_from(BankAccount).where(BankAccount.archived_at.is_(None))
        )
    ).scalar_one() == 0
    row = BankAccount(
        company_id=access.company_id,
        **body.model_dump(exclude={"is_primary"}),
        is_primary=body.is_primary or first,
    )
    access.db.add(row)
    await access.db.flush()
    if row.is_primary:
        await _make_only_primary(access, row.id)
    await access.audit(
        "bank_account.created",
        entity_type="bank_account",
        entity_id=row.id,
        after=_bank_audit(row),
    )
    await access.db.commit()
    return _bank_out(row)


@router.patch("/bank-accounts/{account_id}", summary="Change a bank account")
async def update_bank_account(
    account_id: uuid.UUID, body: BankAccountPatch, access: BankWrites
) -> BankAccountOut:
    row: BankAccount = await _live(access, BankAccount, account_id)
    changes = body.model_dump(exclude_unset=True)
    if any(
        changes.get(name, "x") is None
        for name in ("label", "bank_name", "account_holder", "sort_code", "account_number")
    ):
        raise AppError("VALIDATION_ERROR", "That cannot be empty.", status_code=422)
    if changes.get("is_primary") is False and row.is_primary:
        raise ConflictError("Choose another account as the main one instead.", field="is_primary")
    if "label" in changes:
        await _free(
            access,
            BankAccount,
            BankAccount.label,
            changes["label"],
            "label",
            except_id=row.id,
        )
    # Compare the real values before masking (ISS-07): a new account number that keeps the same
    # last four digits must still be audited. Only the field names go in the trail.
    changed = [name for name, value in changes.items() if getattr(row, name) != value]
    before = _bank_audit(row)
    for name, value in changes.items():
        setattr(row, name, value)
    if changes.get("is_primary"):
        await _make_only_primary(access, row.id)
    if changed:
        await access.audit(
            "bank_account.updated",
            entity_type="bank_account",
            entity_id=row.id,
            before=before,
            after=_bank_audit(row),
            summary=f"Changed: {', '.join(changed)}",
        )
    await access.db.commit()
    return _bank_out(row)


@router.delete("/bank-accounts/{account_id}", status_code=204, summary="Archive a bank account")
async def archive_bank_account(account_id: uuid.UUID, access: BankWrites) -> None:
    row: BankAccount = await _live(access, BankAccount, account_id)
    others = (
        await access.db.execute(
            select(func.count())
            .select_from(BankAccount)
            .where(BankAccount.archived_at.is_(None), BankAccount.id != row.id)
        )
    ).scalar_one()
    if row.is_primary and others:
        raise ConflictError("Choose another account as the main one first.")
    row.archived_at = _now()
    row.is_primary = False
    await access.audit(
        "bank_account.archived", entity_type="bank_account", entity_id=row.id, summary=row.label
    )
    await access.db.commit()


# --- tax codes -----------------------------------------------------------------------------------


def _tax_out(row: TaxCode) -> TaxCodeOut:
    return TaxCodeOut(
        id=row.id,
        code=row.code,
        reference=row.reference,
        deduction_percentage=_q(row.deduction_percentage),
    )


def _tax_json(row: TaxCode) -> dict[str, object]:
    return {
        "code": row.code,
        "reference": row.reference,
        "deduction_percentage": _money(row.deduction_percentage),
    }


@router.get("/tax-codes", summary="Tax codes")
async def list_tax_codes(access: TaxReads) -> list[TaxCodeOut]:
    rows = (
        await access.db.execute(
            select(TaxCode).where(TaxCode.archived_at.is_(None)).order_by(func.lower(TaxCode.code))
        )
    ).scalars()
    return [_tax_out(row) for row in rows]


@router.post("/tax-codes", status_code=201, summary="Add a tax code")
async def create_tax_code(body: TaxCodeIn, access: TaxWrites) -> TaxCodeOut:
    await _free(access, TaxCode, TaxCode.code, body.code, "code")
    row = TaxCode(company_id=access.company_id, **body.model_dump())
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "tax_code.created", entity_type="tax_code", entity_id=row.id, after=_tax_json(row)
    )
    await access.db.commit()
    return _tax_out(row)


@router.put("/tax-codes/{tax_code_id}", summary="Change a tax code")
async def update_tax_code(tax_code_id: uuid.UUID, body: TaxCodeIn, access: TaxWrites) -> TaxCodeOut:
    row: TaxCode = await _live(access, TaxCode, tax_code_id)
    await _free(
        access,
        TaxCode,
        TaxCode.code,
        body.code,
        "code",
        except_id=row.id,
    )
    before = _tax_json(row)
    row.code, row.reference, row.deduction_percentage = (
        body.code,
        body.reference,
        body.deduction_percentage,
    )
    if before != _tax_json(row):
        await access.audit(
            "tax_code.updated",
            entity_type="tax_code",
            entity_id=row.id,
            before=before,
            after=_tax_json(row),
        )
    await access.db.commit()
    return _tax_out(row)


@router.delete("/tax-codes/{tax_code_id}", status_code=204, summary="Archive a tax code")
async def archive_tax_code(tax_code_id: uuid.UUID, access: TaxWrites) -> None:
    row: TaxCode = await _live(access, TaxCode, tax_code_id)
    row.archived_at = _now()
    await access.audit(
        "tax_code.archived", entity_type="tax_code", entity_id=row.id, summary=row.code
    )
    await access.db.commit()


# --- payment types -------------------------------------------------------------------------------


def _type_out(row: PaymentType) -> PaymentTypeOut:
    return PaymentTypeOut(id=row.id, name=row.name, min_hourly_rate=_q(row.min_hourly_rate))


def _type_json(row: PaymentType) -> dict[str, object]:
    return {"name": row.name, "min_hourly_rate": _money(row.min_hourly_rate)}


@router.get("/payment-types", summary="Payment types")
async def list_payment_types(access: TypeReads) -> list[PaymentTypeOut]:
    rows = (
        await access.db.execute(
            select(PaymentType)
            .where(PaymentType.archived_at.is_(None))
            .order_by(func.lower(PaymentType.name))
        )
    ).scalars()
    return [_type_out(row) for row in rows]


@router.post("/payment-types", status_code=201, summary="Add a payment type")
async def create_payment_type(body: PaymentTypeIn, access: TypeWrites) -> PaymentTypeOut:
    await _free(
        access,
        PaymentType,
        PaymentType.name,
        body.name,
        "name",
    )
    row = PaymentType(company_id=access.company_id, **body.model_dump())
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "payment_type.created", entity_type="payment_type", entity_id=row.id, after=_type_json(row)
    )
    await access.db.commit()
    return _type_out(row)


@router.put("/payment-types/{type_id}", summary="Change a payment type")
async def update_payment_type(
    type_id: uuid.UUID, body: PaymentTypeIn, access: TypeWrites
) -> PaymentTypeOut:
    row: PaymentType = await _live(access, PaymentType, type_id)
    await _free(
        access,
        PaymentType,
        PaymentType.name,
        body.name,
        "name",
        except_id=row.id,
    )
    before = _type_json(row)
    row.name, row.min_hourly_rate = body.name, body.min_hourly_rate
    if before != _type_json(row):
        await access.audit(
            "payment_type.updated",
            entity_type="payment_type",
            entity_id=row.id,
            before=before,
            after=_type_json(row),
        )
    await access.db.commit()
    return _type_out(row)


@router.delete("/payment-types/{type_id}", status_code=204, summary="Archive a payment type")
async def archive_payment_type(type_id: uuid.UUID, access: TypeWrites) -> None:
    row: PaymentType = await _live(access, PaymentType, type_id)
    row.archived_at = _now()
    await access.audit(
        "payment_type.archived", entity_type="payment_type", entity_id=row.id, summary=row.name
    )
    await access.db.commit()


# --- pay bands -----------------------------------------------------------------------------------


def _band_out(row: PayBand) -> PayBandOut:
    return PayBandOut(
        id=row.id,
        name=row.name,
        min_annual=_q(row.min_annual),
        max_annual=_q(row.max_annual),
        currency=row.currency,
    )


def _band_json(row: PayBand) -> dict[str, object]:
    return {
        "name": row.name,
        "min_annual": _money(row.min_annual),
        "max_annual": _money(row.max_annual),
        "currency": row.currency,
    }


@router.get("/pay-bands", summary="Pay bands")
async def list_pay_bands(access: BandReads) -> list[PayBandOut]:
    rows = (
        await access.db.execute(
            select(PayBand)
            .where(PayBand.archived_at.is_(None))
            .order_by(PayBand.min_annual, func.lower(PayBand.name))
        )
    ).scalars()
    return [_band_out(row) for row in rows]


@router.post("/pay-bands", status_code=201, summary="Add a pay band")
async def create_pay_band(body: PayBandIn, access: BandWrites) -> PayBandOut:
    await _free(
        access,
        PayBand,
        PayBand.name,
        body.name,
        "name",
    )
    row = PayBand(company_id=access.company_id, **body.model_dump())
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "pay_band.created", entity_type="pay_band", entity_id=row.id, after=_band_json(row)
    )
    await access.db.commit()
    return _band_out(row)


@router.put("/pay-bands/{band_id}", summary="Change a pay band")
async def update_pay_band(band_id: uuid.UUID, body: PayBandIn, access: BandWrites) -> PayBandOut:
    row: PayBand = await _live(access, PayBand, band_id)
    await _free(
        access,
        PayBand,
        PayBand.name,
        body.name,
        "name",
        except_id=row.id,
    )
    before = _band_json(row)
    row.name, row.min_annual, row.max_annual, row.currency = (
        body.name,
        body.min_annual,
        body.max_annual,
        body.currency,
    )
    if before != _band_json(row):
        await access.audit(
            "pay_band.updated",
            entity_type="pay_band",
            entity_id=row.id,
            before=before,
            after=_band_json(row),
        )
    await access.db.commit()
    return _band_out(row)


@router.delete("/pay-bands/{band_id}", status_code=204, summary="Archive a pay band")
async def archive_pay_band(band_id: uuid.UUID, access: BandWrites) -> None:
    row: PayBand = await _live(access, PayBand, band_id)
    row.archived_at = _now()
    await access.audit(
        "pay_band.archived", entity_type="pay_band", entity_id=row.id, summary=row.name
    )
    await access.db.commit()


# --- pay schedules -------------------------------------------------------------------------------


def _schedule_out(row: PaySchedule) -> PayScheduleOut:
    return PayScheduleOut(
        id=row.id,
        name=row.name,
        frequency=row.frequency,  # type: ignore[arg-type]
        pay_day_kind=row.pay_day_kind,  # type: ignore[arg-type]
        pay_day_value=row.pay_day_value,
    )


def _schedule_json(row: PaySchedule) -> dict[str, object]:
    return {
        "name": row.name,
        "frequency": row.frequency,
        "pay_day_kind": row.pay_day_kind,
        "pay_day_value": row.pay_day_value,
    }


@router.get("/pay-schedules", summary="Pay schedules")
async def list_pay_schedules(access: ScheduleReads) -> list[PayScheduleOut]:
    rows = (
        await access.db.execute(
            select(PaySchedule)
            .where(PaySchedule.archived_at.is_(None))
            .order_by(func.lower(PaySchedule.name))
        )
    ).scalars()
    return [_schedule_out(row) for row in rows]


@router.post("/pay-schedules", status_code=201, summary="Add a pay schedule")
async def create_pay_schedule(body: PayScheduleIn, access: ScheduleWrites) -> PayScheduleOut:
    await _free(
        access,
        PaySchedule,
        PaySchedule.name,
        body.name,
        "name",
    )
    row = PaySchedule(company_id=access.company_id, **body.model_dump())
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "pay_schedule.created",
        entity_type="pay_schedule",
        entity_id=row.id,
        after=_schedule_json(row),
    )
    await access.db.commit()
    return _schedule_out(row)


@router.put("/pay-schedules/{schedule_id}", summary="Change a pay schedule")
async def update_pay_schedule(
    schedule_id: uuid.UUID, body: PayScheduleIn, access: ScheduleWrites
) -> PayScheduleOut:
    row: PaySchedule = await _live(access, PaySchedule, schedule_id)
    await _free(
        access,
        PaySchedule,
        PaySchedule.name,
        body.name,
        "name",
        except_id=row.id,
    )
    before = _schedule_json(row)
    row.name, row.frequency, row.pay_day_kind, row.pay_day_value = (
        body.name,
        body.frequency,
        body.pay_day_kind,
        body.pay_day_value,
    )
    if before != _schedule_json(row):
        await access.audit(
            "pay_schedule.updated",
            entity_type="pay_schedule",
            entity_id=row.id,
            before=before,
            after=_schedule_json(row),
        )
    await access.db.commit()
    return _schedule_out(row)


@router.delete("/pay-schedules/{schedule_id}", status_code=204, summary="Archive a pay schedule")
async def archive_pay_schedule(schedule_id: uuid.UUID, access: ScheduleWrites) -> None:
    row: PaySchedule = await _live(access, PaySchedule, schedule_id)
    row.archived_at = _now()
    await access.audit(
        "pay_schedule.archived", entity_type="pay_schedule", entity_id=row.id, summary=row.name
    )
    await access.db.commit()
