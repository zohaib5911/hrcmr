"""The free public sponsorship checker (plan 8.17, T15.8, R5): a title search and salary table.

No login, no CV and no AI. It reads only the SOC reference tables and the published rules, which
every company shares, so nothing a company holds can be reached from here. A search and a code are
limited per connection. A salary check is limited per connection too, and needs a Turnstile token,
as every public POST does."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal  # noqa: TC003  (pydantic reads the field types at runtime)
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.errors import AppError, NotFoundError
from app.core.rate_limit import RateLimiter
from app.core.schemas import RequestModel
from app.db.session import GlobalDb  # noqa: TC001  (FastAPI reads the dependency at runtime)
from app.modules.auth.deps import client_ip
from app.modules.soc.models import SocUnitGroup
from app.modules.soc.retrieval import CANDIDATES, normalise_title, retrieve
from app.modules.soc.router import ZONE, Nation, SalaryPer, query_embedding
from app.modules.soc_rules.engine import (
    Applicant,
    CheckInput,
    OptionResult,
    Verdict,
    evaluate,
)
from app.modules.soc_rules.loader import NoRulesVersionError, load_rules_data

router = APIRouter(prefix="/public/soc", tags=["public-soc"])
SEARCH_PER_CONNECTION = ("public.soc.search", 60, 60)  # searches and codes, per minute
CHECK_PER_CONNECTION = ("public.soc.check", 10, 3600)  # salary checks, per hour
CODE = Annotated[str, Path(pattern=r"^[1-9][0-9]{3}$")]


class PublicHitOut(BaseModel):
    code: str
    title: str


class PublicSearchOut(BaseModel):
    results: list[PublicHitOut]


class PublicCodeOut(BaseModel):
    code: str
    title: str
    description: str
    tasks: list[str]
    typical_titles: list[str]


class PublicCheckIn(RequestModel):
    soc_code: str = Field(pattern=r"^[1-9][0-9]{3}$")
    weekly_hours: Decimal = Field(gt=0, le=168, max_digits=5, decimal_places=2)
    offered_salary: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    salary_per: SalaryPer
    work_nation: Nation
    cos_assignment_date: date | None = None
    turnstile_token: str = Field(min_length=1, max_length=2048)


class PublicCheckOut(BaseModel):
    """The salary table for a code, and nothing about the person who asked."""

    soc_code: str
    title: str
    rules_version_name: str
    rules_effective_from: date
    eligibility: str  # the label, for example "Eligible" or "On the TSL until ..."
    going_rate: Decimal | None
    options: list[OptionResult]
    verdict: Verdict
    dependants_allowed: bool
    notes: list[str]


async def _limit(request: Request, bucket: tuple[str, int, int]) -> None:
    name, limit, window = bucket
    result = await RateLimiter(request.app.state.auth.redis).hit(
        name, client_ip(request) or "unknown", limit=limit, window_seconds=window
    )
    if not result.allowed:
        raise AppError(
            "RATE_LIMITED",
            "Too many requests from this connection. Try again later.",
            status_code=429,
        )


@router.get("/search", response_model=PublicSearchOut)
async def search(
    request: Request,
    db: GlobalDb,
    q: Annotated[str, Query(max_length=100)] = "",
) -> PublicSearchOut:
    await _limit(request, SEARCH_PER_CONNECTION)
    title = normalise_title(q)
    if len(title) < 2:
        return PublicSearchOut(results=[])
    vector = await query_embedding(request, title)
    found = await retrieve(db, title, vector, CANDIDATES)
    return PublicSearchOut(results=[PublicHitOut(code=c.code, title=c.title) for c in found])


@router.get("/{code}", response_model=PublicCodeOut)
async def code_detail(code: CODE, request: Request, db: GlobalDb) -> PublicCodeOut:
    await _limit(request, SEARCH_PER_CONNECTION)
    unit = (
        await db.execute(select(SocUnitGroup).where(SocUnitGroup.code == code))
    ).scalar_one_or_none()
    if unit is None:
        raise NotFoundError("We could not find that SOC code.")
    return PublicCodeOut(
        code=unit.code,
        title=unit.title,
        description=unit.description,
        tasks=list(unit.tasks),
        typical_titles=list(unit.typical_titles),
    )


@router.post("/salary-check", response_model=PublicCheckOut)
async def salary_check(body: PublicCheckIn, request: Request, db: GlobalDb) -> PublicCheckOut:
    await _limit(request, CHECK_PER_CONNECTION)
    ip = client_ip(request)
    if not await request.app.state.auth.turnstile.verify(body.turnstile_token, ip):
        raise AppError(
            "TURNSTILE_FAILED",
            "We could not confirm you are a person. Try again.",
            status_code=400,
            field="turnstile_token",
        )
    try:
        rules = await load_rules_data(db)
    except NoRulesVersionError as exc:
        raise AppError(
            "RULES_NOT_PUBLISHED", "The SOC rules have not been published yet.", status_code=409
        ) from exc
    today = datetime.now(ZONE).date()
    try:
        result = evaluate(
            rules,
            CheckInput(
                soc_code=body.soc_code,
                weekly_hours=body.weekly_hours,
                offered_salary=body.offered_salary,
                salary_per=body.salary_per,
                work_nation=body.work_nation,
                cos_assignment_date=body.cos_assignment_date or today,
                applicant=Applicant(),
            ),
        )
    except ValueError as exc:
        raise AppError(
            "CHECK_NOT_VALID", f"This check cannot be assessed: {exc}", status_code=422
        ) from exc
    return PublicCheckOut(
        soc_code=result.soc_code,
        title=result.title,
        rules_version_name=result.rules_version_name,
        rules_effective_from=result.rules_effective_from,
        eligibility=result.eligibility.label,
        going_rate=result.going_rate,
        options=list(result.options),
        verdict=result.verdict,
        dependants_allowed=result.dependants_allowed,
        notes=list(result.notes),
    )
