"""Request and response shapes for the platform's company and user administration (T17.2)."""

from __future__ import annotations

import uuid  # noqa: TC003  (pydantic reads the field types at runtime)
from datetime import datetime  # noqa: TC003  (pydantic reads the field types at runtime)

from pydantic import BaseModel, Field

from app.core.schemas import RequestModel

REASON_MIN = 5
REASON_MAX = 500


class MetricsOut(BaseModel):
    generated_at: datetime
    signups_24h: int
    signups_7d: int
    companies_active: int
    plans_active: dict[str, int]  # active companies by plan: free, annual, ten_year
    paid_entitled: int  # active paid companies that may use the product now (plan 8.16)
    mrr_pence: int  # annual entitled companies at £50 a year, per month (10-year is one-off)
    arr_pence: int  # the same, per year
    churn_30d: int  # paid plans that ended in the last 30 days
    refunds_30d: int  # Stripe refunds recorded in the last 30 days


class CompanyRow(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    contact_email: str | None
    status: str
    plan: str
    subscription_status: str | None
    subscription_ends_at: datetime | None
    created_at: datetime
    last_active_at: datetime | None  # the latest sign-in of any of its people
    members: int


class CompaniesOut(BaseModel):
    items: list[CompanyRow]
    total: int


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    status: str
    locked: bool
    mfa_enabled: bool
    last_login_at: datetime | None


class PlatformEventOut(BaseModel):
    action: str
    reason: str | None
    summary: str | None
    created_at: datetime


class CompanyDetailOut(CompanyRow):
    trading_name: str | None
    registered_number: str | None
    subscription_started_at: datetime | None
    payment_grace_ends_at: datetime | None
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    people: list[MemberOut]
    events: list[PlatformEventOut]  # the latest platform actions on this company


class ReasonIn(RequestModel):
    reason: str = Field(min_length=REASON_MIN, max_length=REASON_MAX)


class ExtendIn(RequestModel):
    days: int = Field(ge=1, le=365)
    reason: str = Field(min_length=REASON_MIN, max_length=REASON_MAX)


class OptionalReasonIn(RequestModel):
    reason: str | None = Field(default=None, max_length=REASON_MAX)


class UserCompanyOut(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    status: str


class UserRow(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    locked: bool
    mfa_enabled: bool
    email_verified: bool
    last_login_at: datetime | None
    companies: list[UserCompanyOut]


class UsersOut(BaseModel):
    items: list[UserRow]


class SubscriptionRow(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str
    plan: str  # annual | ten_year
    status: str  # Stripe's status for an annual plan; active or refunded for a 10-year payment
    created_at: datetime
    current_period_end: datetime | None
    cancel_at: datetime | None
    refunded_at: datetime | None
    stripe_subscription_id: str | None
    stripe_payment_intent_id: str | None


class SubscriptionsOut(BaseModel):
    items: list[SubscriptionRow]
    total: int


class RefundIn(RequestModel):
    subscription_id: uuid.UUID
    reason: str = Field(min_length=REASON_MIN, max_length=REASON_MAX)
    confirm: bool = Field(description="The second confirmation: must be true to issue the refund.")


class RefundOut(BaseModel):
    subscription: SubscriptionRow
    stripe_refund_id: str


class DeletionRequestRow(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str
    status: str  # awaiting_code | scheduled | withdrawn | completed
    requested_at: datetime
    scheduled_for: datetime | None
    withdrawn_at: datetime | None
    completed_at: datetime | None
    export_requested: bool


class DeletionRequestsOut(BaseModel):
    items: list[DeletionRequestRow]
    total: int


class DataExportRow(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str
    status: str  # queued | ready | failed
    requested_at: datetime
    finished_at: datetime | None
    expires_at: datetime | None
    error_code: str | None


class DataExportsOut(BaseModel):
    items: list[DataExportRow]
    total: int


class ContactMessageRow(BaseModel):
    id: uuid.UUID
    name: str
    company: str | None
    email: str
    topic: str
    message: str
    created_at: datetime
    handled_at: datetime | None


class ContactMessagesOut(BaseModel):
    items: list[ContactMessageRow]
    total: int


class ContactUpdateIn(RequestModel):
    handled: bool


class TermsIn(RequestModel):
    version: str = Field(pattern=r"^[A-Za-z0-9._-]{1,40}$")
    url: str = Field(min_length=1, max_length=300, pattern=r"^(https://|/)")
    reason: str = Field(min_length=REASON_MIN, max_length=REASON_MAX)


class TermsVersionRow(BaseModel):
    id: uuid.UUID
    version: str
    url: str
    published_at: datetime
    current: bool  # the newest published version: everyone accepts this one


class TermsVersionsOut(BaseModel):
    items: list[TermsVersionRow]
    total: int


class FeatureFlagRow(BaseModel):
    key: str
    enabled: bool
    description: str
    updated_at: datetime


class FeatureFlagsOut(BaseModel):
    items: list[FeatureFlagRow]
    total: int


class FeatureFlagIn(RequestModel):
    enabled: bool
    description: str | None = Field(default=None, max_length=300)
    reason: str = Field(min_length=REASON_MIN, max_length=REASON_MAX)
