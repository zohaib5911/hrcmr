"""The shapes the auth endpoints accept and return (plan.md section 11, "Auth")."""

from __future__ import annotations

import uuid  # noqa: TC003  (pydantic resolves the annotations at runtime)
from datetime import datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.schemas import RequestModel

BankHolidayRegion = Literal["england-and-wales", "scotland", "northern-ireland"]
Role = Literal[
    "company_admin", "hr_admin", "people_manager", "recruiter", "employee", "read_only_auditor"
]


class Accepted(BaseModel):
    """The same answer whether or not the address has an account (nothing is revealed)."""

    status: Literal["check_your_inbox"] = "check_your_inbox"


class SignupRequest(RequestModel):
    company_name: str = Field(min_length=1, max_length=200)
    bank_holiday_region: BankHolidayRegion = "england-and-wales"
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(max_length=1000)
    accept_terms: bool
    turnstile_token: str | None = Field(default=None, max_length=4096)


class TokenRequest(RequestModel):
    token: str = Field(min_length=1, max_length=200)


class EmailRequest(RequestModel):
    email: EmailStr
    turnstile_token: str | None = Field(default=None, max_length=4096)


class LoginRequest(RequestModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1000)
    turnstile_token: str | None = Field(default=None, max_length=4096)


class ResetPasswordRequest(RequestModel):
    token: str = Field(min_length=1, max_length=200)
    new_password: str = Field(max_length=1000)


class ChangePasswordRequest(RequestModel):
    current_password: str = Field(min_length=1, max_length=1000)
    new_password: str = Field(max_length=1000)


class CodeRequest(RequestModel):
    code: str = Field(min_length=1, max_length=32)


class StepUpRequest(RequestModel):
    password: str | None = Field(default=None, max_length=1000)
    code: str | None = Field(default=None, max_length=32)


class AcceptTermsRequest(RequestModel):
    version: str = Field(min_length=1, max_length=40)


class SwitchCompanyRequest(RequestModel):
    company_id: uuid.UUID


class AcceptInvitationRequest(RequestModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    password: str | None = Field(default=None, max_length=1000)
    accept_terms: bool


class CompanyMembership(BaseModel):
    company_id: uuid.UUID
    company_name: str
    plan: Literal["free", "annual", "ten_year"]
    role: Role
    status: Literal["active", "suspended"]


class MeUser(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    email_verified: bool
    mfa_enabled: bool
    theme_pref: Literal["system", "light", "dark"]


class SupportModeInfo(BaseModel):
    """Present while a platform admin is in support mode (T17.3): the tenant app shows a banner."""

    id: uuid.UUID
    company_name: str
    ticket_ref: str
    expires_at: datetime
    write_enabled: bool


class MeResponse(BaseModel):
    user: MeUser
    companies: list[CompanyMembership]
    active_company_id: uuid.UUID | None
    role: Role | None
    permissions: list[str] = Field(
        description="What the active role may do (plan 7). The web app hides what is not listed; "
        "the API still checks every request."
    )
    mfa: Literal["not_required", "challenge", "enrol"]
    terms_acceptance_required: bool
    terms_version: str
    step_up_active: bool
    platform_admin: bool
    # True only when the server has an AI key and the active company allows AI features.
    ai_available: bool
    support: SupportModeInfo | None = None


class LoginResponse(BaseModel):
    mfa_required: bool
    company_selection_required: bool
    me: MeResponse | None = Field(
        default=None, description="Present once the second step (if any) is done."
    )


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class InvitationDetails(BaseModel):
    company_name: str
    email: str
    role: Role
    expires_at: datetime
    has_account: bool
