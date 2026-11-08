"""The platform's company and user administration (T17.2): the overview numbers, companies (search,
detail, suspend, reactivate, extend the 10-year plan, mark for deletion) and users (search by
e-mail, lock, unlock). Every page view is audited by the guard; every change is audited here.

Marking a company for deletion is owner-only. The rest is open to any platform admin with MFA.

T17.4 adds the subscriptions and refunds (owner only, billing.py), the deletion and export queues
(queues.py) and the contact inbox (contact.py).
"""

from __future__ import annotations

import uuid  # noqa: TC003  (FastAPI reads the path parameter type at runtime)
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy import select

from app.core.errors import AppError, ForbiddenError
from app.modules.identity.models import PlatformAdmin
from app.modules.platform_admin import (
    announcements,
    billing,
    companies,
    contact,
    flags,
    metrics,
    queues,
    terms,
    users,
)
from app.modules.platform_admin.schemas import (
    AnnouncementIn,
    AnnouncementRow,
    AnnouncementsOut,
    CompaniesOut,
    CompanyDetailOut,
    ContactMessageRow,
    ContactMessagesOut,
    ContactUpdateIn,
    DataExportsOut,
    DeletionRequestsOut,
    ExtendIn,
    FeatureFlagIn,
    FeatureFlagRow,
    FeatureFlagsOut,
    MetricsOut,
    OptionalReasonIn,
    ReasonIn,
    RefundIn,
    RefundOut,
    SubscriptionsOut,
    TermsIn,
    TermsVersionRow,
    TermsVersionsOut,
    UserRow,
    UsersOut,
)
from app.modules.rbac.platform import PlatformAccess, require_platform

router = APIRouter(tags=["platform-admin"])
Reader = Annotated[PlatformAccess, Depends(require_platform("platform.companies.read"))]
Writer = Annotated[PlatformAccess, Depends(require_platform("platform.companies.write"))]
Refunder = Annotated[PlatformAccess, Depends(require_platform("platform.billing.refund"))]
Content = Annotated[PlatformAccess, Depends(require_platform("platform.content.write"))]
PLAN_PATTERN = "^(free|annual|ten_year)$"
STATUS_PATTERN = "^(active|suspended|pending_deletion|deleted)$"


async def _is_owner(access: PlatformAccess) -> bool:
    level = (
        await access.db.execute(
            select(PlatformAdmin.level).where(PlatformAdmin.user_id == access.caller.user_id)
        )
    ).scalar_one_or_none()
    return level == "owner"


@router.get("/platform/metrics", response_model=MetricsOut)
async def overview(access: Reader) -> MetricsOut:
    return await metrics.overview(access.db)


@router.get("/platform/companies", response_model=CompaniesOut)
async def list_companies(
    access: Reader,
    q: Annotated[str | None, Query(max_length=120)] = None,
    plan: Annotated[str | None, Query(pattern=PLAN_PATTERN)] = None,
    status: Annotated[str | None, Query(pattern=STATUS_PATTERN)] = None,
    created_since: datetime | None = None,
    active_since: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=companies.PAGE_MAX)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> CompaniesOut:
    return await companies.search(
        access.db,
        q=q,
        plan=plan,
        status=status,
        created_since=created_since,
        active_since=active_since,
        limit=limit,
        offset=offset,
    )


@router.get("/platform/companies/{company_id}", response_model=CompanyDetailOut)
async def get_company(company_id: uuid.UUID, access: Reader) -> CompanyDetailOut:
    company = await companies.company_or_404(access.db, company_id)
    return await companies.detail(access.db, company)


@router.post("/platform/companies/{company_id}/suspend", response_model=CompanyDetailOut)
async def suspend_company(
    company_id: uuid.UUID, body: ReasonIn, access: Writer
) -> CompanyDetailOut:
    company = await companies.company_or_404(access.db, company_id)
    await companies.suspend(access.db, access.audit_context, company, body.reason)
    await access.db.commit()
    return await companies.detail(access.db, company)


@router.post("/platform/companies/{company_id}/reactivate", response_model=CompanyDetailOut)
async def reactivate_company(
    company_id: uuid.UUID, body: ReasonIn, access: Writer
) -> CompanyDetailOut:
    company = await companies.company_or_404(access.db, company_id)
    await companies.reactivate(access.db, access.audit_context, company, body.reason)
    await access.db.commit()
    return await companies.detail(access.db, company)


@router.post("/platform/companies/{company_id}/extend-plan", response_model=CompanyDetailOut)
async def extend_company_plan(
    company_id: uuid.UUID, body: ExtendIn, access: Writer
) -> CompanyDetailOut:
    company = await companies.company_or_404(access.db, company_id)
    await companies.extend_plan(
        access.db,
        access.audit_context,
        company,
        days=body.days,
        reason=body.reason,
        now=datetime.now(UTC),
    )
    await access.db.commit()
    return await companies.detail(access.db, company)


@router.post("/platform/companies/{company_id}/mark-for-deletion", response_model=CompanyDetailOut)
async def mark_company_for_deletion(
    company_id: uuid.UUID, body: ReasonIn, access: Writer
) -> CompanyDetailOut:
    if not await _is_owner(access):
        raise ForbiddenError("Only an owner can mark a company for deletion.")
    company = await companies.company_or_404(access.db, company_id)
    await companies.mark_for_deletion(access.db, access.audit_context, company, body.reason)
    await access.db.commit()
    return await companies.detail(access.db, company)


@router.get("/platform/subscriptions", response_model=SubscriptionsOut)
async def list_subscriptions(
    access: Reader,
    plan: Annotated[str | None, Query(pattern="^(annual|ten_year)$")] = None,
    refunded: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=billing.PAGE_MAX)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> SubscriptionsOut:
    return await billing.subscriptions(
        access.db, plan=plan, refunded=refunded, limit=limit, offset=offset
    )


@router.post("/platform/refunds", response_model=RefundOut)
async def issue_refund(body: RefundIn, request: Request, access: Refunder) -> RefundOut:
    """A full refund of the latest payment on a purchase. Owner only (T17.4)."""
    if not await _is_owner(access):
        raise ForbiddenError("Only an owner can issue a refund.")
    if not body.confirm:
        raise AppError(
            "CONFIRMATION_REQUIRED",
            "Confirm that this payment should be refunded in full.",
            status_code=422,
            field="confirm",
        )
    subscription = await billing.subscription_or_404(access.db, body.subscription_id)
    refund_id = await billing.refund(
        access.db,
        request.app.state.stripe,
        access.audit_context,
        subscription,
        reason=body.reason,
        now=datetime.now(UTC),
    )
    await access.db.commit()
    return RefundOut(
        subscription=await billing.row_for(access.db, subscription),
        stripe_refund_id=refund_id,
    )


@router.get("/platform/deletion-requests", response_model=DeletionRequestsOut)
async def list_deletion_requests(
    access: Reader,
    status: Annotated[
        str | None,
        Query(pattern="^(awaiting_code|scheduled|withdrawn|completed)$"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=queues.PAGE_MAX)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> DeletionRequestsOut:
    return await queues.deletion_requests(access.db, status=status, limit=limit, offset=offset)


@router.get("/platform/data-exports", response_model=DataExportsOut)
async def list_data_exports(
    access: Reader,
    status: Annotated[str | None, Query(pattern="^(queued|ready|failed)$")] = None,
    limit: Annotated[int, Query(ge=1, le=queues.PAGE_MAX)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> DataExportsOut:
    return await queues.data_exports(access.db, status=status, limit=limit, offset=offset)


@router.get("/platform/contact-messages", response_model=ContactMessagesOut)
async def list_contact_messages(
    access: Reader,
    handled: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=contact.PAGE_MAX)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> ContactMessagesOut:
    return await contact.messages(access.db, handled=handled, limit=limit, offset=offset)


@router.patch("/platform/contact-messages/{message_id}", response_model=ContactMessageRow)
async def mark_contact_message(
    message_id: uuid.UUID, body: ContactUpdateIn, access: Writer
) -> ContactMessageRow:
    message = await contact.message_or_404(access.db, message_id)
    await contact.set_handled(
        access.db, access.audit_context, message, handled=body.handled, now=datetime.now(UTC)
    )
    await access.db.commit()
    return contact.row(message)


@router.get("/platform/terms-versions", response_model=TermsVersionsOut)
async def list_terms_versions(access: Reader) -> TermsVersionsOut:
    return await terms.versions(access.db)


@router.post("/platform/terms-versions", status_code=201, response_model=TermsVersionRow)
async def publish_terms_version(body: TermsIn, access: Content) -> TermsVersionRow:
    """Publish a new terms version. Everyone must accept it before using the product (T17.5)."""
    if not await _is_owner(access):
        raise ForbiddenError("Only an owner can publish a terms version.")
    published = await terms.publish(
        access.db,
        access.audit_context,
        version=body.version,
        url=body.url,
        reason=body.reason,
        now=datetime.now(UTC),
    )
    await access.db.commit()
    return terms.row(published, current=True)


@router.get("/platform/feature-flags", response_model=FeatureFlagsOut)
async def list_feature_flags(access: Reader) -> FeatureFlagsOut:
    return await flags.flags(access.db)


@router.put("/platform/feature-flags/{key}", response_model=FeatureFlagRow)
async def set_feature_flag(
    key: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{2,59}$")],
    body: FeatureFlagIn,
    access: Content,
) -> FeatureFlagRow:
    """Turn a feature on or off for everyone, with a reason (T17.5)."""
    flag = await flags.set_flag(
        access.db,
        access.audit_context,
        key,
        enabled=body.enabled,
        description=body.description,
        reason=body.reason,
        actor=access.caller.user_id,
        now=datetime.now(UTC),
    )
    await access.db.commit()
    return flags.row(flag)


@router.get("/platform/announcements", response_model=AnnouncementsOut)
async def list_announcements(access: Reader) -> AnnouncementsOut:
    return await announcements.announcements(access.db, datetime.now(UTC))


@router.post("/platform/announcements", status_code=201, response_model=AnnouncementRow)
async def create_announcement(body: AnnouncementIn, access: Content) -> AnnouncementRow:
    """Schedule a banner for one region (T17.5). Companies in that region see it while live."""
    now = datetime.now(UTC)
    item = await announcements.create(
        access.db,
        access.audit_context,
        region=body.region,
        title=body.title,
        body=body.body,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        reason=body.reason,
        now=now,
    )
    await access.db.commit()
    return announcements.row(item, now)


@router.post("/platform/announcements/{announcement_id}/end", response_model=AnnouncementRow)
async def end_announcement(
    announcement_id: uuid.UUID, body: ReasonIn, access: Content
) -> AnnouncementRow:
    now = datetime.now(UTC)
    item = await announcements.end(
        access.db, access.audit_context, announcement_id, reason=body.reason, now=now
    )
    await access.db.commit()
    return announcements.row(item, now)


@router.get("/platform/users", response_model=UsersOut)
async def search_users(
    access: Reader,
    q: Annotated[str, Query(min_length=users.SEARCH_MIN, max_length=254)],
) -> UsersOut:
    return await users.search(access.db, q)


@router.post("/platform/users/{user_id}/lock", response_model=UserRow)
async def lock_user(
    user_id: uuid.UUID, access: Writer, body: OptionalReasonIn | None = None
) -> UserRow:
    user = await users.user_or_404(access.db, user_id)
    await users.lock(access.db, access.audit_context, user, body.reason if body else None)
    await access.db.commit()
    return await users.row(access.db, user)


@router.post("/platform/users/{user_id}/unlock", response_model=UserRow)
async def unlock_user(
    user_id: uuid.UUID, access: Writer, body: OptionalReasonIn | None = None
) -> UserRow:
    user = await users.user_or_404(access.db, user_id)
    await users.unlock(access.db, access.audit_context, user, body.reason if body else None)
    await access.db.commit()
    return await users.row(access.db, user)
