"""The /auth endpoints (plan.md section 11). Thin: each one checks its input, calls the service that
does the work, and sets or clears the session cookie."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from app.core.errors import AppError, ConflictError, ForbiddenError
from app.core.totp import generate_secret, provisioning_uri
from app.db.session import GlobalDb  # noqa: TC001  (FastAPI reads the annotation at run time)
from app.modules.audit.service import AuditContext, record
from app.modules.auth import accounts
from app.modules.auth.deps import (
    Auth,
    Caller,
    SessionCaller,
    SignedIn,
    clear_session_cookie,
    client_ip,
    set_session_cookie,
    unauthenticated,
    user_agent,
)
from app.modules.auth.policy import mfa_required
from app.modules.auth.schemas import (
    Accepted,
    AcceptInvitationRequest,
    AcceptTermsRequest,
    ChangePasswordRequest,
    CodeRequest,
    EmailRequest,
    InvitationDetails,
    LoginRequest,
    LoginResponse,
    MeResponse,
    MfaSetupResponse,
    RecoveryCodesResponse,
    ResetPasswordRequest,
    SignupRequest,
    StepUpRequest,
    SwitchCompanyRequest,
    TokenRequest,
)
from app.modules.auth.service import InvalidCredentialsError, RateLimitedError
from app.modules.auth.sessions import require_step_up, utcnow
from app.modules.companies.models import Company
from app.modules.identity.models import Membership, TermsAcceptance, User

if TYPE_CHECKING:
    from app.modules.auth.service import LoginOutcome

router = APIRouter(prefix="/auth", tags=["auth"])

TURNSTILE_AFTER_FAILURES = 3
_MFA_PENDING_SECONDS = 600


async def _audit(
    db: GlobalDb, request: Request, caller: Caller, action: str, **details: object
) -> None:
    """Note a security change on the company the person is working in (if they are in one)."""
    company_id = caller.company_id
    if company_id is None:
        return
    await db.company_for_this_transaction(company_id)
    await record(
        db,
        AuditContext(
            company_id=company_id,
            actor_user_id=caller.user_id,
            ip=client_ip(request),
            user_agent=user_agent(request),
            request_id=str(getattr(request.state, "request_id", "")) or None,
        ),
        action,
        entity_type="user",
        entity_id=caller.user_id,
        after=dict(details) or None,
    )


async def _me(db: GlobalDb, auth: Auth, token: str) -> MeResponse:
    """Describe a session that was just created or rotated."""
    data = await auth.sessions.get(token)
    if data is None:
        raise unauthenticated()
    user = (await db.execute(select(User).where(User.id == uuid.UUID(data.user_id)))).scalar_one()
    return await accounts.build_me(db, Caller(token=token, session=data, user=user))


def _cookie(auth: Auth, response: Response, token: str, expires_at_iso: str) -> None:
    from datetime import datetime

    set_session_cookie(response, auth.settings, token, datetime.fromisoformat(expires_at_iso))


async def _login_response(
    db: GlobalDb, auth: Auth, response: Response, outcome: LoginOutcome
) -> LoginResponse:
    _cookie(auth, response, outcome.token, outcome.session.expires_at)
    me = await _me(db, auth, outcome.token)
    return LoginResponse(
        mfa_required=outcome.mfa_challenge,
        company_selection_required=me.active_company_id is None and len(me.companies) > 1,
        me=None if outcome.mfa_challenge else me,
    )


# --- account -------------------------------------------------------------------------------


@router.post("/signup", status_code=202, summary="Create a company and its first admin")
async def signup(body: SignupRequest, request: Request, db: GlobalDb, auth: Auth) -> Accepted:
    await accounts.sign_up(db, auth, body, ip=client_ip(request))
    return Accepted()


@router.post("/verify-email", summary="Confirm an e-mail address and sign in")
async def verify_email(
    body: TokenRequest, request: Request, response: Response, db: GlobalDb, auth: Auth
) -> LoginResponse:
    row = await accounts.consume_email_token(db, body.token, "verify")
    user = (await db.execute(select(User).where(User.id == row.user_id))).scalar_one()
    user.email_verified_at = user.email_verified_at or utcnow()
    outcome = await auth.auth.open_session(
        db, user, ip=client_ip(request), user_agent=user_agent(request)
    )
    await db.commit()
    return await _login_response(db, auth, response, outcome)


@router.post("/resend-verification", status_code=202, summary="Send the verification e-mail again")
async def resend_verification(
    body: EmailRequest, request: Request, db: GlobalDb, auth: Auth
) -> Accepted:
    await accounts.check_turnstile(auth, body.turnstile_token, client_ip(request))
    await accounts.resend_verification(db, auth, str(body.email), ip=client_ip(request))
    return Accepted()


@router.post("/login", summary="Sign in with an e-mail address and password")
async def login(
    body: LoginRequest, request: Request, response: Response, db: GlobalDb, auth: Auth
) -> LoginResponse:
    ip = client_ip(request)
    email = str(body.email)
    if await auth.auth.failure_count(email) >= TURNSTILE_AFTER_FAILURES:
        await accounts.check_turnstile(auth, body.turnstile_token, ip)
    try:
        outcome = await auth.auth.login(
            db, email=email, password=body.password, ip=ip, user_agent=user_agent(request)
        )
    except (InvalidCredentialsError, RateLimitedError):
        await db.commit()  # keep the failure count and any lock
        raise
    await db.commit()
    return await _login_response(db, auth, response, outcome)


@router.post("/logout", status_code=204, summary="Sign out")
async def logout(response: Response, db: GlobalDb, auth: Auth, caller: SessionCaller) -> None:
    await auth.sessions.revoke(db, caller.token, caller.session)
    await db.commit()
    clear_session_cookie(response, auth.settings)


@router.get("/me", summary="Who is signed in, and where they stand")
async def me(db: GlobalDb, caller: SessionCaller) -> MeResponse:
    return await accounts.build_me(db, caller)


# --- passwords -----------------------------------------------------------------------------


@router.post("/forgot-password", status_code=202, summary="E-mail a password reset link")
async def forgot_password(
    body: EmailRequest, request: Request, db: GlobalDb, auth: Auth
) -> Accepted:
    await accounts.forgot_password(
        db, auth, str(body.email), body.turnstile_token, ip=client_ip(request)
    )
    return Accepted()


@router.post(
    "/reset-password", status_code=204, summary="Choose a new password from an e-mailed link"
)
async def reset_password(body: ResetPasswordRequest, db: GlobalDb, auth: Auth) -> None:
    await accounts.reset_password(db, auth, body.token, body.new_password)


@router.post("/change-password", summary="Change your password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: GlobalDb,
    auth: Auth,
    caller: SignedIn,
) -> MeResponse:
    from app.modules.auth.passwords import hash_password, verify_password

    user = caller.user
    if not user.password_hash or not verify_password(user.password_hash, body.current_password):
        raise AppError(
            "INVALID_CREDENTIALS",
            "Your current password is not right.",
            status_code=401,
            field="current_password",
        )
    await accounts.check_password(body.new_password, field="new_password")
    user.password_hash = hash_password(body.new_password)
    user.requires_password_change = False
    await auth.sessions.revoke_all(db, user.id, except_session_id=caller.session.session_id)
    await _audit(db, request, caller, "auth.password.changed")
    token, data = await auth.sessions.rotate(
        db, caller.token, caller.session, ip=client_ip(request), user_agent=user_agent(request)
    )
    await db.commit()
    _cookie(auth, response, token, data.expires_at)
    await auth.mailer.send_template(
        to=str(user.email), template="password_changed", data={"first_name": user.first_name}
    )
    return await _me(db, auth, token)


# --- two-step verification -----------------------------------------------------------------


@router.post("/mfa/setup", summary="Start setting up an authenticator app")
async def mfa_setup(auth: Auth, caller: SignedIn) -> MfaSetupResponse:
    if caller.user.mfa_enabled:
        raise ConflictError("Two-step verification is already on.")
    secret = generate_secret()
    await auth.redis.set(f"mfa:pending:{caller.user_id}", secret, ex=_MFA_PENDING_SECONDS)
    return MfaSetupResponse(
        secret=secret,
        otpauth_uri=provisioning_uri(secret, str(caller.user.email), auth.settings.brand_name),
    )


@router.post("/mfa/verify", summary="Finish setting up an authenticator app")
async def mfa_verify(
    body: CodeRequest,
    request: Request,
    response: Response,
    db: GlobalDb,
    auth: Auth,
    caller: SignedIn,
) -> RecoveryCodesResponse:
    secret = await auth.redis.get(f"mfa:pending:{caller.user_id}")
    if secret is None:
        raise AppError(
            "MFA_SETUP_EXPIRED", "That setup has timed out. Start again.", status_code=400
        )
    codes = await auth.auth.confirm_mfa_enrolment(caller.user, str(secret), body.code)
    await auth.redis.delete(f"mfa:pending:{caller.user_id}")
    await _audit(db, request, caller, "auth.mfa.enabled")
    token, data = await auth.sessions.rotate(
        db,
        caller.token,
        caller.session,
        mfa_passed=True,
        ip=client_ip(request),
        user_agent=user_agent(request),
    )
    await db.commit()
    _cookie(auth, response, token, data.expires_at)
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post(
    "/mfa/challenge", summary="Give the code from your authenticator app to finish signing in"
)
async def mfa_challenge(
    body: CodeRequest,
    request: Request,
    response: Response,
    db: GlobalDb,
    auth: Auth,
    caller: SessionCaller,
) -> MeResponse:
    try:
        token, data = await auth.auth.complete_mfa(
            db,
            token=caller.token,
            data=caller.session,
            code=body.code,
            ip=client_ip(request),
            user_agent=user_agent(request),
        )
    except AppError:
        await db.commit()  # a used recovery code or a spent attempt is kept
        raise
    await db.commit()
    _cookie(auth, response, token, data.expires_at)
    return await _me(db, auth, token)


async def _policy_requires_mfa(db: GlobalDb, caller: Caller) -> bool:
    from app.modules.identity.models import PlatformAdmin

    platform_admin = (
        await db.execute(select(PlatformAdmin.id).where(PlatformAdmin.user_id == caller.user_id))
    ).first() is not None
    if platform_admin:
        return True
    rows = (
        await db.execute(
            select(Company.mfa_policy, Membership.role)
            .join(Membership, Membership.company_id == Company.id)
            .where(Membership.user_id == caller.user_id, Membership.status == "active")
        )
    ).all()
    return any(mfa_required(policy=policy, role=role) for policy, role in rows)


@router.post("/mfa/disable", status_code=204, summary="Turn two-step verification off")
async def mfa_disable(request: Request, db: GlobalDb, auth: Auth, caller: SignedIn) -> None:
    require_step_up(caller.session)
    if await _policy_requires_mfa(db, caller):
        raise ForbiddenError(
            "Your company requires two-step verification, so it cannot be turned off."
        )
    auth.auth.disable_mfa(caller.user)
    await _audit(db, request, caller, "auth.mfa.disabled")
    await db.commit()


@router.post("/mfa/recovery-codes", summary="Make a new set of recovery codes")
async def mfa_recovery_codes(db: GlobalDb, auth: Auth, caller: SignedIn) -> RecoveryCodesResponse:
    require_step_up(caller.session)
    if not caller.user.mfa_enabled:
        raise ConflictError("Turn on two-step verification first.")
    codes = auth.auth.regenerate_recovery_codes(caller.user)
    await db.commit()
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post("/step-up", summary="Confirm it is you again, for a sensitive action")
async def step_up(
    body: StepUpRequest, response: Response, db: GlobalDb, auth: Auth, caller: SignedIn
) -> MeResponse:
    if (body.password is None) == (body.code is None):
        raise AppError(
            "BAD_REQUEST", "Give either your password or a code.", status_code=422, field="password"
        )
    try:
        data = await auth.auth.step_up(
            db, token=caller.token, data=caller.session, password=body.password, code=body.code
        )
    except AppError:
        await db.commit()
        raise
    await db.commit()
    return await accounts.build_me(db, Caller(caller.token, data, caller.user))


# --- terms, invitations, company -----------------------------------------------------------


@router.post("/accept-terms", status_code=204, summary="Accept the current terms")
async def accept_terms(
    body: AcceptTermsRequest, request: Request, db: GlobalDb, caller: SignedIn
) -> None:
    terms = await accounts.current_terms(db)
    if body.version != terms.version:
        raise AppError(
            "TERMS_OUT_OF_DATE",
            "These terms have been replaced. Reload to read the new ones.",
            status_code=409,
            field="version",
        )
    already = (
        await db.execute(
            select(TermsAcceptance.id).where(
                TermsAcceptance.user_id == caller.user_id, TermsAcceptance.version == terms.version
            )
        )
    ).first()
    if already is None:
        db.add(
            TermsAcceptance(user_id=caller.user_id, version=terms.version, ip=client_ip(request))
        )
        await db.commit()


@router.get("/invitations/{token}", summary="See what an invitation is for")
async def invitation(token: str, db: GlobalDb) -> InvitationDetails:
    company, email, role, expires_at, has_account = await accounts.invitation_details(db, token)
    return InvitationDetails(
        company_name=company,
        email=email,
        role=role,  # type: ignore[arg-type]
        expires_at=expires_at,
        has_account=has_account,
    )


@router.post("/invitations/{token}/accept", summary="Accept an invitation")
async def accept_invitation_endpoint(
    token: str,
    body: AcceptInvitationRequest,
    request: Request,
    response: Response,
    db: GlobalDb,
    auth: Auth,
) -> LoginResponse:
    user = await accounts.accept_invite(
        db,
        auth,
        token,
        first_name=body.first_name,
        last_name=body.last_name,
        password=body.password,
        accept_terms=body.accept_terms,
        ip=client_ip(request),
    )
    if user is None:  # they already had an account: they sign in as usual
        return LoginResponse(mfa_required=False, company_selection_required=False, me=None)
    outcome = await auth.auth.open_session(
        db, user, ip=client_ip(request), user_agent=user_agent(request)
    )
    await db.commit()
    return await _login_response(db, auth, response, outcome)


@router.post("/switch-company", summary="Change the company you are working in")
async def switch_company(
    body: SwitchCompanyRequest,
    request: Request,
    response: Response,
    db: GlobalDb,
    auth: Auth,
    caller: SignedIn,
) -> MeResponse:
    membership = (
        await db.execute(
            select(Membership.id)
            .join(Company, Company.id == Membership.company_id)
            .where(
                Membership.user_id == caller.user_id,
                Membership.company_id == body.company_id,
                Membership.status == "active",
                Company.status == "active",
            )
        )
    ).first()
    if membership is None:  # also what someone else's company looks like
        raise AppError("NOT_FOUND", "We could not find that company.", status_code=404)
    token, data = await auth.sessions.rotate(
        db,
        caller.token,
        caller.session,
        change_company=True,
        company_id=body.company_id,
        ip=client_ip(request),
        user_agent=user_agent(request),
    )
    await db.commit()
    _cookie(auth, response, token, data.expires_at)
    return await _me(db, auth, token)
