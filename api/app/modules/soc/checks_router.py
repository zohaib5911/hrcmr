"""Saved sponsorship checks: create a draft, list, read, confirm and report (plan 8.17, T15.6).

A draft is one rules check for the code the user picked. Confirming the code is the step that makes
the PDF report available, and nothing is written to a posting or a designation here.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (FastAPI reads the path parameter type at runtime)
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field, StringConstraints, TypeAdapter
from sqlalchemy import select

from app.core.errors import AppError, NotFoundError
from app.core.schemas import RequestModel
from app.modules.rbac.deps import Access, require
from app.modules.soc import checks as service
from app.modules.soc.models import SocCheck, SocUnitGroup
from app.modules.soc.report import report_pdf
from app.modules.soc.router import ZONE, SocCheckIn, Title, check_input
from app.modules.soc_rules.engine import CheckResult, evaluate
from app.modules.soc_rules.loader import NoRulesVersionError, load_rules_data

router = APIRouter(tags=["soc"])
Runner = Annotated[Access, Depends(require("soc.check.run"))]
Reader = Annotated[Access, Depends(require("soc.check.read"))]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


class SocCheckCreateIn(RequestModel):
    job_title: Title
    job_description: Notes = ""
    soc_code: str = Field(pattern=r"^[1-9][0-9]{3}$")
    check: SocCheckIn


class SocCheckSummaryOut(BaseModel):
    id: str
    status: str  # draft | confirmed
    job_title: str
    soc_code: str
    soc_title: str
    eligibility: str  # the eligibility chip's label
    verdict_meets: bool | None  # null when a band or role is still needed
    rules_version_name: str
    rules_effective_from: date
    created_at: datetime
    confirmed_at: datetime | None


class SocCheckOut(SocCheckSummaryOut):
    job_description: str
    inputs: dict[str, Any]
    result: CheckResult


class SocCheckListOut(BaseModel):
    items: list[SocCheckSummaryOut]


def _summary_fields(row: SocCheck) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "status": row.status,
        "job_title": row.job_title,
        "soc_code": row.soc_code,
        "soc_title": row.soc_title,
        "eligibility": str(row.result["eligibility"]["label"]),
        "verdict_meets": row.result["verdict"]["meets"],
        "rules_version_name": row.rules_version_name,
        "rules_effective_from": row.rules_effective_from,
        "created_at": row.created_at,
        "confirmed_at": row.confirmed_at,
    }


def _detail(row: SocCheck) -> SocCheckOut:
    result = TypeAdapter(CheckResult).validate_python(row.result)
    return SocCheckOut(
        **_summary_fields(row),
        job_description=row.job_description,
        inputs=row.inputs,
        result=result,
    )


async def _find(access: Access, check_id: uuid.UUID) -> SocCheck:
    row = await access.db.get(SocCheck, check_id)
    if row is None:  # another company's check looks the same as a missing one
        raise NotFoundError("We could not find that check.")
    return row


@router.post("/soc/checks", response_model=SocCheckOut)
async def create_check(body: SocCheckCreateIn, access: Runner) -> SocCheckOut:
    """Saves a draft: the rules engine's answer for this code, on the live rules version."""
    try:
        rules = await load_rules_data(access.db)
    except NoRulesVersionError as exc:
        raise AppError(
            "RULES_NOT_PUBLISHED", "The SOC rules have not been published yet.", status_code=409
        ) from exc
    found = (
        await access.db.execute(select(SocUnitGroup.code).where(SocUnitGroup.code == body.soc_code))
    ).scalar_one_or_none()
    if found is None:
        raise NotFoundError("We could not find that SOC code.")
    today = datetime.now(ZONE).date()
    try:
        result = evaluate(rules, check_input(body.check, body.soc_code, today))
    except ValueError as exc:
        raise AppError(
            "CHECK_NOT_VALID", f"This check cannot be assessed: {exc}", status_code=422
        ) from exc
    # The date the check used is stored, so a draft made today still shows the same date later.
    inputs = body.check.model_dump(mode="json") | {
        "cos_assignment_date": (body.check.cos_assignment_date or today).isoformat()
    }
    row = await service.create_draft(
        access.db,
        company_id=access.company_id,
        user_id=access.caller.user_id,
        job_title=body.job_title,
        job_description=body.job_description,
        soc_code=body.soc_code,
        inputs=inputs,
        rules=rules,
        result=result,
    )
    await access.audit(
        "soc.check.drafted",
        entity_type="soc_check",
        entity_id=row.id,
        after={"soc_code": row.soc_code, "rules_version": row.rules_version_name},
    )
    await access.db.commit()
    return _detail(row)


@router.get("/soc/checks", response_model=SocCheckListOut)
async def list_checks(access: Reader) -> SocCheckListOut:
    rows = await service.history(access.db)
    return SocCheckListOut(items=[SocCheckSummaryOut(**_summary_fields(row)) for row in rows])


@router.get("/soc/checks/{check_id}", response_model=SocCheckOut)
async def read_check(check_id: uuid.UUID, access: Reader) -> SocCheckOut:
    return _detail(await _find(access, check_id))


@router.post("/soc/checks/{check_id}/confirm", response_model=SocCheckOut)
async def confirm_check(check_id: uuid.UUID, access: Runner) -> SocCheckOut:
    row = await service.confirm(access.db, await _find(access, check_id), access.caller.user_id)
    await access.audit(
        "soc.check.confirmed",
        entity_type="soc_check",
        entity_id=row.id,
        after={"soc_code": row.soc_code},
    )
    await access.db.commit()
    return _detail(row)


@router.get("/soc/checks/{check_id}/report.pdf", response_class=Response)
async def check_report(check_id: uuid.UUID, access: Reader) -> Response:
    row = await _find(access, check_id)
    if row.status != "confirmed":
        raise AppError(
            "CHECK_NOT_CONFIRMED",
            "Confirm the code before the report is made.",
            status_code=409,
        )
    pdf = await report_pdf(row)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="soc-check-{row.soc_code}.pdf"'},
    )
