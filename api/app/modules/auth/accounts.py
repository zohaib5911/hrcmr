"""What the auth endpoints do besides signing in: creating an account, e-mailed one-time links,
passwords, invitations, company switching, and describing the caller (plan.md 8.1)."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.core.rate_limit import (
    PASSWORD_RESET_PER_EMAIL,
    SIGNUP_PER_IP,
    RateLimiter,
)
from app.core.rbac_matrix import permissions_for
from app.db.ids import uuid7
from app.modules.audit.service import AuditContext, record
from app.modules.auth.audit import security_event
from app.modules.auth.invitations import accept_invitation, find_valid_invitation
from app.modules.auth.passwords import (
    PasswordProblem,
    hash_password,
    password_problems,
    spend_verification_time,
)
from app.modules.auth.policy import mfa_state
from app.modules.auth.schemas import (
    CompanyMembership,
    MeResponse,
    MeUser,
)
from app.modules.auth.service import RateLimitedError
from app.modules.auth.tokens import hash_token, new_token
from app.modules.companies.models import Company
from app.modules.identity.models import (
    EmailToken,
    Membership,
    PlatformAdmin,
    TermsAcceptance,
    TermsVersion,
    User,
)
from app.modules.leave.service import seed_types
from app.modules.organogram.service import seed_levels

if TYPE_CHECKING:
    import uuid

    from app.db.session import GlobalSession
    from app.modules.auth.container import AuthContainer
    from app.modules.auth.deps import Caller
    from app.modules.auth.schemas import SignupRequest

VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(hours=1)

_PASSWORD_MESSAGES = {
    PasswordProblem.TOO_SHORT: "Use at least 12 characters.",
    PasswordProblem.TOO_LONG: "That password is too long. Use 200 characters or fewer.",
    PasswordProblem.COMMON: "That password is too common. Choose something harder to guess.",
    PasswordProblem.BREACHED: "That password has been in a data breach. Choose a different one.",
}


def now() -> datetime:
    return datetime.now(UTC)


class TokenInvalidError(AppError):
    """One answer for a link that is unknown, used or too old."""

    def __init__(self) -> None:
        super().__init__(
            "TOKEN_INVALID",
            "This link is no longer valid. Request a new one.",
            status_code=410,
        )


def link(auth: AuthContainer, path: str, token: str) -> str:
    return f"{auth.settings.web_origin}{path}?token={token}"


async def check_password(password: str, field: str = "password") -> None:
    problems = await password_problems(password)
    if problems:
        raise AppError(
            "WEAK_PASSWORD", _PASSWORD_MESSAGES[problems[0]], status_code=422, field=field
        )


async def check_turnstile(auth: AuthContainer, token: str | None, ip: str | None) -> None:
    if not await auth.turnstile.verify(token, ip):
        raise AppError(
            "TURNSTILE_FAILED",
            "We could not confirm you are a person. Try again.",
            status_code=400,
            field="turnstile_token",
        )


async def current_terms(db: GlobalSession) -> TermsVersion:
    terms = (
        await db.execute(select(TermsVersion).order_by(TermsVersion.published_at.desc()).limit(1))
    ).scalar_one_or_none()
    if terms is None:
        raise AppError("TERMS_UNAVAILABLE", "Terms are not available yet.", status_code=503)
    return terms


async def issue_email_token(
    db: GlobalSession, user_id: uuid.UUID, purpose: str, ttl: timedelta
) -> str:
    token = new_token()
    db.add(
        EmailToken(
            user_id=user_id, purpose=purpose, token_hash=hash_token(token), expires_at=now() + ttl
        )
    )
    await db.flush()
    return token


async def consume_email_token(db: GlobalSession, token: str, purpose: str) -> EmailToken:
    row = (
        await db.execute(select(EmailToken).where(EmailToken.token_hash == hash_token(token)))
    ).scalar_one_or_none()
    if row is None or row.purpose != purpose or row.used_at is not None or row.expires_at <= now():
        raise TokenInvalidError
    row.used_at = now()
    return row


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50] or "company"
    return f"{base}-{secrets.token_hex(3)}"


# --- signing up ---------------------------------------------------------------------------------


async def sign_up(
    db: GlobalSession, auth: AuthContainer, request: SignupRequest, *, ip: str | None
) -> None:
    """Create a company and its first Company Admin, on the free plan, and send the verification
    e-mail. The caller gets the same answer if the address already has an account."""
    limit_name, limit, window = SIGNUP_PER_IP
    result = await RateLimiter(auth.redis).hit(
        limit_name, ip or "unknown", limit=limit, window_seconds=window
    )
    if not result.allowed:
        raise RateLimitedError(result.retry_after)
    if not request.accept_terms:
        raise AppError(
            "TERMS_REQUIRED",
            "Accept the terms to create an account.",
            status_code=422,
            field="accept_terms",
        )
    await check_turnstile(auth, request.turnstile_token, ip)
    await check_password(request.password)
    password_hash = hash_password(request.password)  # always done, so timing does not give it away

    email = str(request.email).strip().lower()
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        await auth.mailer.send_template(
            to=email,
            template="account_exists",
            data={
                "first_name": existing.first_name,
                "sign_in_link": f"{auth.settings.web_origin}/login",
                "reset_link": f"{auth.settings.web_origin}/forgot-password",
            },
        )
        return

    terms = await current_terms(db)
    company = Company(
        id=uuid7(),
        name=request.company_name.strip(),
        slug=_slug(request.company_name),
        bank_holiday_region=request.bank_holiday_region,
    )
    user = User(
        email=email,
        first_name=request.first_name.strip(),
        last_name=request.last_name.strip(),
        password_hash=password_hash,
    )
    db.add_all([company, user])
    try:
        await db.flush()
    except IntegrityError:  # a slug collision or a sign-up racing this one: treat as "exists"
        await db.rollback()
        return
    await db.scope_to_company(company.id)
    await seed_types(db, company.id)
    await seed_levels(db, company.id)
    db.add(Membership(user_id=user.id, company_id=company.id, role="company_admin"))
    db.add(TermsAcceptance(user_id=user.id, version=terms.version, ip=ip))
    token = await issue_email_token(db, user.id, "verify", VERIFY_TTL)
    await record(
        db,
        AuditContext(company_id=company.id, actor_user_id=user.id, ip=ip),
        "company.created",
        entity_type="company",
        entity_id=company.id,
        after={"name": company.name, "plan": "free", "admin_email": email},
    )
    await security_event(db, "auth.signup", user_id=user.id, company_id=company.id, ip=ip)
    await db.commit()
    await auth.mailer.send_template(
        to=email,
        template="verify_email",
        data={
            "first_name": user.first_name,
            "link": link(auth, "/verify-email", token),
        },
    )


async def resend_verification(
    db: GlobalSession, auth: AuthContainer, email: str, *, ip: str | None
) -> None:
    email = email.strip().lower()
    _, limit, window = PASSWORD_RESET_PER_EMAIL
    result = await RateLimiter(auth.redis).hit(
        "verify-email", email, limit=limit, window_seconds=window
    )
    if not result.allowed:
        raise RateLimitedError(result.retry_after)
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or user.email_verified_at is not None or not user.is_active:
        spend_verification_time()
        return
    token = await issue_email_token(db, user.id, "verify", VERIFY_TTL)
    await db.commit()
    await auth.mailer.send_template(
        to=email,
        template="verify_email",
        data={"first_name": user.first_name, "link": link(auth, "/verify-email", token)},
    )


# --- passwords ----------------------------------------------------------------------------------


async def forgot_password(
    db: GlobalSession,
    auth: AuthContainer,
    email: str,
    turnstile_token: str | None,
    *,
    ip: str | None,
) -> None:
    email = email.strip().lower()
    await check_turnstile(auth, turnstile_token, ip)
    name, limit, window = PASSWORD_RESET_PER_EMAIL
    result = await RateLimiter(auth.redis).hit(name, email, limit=limit, window_seconds=window)
    if not result.allowed:
        raise RateLimitedError(result.retry_after)
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not user.is_active:
        spend_verification_time()
        return
    token = await issue_email_token(db, user.id, "reset", RESET_TTL)
    await db.commit()
    await auth.mailer.send_template(
        to=email,
        template="reset_password",
        data={"first_name": user.first_name, "link": link(auth, "/reset-password", token)},
    )


async def reset_password(
    db: GlobalSession,
    auth: AuthContainer,
    token: str,
    new_password: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> None:
    await check_password(new_password, field="new_password")
    row = await consume_email_token(db, token, "reset")
    user = (await db.execute(select(User).where(User.id == row.user_id))).scalar_one()
    user.password_hash = hash_password(new_password)
    user.requires_password_change = False
    user.failed_login_count = 0
    user.locked_until = None
    await auth.auth.clear_lockout(str(user.email))
    await auth.sessions.revoke_all(db, user.id)  # a reset ends every session, wherever it was
    await security_event(
        db,
        "auth.password.reset",
        user_id=user.id,
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    await db.commit()
    await auth.mailer.send_template(
        to=str(user.email), template="password_changed", data={"first_name": user.first_name}
    )


# --- describing the caller -----------------------------------------------------------------------


async def build_me(db: GlobalSession, caller: Caller, *, ai_key: bool = False) -> MeResponse:
    user = caller.user
    rows = (
        await db.execute(
            select(Membership, Company)
            .join(Company, Company.id == Membership.company_id)
            .where(Membership.user_id == user.id)
            .order_by(Company.name)
        )
    ).all()
    companies = [
        CompanyMembership(
            company_id=company.id,
            company_name=company.name,
            plan=company.plan,  # type: ignore[arg-type]
            role=membership.role,  # type: ignore[arg-type]
            status=membership.status,  # type: ignore[arg-type]
        )
        for membership, company in rows
    ]
    active = next((c for c in rows if str(c[1].id) == caller.session.company_id), None)
    platform_admin = (
        await db.execute(select(PlatformAdmin.id).where(PlatformAdmin.user_id == user.id))
    ).first() is not None
    terms = await current_terms(db)
    accepted = (
        await db.execute(
            select(TermsAcceptance.id).where(
                TermsAcceptance.user_id == user.id, TermsAcceptance.version == terms.version
            )
        )
    ).first() is not None
    role = active[0].role if active else None
    state = mfa_state(
        enrolled=user.mfa_enabled,
        passed=caller.session.mfa_passed,
        policy=active[1].mfa_policy if active else "optional",
        role=role,
        platform_admin=platform_admin,
    )
    from app.modules.auth.sessions import utcnow

    return MeResponse(
        user=MeUser(
            id=user.id,
            email=str(user.email),
            first_name=user.first_name,
            last_name=user.last_name,
            email_verified=user.email_verified_at is not None,
            mfa_enabled=user.mfa_enabled,
            theme_pref=user.theme_pref,  # type: ignore[arg-type]
        ),
        companies=companies,
        active_company_id=active[1].id if active else None,
        role=role,  # type: ignore[arg-type]
        permissions=sorted(permissions_for(role)),
        mfa=state.value,
        terms_acceptance_required=not accepted,
        terms_version=terms.version,
        step_up_active=caller.session.has_recent_step_up(utcnow()),
        platform_admin=platform_admin,
        ai_available=ai_key and active is not None and active[1].ai_features_enabled,
    )


# --- invitations ---------------------------------------------------------------------------------


async def invitation_details(db: GlobalSession, token: str) -> tuple[str, str, str, datetime, bool]:
    invitation = await find_valid_invitation(db, token)
    company = (
        await db.execute(select(Company.name).where(Company.id == invitation.company_id))
    ).scalar_one()
    has_account = (
        await db.execute(select(User.id).where(User.email == invitation.email))
    ).first() is not None
    return company, str(invitation.email), invitation.role, invitation.expires_at, has_account


async def accept_invite(
    db: GlobalSession,
    auth: AuthContainer,
    token: str,
    *,
    first_name: str,
    last_name: str,
    password: str | None,
    accept_terms: bool,
    ip: str | None,
) -> User | None:
    """Join the company. A new person sets their own password and is returned (so the caller can
    sign them in); someone who already has an account is added and must sign in as usual."""
    invitation = await find_valid_invitation(db, token)
    existing = (
        await db.execute(select(User).where(User.email == invitation.email))
    ).scalar_one_or_none()
    new_user: User | None = None
    if existing is None:
        if not accept_terms:
            raise AppError(
                "TERMS_REQUIRED",
                "Accept the terms to continue.",
                status_code=422,
                field="accept_terms",
            )
        if password is None:
            raise AppError(
                "PASSWORD_REQUIRED", "Choose a password.", status_code=422, field="password"
            )
        await check_password(password)
        new_user = User(
            email=str(invitation.email),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            password_hash=hash_password(password),
            email_verified_at=now(),  # the link only reached them by e-mail
        )
        db.add(new_user)
        await db.flush()
    else:
        spend_verification_time()
    user = new_user if new_user is not None else existing
    if user is None:  # unreachable: one of the two branches above set it
        raise AppError("INVITATION_INVALID", "This invitation is not valid.", status_code=410)
    await accept_invitation(db, token)
    await db.scope_to_company(invitation.company_id)
    already = (
        await db.execute(
            select(Membership.id).where(
                Membership.user_id == user.id, Membership.company_id == invitation.company_id
            )
        )
    ).first()
    if already is None:
        db.add(Membership(user_id=user.id, company_id=invitation.company_id, role=invitation.role))
    if new_user is not None:
        terms = await current_terms(db)
        db.add(TermsAcceptance(user_id=new_user.id, version=terms.version, ip=ip))
    await record(
        db,
        AuditContext(company_id=invitation.company_id, actor_user_id=user.id, ip=ip),
        "invitation.accepted",
        entity_type="user",
        entity_id=user.id,
        after={"email": str(invitation.email), "role": invitation.role},
    )
    await db.commit()
    return new_user
