"""The SOC checker's search and match endpoints (plan 8.17, T15.4).

``GET /soc/search`` finds unit groups for a job title (retrieval only, no AI). ``POST /soc/match``
takes the job and the applicant's pay and hours: it retrieves candidates, has Claude rank them when
AI is on (see ``ranking``), then runs the deterministic rules engine on the top three codes.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from decimal import Decimal  # noqa: TC003  (pydantic reads the field types at runtime)
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, StringConstraints

from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.schemas import RequestModel
from app.modules.rbac.deps import Access, require
from app.modules.soc.importer import Embedder, fastembed_embedder
from app.modules.soc.ranking import Ranked, rank
from app.modules.soc.retrieval import (
    CANDIDATES,
    DESCRIPTION_CHARS,
    normalise_title,
    query_vector,
    retrieve,
)
from app.modules.soc_rules.engine import Applicant, CheckInput, CheckResult, evaluate
from app.modules.soc_rules.loader import NoRulesVersionError, load_rules_data

logger = get_logger("app.soc")
router = APIRouter(tags=["soc"])
Searcher = Annotated[Access, Depends(require("soc.check.read"))]
Matcher = Annotated[Access, Depends(require("soc.check.run"))]

TOP_CHECKS = 3  # plan 8.17 step 2d: the rules engine runs on the top three codes
ZONE = ZoneInfo("Europe/London")
SEARCH_UNAVAILABLE = "The job title search is not available right now. Try again later."
Situation = Literal[
    "outside_uk",
    "switching_graduate",
    "switching_student",
    "switching_other",
    "extending",
    "changing_employer",
]
Nation = Literal["England", "Scotland", "Wales", "Northern Ireland"]
SalaryPer = Literal["year", "month", "week", "hour"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]


class SocSearchHitOut(BaseModel):
    code: str
    title: str
    matched_title: str


class SocSearchOut(BaseModel):
    results: list[SocSearchHitOut]


class SocApplicantIn(RequestModel):
    """The applicant's situation and qualifiers (plan 8.17 step 1). Each flag defaults to no."""

    situation: Situation = "outside_uk"
    skilled_worker_before_2024_04_04: bool = False
    skilled_worker_before_2025_07_22: bool = False
    same_sponsor: bool = False
    previous_isl_same_job: bool = False
    under_26: bool = False
    recent_uk_student_or_graduate: bool = False
    professional_training: bool = False
    postdoctoral: bool = False
    phd_relevant: bool = False
    stem_phd: bool = False


class SocCheckIn(RequestModel):
    weekly_hours: Annotated[Decimal, Field(gt=0, le=168, max_digits=5, decimal_places=2)]
    offered_salary: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
    salary_per: SalaryPer
    work_nation: Nation
    # The Certificate of Sponsorship assignment date; today when left out.
    cos_assignment_date: date | None = None
    applicant: SocApplicantIn = Field(default_factory=SocApplicantIn)
    # Table 3/3a/4/5 codes need the band or role, and teachers the pay area (SOC rules notes).
    pay_scale_role: str | None = Field(default=None, max_length=200)
    pay_scale_administration: str | None = Field(default=None, max_length=200)


class SocMatchIn(RequestModel):
    job_title: Title
    job_description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] = ""
    check: SocCheckIn


class SocCandidateOut(BaseModel):
    rank: int
    code: str
    title: str
    matched_title: str
    confidence: int | None  # null when the result is not AI-ranked
    matched_duties: list[str]
    reason: str | None


class SocMatchOut(BaseModel):
    ai_ranked: bool
    notice: str | None
    confidence: int | None  # the best candidate's confidence, 0-100
    low_confidence: bool  # true when that confidence is under 60
    candidates: list[SocCandidateOut]
    checks: list[CheckResult]  # the rules engine's answer for the top three codes


async def query_embedding(request: Request, text: str) -> list[float]:
    """The query embedding. The local model loads on first use and is then kept on the app."""
    try:
        embed: Embedder | None = getattr(request.app.state, "soc_embedder", None)
        if embed is None:
            embed = await asyncio.to_thread(fastembed_embedder)
            request.app.state.soc_embedder = embed
        return await query_vector(embed, text)
    except Exception as exc:  # the weights could not load, or the model failed on this input
        logger.warning("soc_embedding_failed")
        raise AppError("SOC_SEARCH_UNAVAILABLE", SEARCH_UNAVAILABLE, status_code=503) from exc


def check_input(check: SocCheckIn, code: str, today: date) -> CheckInput:
    return CheckInput(
        soc_code=code,
        weekly_hours=check.weekly_hours,
        offered_salary=check.offered_salary,
        salary_per=check.salary_per,
        work_nation=check.work_nation,
        cos_assignment_date=check.cos_assignment_date or today,
        applicant=Applicant(**check.applicant.model_dump()),
        pay_scale_role=check.pay_scale_role,
        pay_scale_administration=check.pay_scale_administration,
    )


def _candidate_out(position: int, item: Ranked) -> SocCandidateOut:
    return SocCandidateOut(
        rank=position,
        code=item.candidate.code,
        title=item.candidate.title,
        matched_title=item.candidate.matched_title,
        confidence=item.confidence,
        matched_duties=list(item.matched_duties),
        reason=item.reason,
    )


@router.get("/soc/search", response_model=SocSearchOut)
async def search(
    request: Request,
    access: Searcher,
    q: Annotated[str, Query(max_length=100)] = "",
) -> SocSearchOut:
    """Up to ten unit groups for a job title. Under two characters returns nothing."""
    title = normalise_title(q)
    if len(title) < 2:
        return SocSearchOut(results=[])
    vector = await query_embedding(request, title)
    found = await retrieve(access.db, title, vector, CANDIDATES)
    return SocSearchOut(
        results=[
            SocSearchHitOut(code=c.code, title=c.title, matched_title=c.matched_title)
            for c in found
        ]
    )


@router.post("/soc/match", response_model=SocMatchOut)
async def match(body: SocMatchIn, request: Request, access: Matcher) -> SocMatchOut:
    """Ranks the codes for a job, then checks the top three against the published rules.

    Answers 409 until a rules version is published, because the eligibility check needs it.
    """
    try:
        rules = await load_rules_data(access.db)
    except NoRulesVersionError as exc:
        raise AppError(
            "RULES_NOT_PUBLISHED", "The SOC rules have not been published yet.", status_code=409
        ) from exc
    title = normalise_title(body.job_title)
    if not title:
        raise AppError(
            "INVALID_JOB_TITLE",
            "Enter a job title with at least one letter or number.",
            status_code=422,
            field="job_title",
        )
    description = normalise_title(body.job_description)[:DESCRIPTION_CHARS]
    vector = await query_embedding(request, f"{title} {description}".strip())
    candidates = await retrieve(access.db, title, vector, CANDIDATES)
    outcome = await rank(
        request,
        access,
        job_title=body.job_title,
        job_description=body.job_description,
        candidates=candidates,
    )
    today = datetime.now(ZONE).date()
    try:
        checks = [
            evaluate(rules, check_input(body.check, item.candidate.code, today))
            for item in outcome.items[:TOP_CHECKS]
        ]
    except ValueError as exc:
        raise AppError(
            "CHECK_NOT_VALID", f"This check cannot be assessed: {exc}", status_code=422
        ) from exc
    top = outcome.items[0].confidence if outcome.items else None
    return SocMatchOut(
        ai_ranked=outcome.ai_ranked,
        notice=outcome.notice,
        confidence=top,
        low_confidence=outcome.low_confidence,
        candidates=[_candidate_out(n, item) for n, item in enumerate(outcome.items, start=1)],
        checks=checks,
    )
