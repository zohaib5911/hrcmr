"""Public careers pages and the apply form (T11.6). No login.

Only external, open postings are shown. Every POST checks Turnstile and a rate limit.
Responses carry only the fields listed here; a test checks that nothing else leaks (recipe R5).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal  # noqa: TC003
from typing import Annotated, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr, StringConstraints, field_validator
from sqlalchemy import func, select

from app.core.crypto import encrypt
from app.core.errors import AppError, NotFoundError
from app.core.rate_limit import RateLimiter
from app.core.rbac_matrix import scope_for
from app.core.schemas import RequestModel
from app.db.ids import uuid7
from app.db.session import GlobalDb, GlobalSession, TenantSession, get_engine
from app.modules.audit.service import AuditContext, record
from app.modules.auth.deps import client_ip
from app.modules.companies.models import Company, Location
from app.modules.email.models import EmailOutbox
from app.modules.email.outbox import PAYLOAD_CONTEXT
from app.modules.email.templates import check
from app.modules.identity.models import Membership
from app.modules.notifications.models import Notification
from app.modules.recruitment.models import Application, Candidate, Posting

router = APIRouter(prefix="/public", tags=["careers"])

APPLY_PER_CONNECTION = ("careers.apply", 20, 3600)  # attempts, per hour, per connection


class CareersPostingItem(BaseModel):
    slug: str
    title: str
    location: str | None
    closes_on: date | None


class CareersPage(BaseModel):
    company: str
    postings: list[CareersPostingItem]


class CareersPostingDetail(BaseModel):
    company: str
    slug: str
    title: str
    location: str | None
    salary_from: Decimal | None
    salary_to: Decimal | None
    salary_per: str | None
    weekly_hours: Decimal | None
    description: str | None
    visa_sponsorship: str
    closes_on: date | None


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class ApplyIn(RequestModel):
    first_name: Name
    last_name: Name
    email: EmailStr
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    what_you_bring: Annotated[str, StringConstraints(max_length=3000)] | None = None
    consent: bool
    turnstile_token: Annotated[str, StringConstraints(min_length=1, max_length=2048)]

    @field_validator("consent")
    @classmethod
    def consented(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError(
                "Tick to agree that we may store your details to consider your application."
            )
        return value


class ApplyOut(BaseModel):
    received: Literal[True] = True


async def _company(db: GlobalSession, slug: str) -> Company:
    company = (
        await db.execute(select(Company).where(Company.slug == slug, Company.status == "active"))
    ).scalar_one_or_none()
    if company is None:
        raise NotFoundError
    return company


async def _open_external(tenant: TenantSession, slug: str) -> tuple[Posting, str | None]:
    """An open, external posting in this company with its location name; otherwise a 404."""
    row = (
        await tenant.execute(
            select(Posting, Location.name)
            .outerjoin(Location, Location.id == Posting.location_id)
            .where(
                Posting.slug == slug,
                Posting.visibility == "external",
                Posting.status == "open",
            )
        )
    ).first()
    if row is None:
        raise NotFoundError
    return row[0], row[1]


@router.get("/careers/{company_slug}", response_model=CareersPage)
async def careers_page(company_slug: str, db: GlobalDb, request: Request) -> CareersPage:
    company = await _company(db, company_slug)
    async with TenantSession(get_engine(request), company_id=company.id) as tenant:
        rows = (
            await tenant.execute(
                select(Posting, Location.name)
                .outerjoin(Location, Location.id == Posting.location_id)
                .where(Posting.visibility == "external", Posting.status == "open")
                .order_by(Posting.posted_on.desc().nulls_last(), Posting.title)
            )
        ).all()
    return CareersPage(
        company=company.name,
        postings=[
            CareersPostingItem(
                slug=row.slug, title=row.title, location=place, closes_on=row.closes_on
            )
            for row, place in rows
        ],
    )


@router.get("/postings/{company_slug}/{posting_slug}", response_model=CareersPostingDetail)
async def careers_posting(
    company_slug: str, posting_slug: str, db: GlobalDb, request: Request
) -> CareersPostingDetail:
    company = await _company(db, company_slug)
    async with TenantSession(get_engine(request), company_id=company.id) as tenant:
        row, place = await _open_external(tenant, posting_slug)
    return CareersPostingDetail(
        company=company.name,
        slug=row.slug,
        title=row.title,
        location=place,
        salary_from=row.salary_from,
        salary_to=row.salary_to,
        salary_per=row.salary_per,
        weekly_hours=row.weekly_hours,
        description=row.description,
        visa_sponsorship=row.visa_sponsorship,
        closes_on=row.closes_on,
    )


@router.post(
    "/postings/{company_slug}/{posting_slug}/apply", status_code=202, response_model=ApplyOut
)
async def apply(
    company_slug: str, posting_slug: str, body: ApplyIn, db: GlobalDb, request: Request
) -> ApplyOut:
    company = await _company(db, company_slug)
    ip = client_ip(request)
    auth = request.app.state.auth
    name, limit, window = APPLY_PER_CONNECTION
    result = await RateLimiter(auth.redis).hit(
        name, ip or "unknown", limit=limit, window_seconds=window
    )
    if not result.allowed:
        raise AppError(
            "RATE_LIMITED",
            "Too many applications from this connection. Try again later.",
            status_code=429,
        )
    if not await auth.turnstile.verify(body.turnstile_token, ip):
        raise AppError(
            "TURNSTILE_FAILED",
            "We could not confirm you are a person. Try again.",
            status_code=400,
            field="turnstile_token",
        )
    email = str(body.email).strip().lower()
    async with TenantSession(get_engine(request), company_id=company.id) as tenant:
        posting, _place = await _open_external(tenant, posting_slug)
        candidate = (
            await tenant.execute(
                select(Candidate)
                .where(func.lower(Candidate.email) == email, Candidate.archived_at.is_(None))
                .limit(1)
            )
        ).scalar_one_or_none()
        if candidate is None:
            candidate = Candidate(
                id=uuid7(),
                company_id=company.id,
                first_name=body.first_name,
                last_name=body.last_name,
                email=email,
                phone=body.phone,
                source="Careers page",
            )
            tenant.add(candidate)
            await tenant.flush()
        already = (
            await tenant.execute(
                select(Application.id).where(
                    Application.candidate_id == candidate.id, Application.posting_id == posting.id
                )
            )
        ).first()
        if already is None:
            await _record_application(tenant, company, posting, candidate, body, ip, request)
        await tenant.commit()
    return ApplyOut()


async def _record_application(
    tenant: TenantSession,
    company: Company,
    posting: Posting,
    candidate: Candidate,
    body: ApplyIn,
    ip: str | None,
    request: Request,
) -> None:
    moment = datetime.now(UTC).isoformat()
    application = Application(
        id=uuid7(),
        company_id=company.id,
        candidate_id=candidate.id,
        posting_id=posting.id,
        stage="applied",
        stage_history=[{"stage": "applied", "at": moment, "by": None}],
        cover_note=body.what_you_bring,
        applied_via="careers_page",
    )
    tenant.add(application)
    await tenant.flush()
    data: dict[str, str] = {
        "first_name": candidate.first_name,
        "job_title": posting.title,
        "company_name": company.name,
    }
    check("application_received", data)
    tenant.add(
        EmailOutbox(
            to_address=candidate.email or "",
            template="application_received",
            payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
        )
    )
    recruiters = (
        await tenant.execute(
            select(Membership.user_id, Membership.role).where(
                Membership.company_id == company.id, Membership.status == "active"
            )
        )
    ).all()
    link = f"/recruitment/applications/{application.id}"
    for user_id, role in recruiters:
        if scope_for(role, "recruitment.application.read") is None:
            continue
        tenant.add(
            Notification(
                company_id=company.id,
                user_id=user_id,
                kind="recruitment.application_received",
                title="New application",
                body=f"{candidate.first_name} {candidate.last_name} applied for {posting.title}",
                link=link,
            )
        )
    await record(
        tenant,
        AuditContext(company_id=company.id, actor_user_id=None, actor_type="system", ip=ip),
        "recruitment.application.received",
        entity_type="application",
        entity_id=application.id,
        after={"posting_id": str(posting.id), "candidate_id": str(candidate.id)},
    )
