"""User Access (plan.md 8.15): who in the company can sign in, with which role. The list, inviting,
changing a role, suspending and reactivating, and resetting someone's two-step verification. Linking
a user to an employee record comes with the employees themselves (Phase 6)."""

from __future__ import annotations

import uuid  # noqa: TC003  (FastAPI reads the annotations at run time)
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import ROLE_PERMISSIONS
from app.db.session import GlobalDb  # noqa: TC001
from app.modules.access.roles import groups_for
from app.modules.access.schemas import (
    AccessList,
    AccessUser,
    EmployeeLinkIn,
    InviteIn,
    Role,
    RoleIn,
    RoleMatrix,
    RoleSummary,
    Status,
    TwoStepPolicy,
    TwoStepPolicyIn,
)
from app.modules.audit.service import record as record_audit
from app.modules.auth.accounts import link
from app.modules.auth.deps import Auth  # noqa: TC001
from app.modules.auth.invitations import create_invitation, renew_invitation
from app.modules.auth.policy import mfa_required
from app.modules.auth.sessions import require_step_up
from app.modules.companies.models import Company
from app.modules.employees.models import Employee
from app.modules.identity.models import Invitation, Membership, PlatformAdmin, User
from app.modules.rbac.deps import Access, require
from app.modules.rbac.rules import (
    check_can_change_role,
    check_can_invite,
    ensure_company_keeps_an_admin,
)

router = APIRouter(tags=["access"])

Reads = Annotated[Access, Depends(require("rbac.user.read"))]
Invites = Annotated[Access, Depends(require("rbac.user.invite"))]
Assigns = Annotated[Access, Depends(require("rbac.role.assign"))]

ROLE_LABELS: dict[str, str] = {
    "company_admin": "Company Admin",
    "hr_admin": "HR Admin",
    "people_manager": "People Manager",
    "recruiter": "Recruiter",
    "employee": "Employee",
    "read_only_auditor": "Read-only Auditor",
}


# --- reading ------------------------------------------------------------------------------------


def _member(m: Membership, u: User, *, you: uuid.UUID) -> AccessUser:
    return AccessUser(
        id=m.id,
        user_id=u.id,
        first_name=u.first_name,
        last_name=u.last_name,
        email=u.email,
        role=m.role,  # type: ignore[arg-type]
        status=m.status,  # type: ignore[arg-type]
        two_step=u.mfa_enabled,
        employee_id=m.employee_id,
        last_login_at=u.last_login_at,
        invite_expires_at=None,
        is_you=u.id == you,
    )


def _invited(i: Invitation) -> AccessUser:
    return AccessUser(
        id=i.id,
        user_id=None,
        first_name=i.first_name or "",
        last_name=i.last_name or "",
        email=str(i.email),
        role=i.role,  # type: ignore[arg-type]
        status="invited",
        two_step=False,
        employee_id=None,
        last_login_at=None,
        invite_expires_at=i.expires_at,
        is_you=False,
    )


async def _people(access: Access, db: GlobalDb) -> list[AccessUser]:
    members = (
        await access.db.execute(select(Membership, User).join(User, User.id == Membership.user_id))
    ).all()
    pending = (
        (
            await db.execute(
                select(Invitation).where(
                    Invitation.company_id == access.company_id, Invitation.accepted_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    people = [_member(m, u, you=access.caller.user_id) for m, u in members]
    people += [_invited(i) for i in pending]
    return sorted(people, key=lambda p: (p.last_name.lower(), p.first_name.lower(), p.email))


@router.get("/users", response_model=AccessList)
async def list_users(
    access: Reads,
    db: GlobalDb,
    role: Annotated[Role | None, Query()] = None,
    status: Annotated[Status | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100, description="Name or e-mail contains.")] = None,
) -> AccessList:
    everyone = await _people(access, db)
    words = (q or "").lower().split()
    shown = [
        p
        for p in everyone
        if (role is None or p.role == role)
        and (status is None or p.status == status)
        and all(w in f"{p.first_name} {p.last_name} {p.email}".lower() for w in words)
    ]
    return AccessList(
        users=shown[:500],
        total=len(everyone),
        unlinked=sum(1 for p in everyone if p.status == "active" and p.employee_id is None),
    )


async def _target(access: Access, membership_id: uuid.UUID) -> tuple[Membership, User]:
    row = (
        await access.db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.id == membership_id)
        )
    ).first()
    if row is None:
        raise NotFoundError
    return row[0], row[1]


# --- inviting -----------------------------------------------------------------------------------


async def _send_invite(
    access: Access, db: GlobalDb, auth: Auth, invitation: Invitation, token: str
) -> None:
    company = (
        await db.execute(select(Company.name).where(Company.id == access.company_id))
    ).scalar_one()
    await auth.mailer.send_template(
        to=str(invitation.email),
        template="invite",
        data={
            "first_name": invitation.first_name or "there",
            "inviter_name": access.caller.user.first_name,
            "company_name": company,
            "role_label": ROLE_LABELS[invitation.role],
            "link": link(auth, "/accept-invite", token),
        },
    )


async def _pending(db: GlobalDb, company_id: uuid.UUID, **where: object) -> Invitation | None:
    query = select(Invitation).where(
        Invitation.company_id == company_id, Invitation.accepted_at.is_(None)
    )
    for column, value in where.items():
        query = query.where(getattr(Invitation, column) == value)
    return (await db.execute(query)).scalar_one_or_none()


@router.post("/users/invitations", status_code=201, response_model=AccessUser)
async def invite_user(body: InviteIn, access: Invites, db: GlobalDb, auth: Auth) -> AccessUser:
    check_can_invite(access.role, body.role)
    if body.role in {"company_admin", "hr_admin"}:
        require_step_up(access.caller.session)
    email = str(body.email).strip().lower()
    already = (
        await access.db.execute(
            select(Membership.id)
            .join(User, User.id == Membership.user_id)
            .where(User.email == email)
        )
    ).first()
    if already is not None:
        raise ConflictError("That person already has access to this company.")
    await db.scope_to_company(access.company_id)
    invitation = await _pending(db, access.company_id, email=email)
    if invitation is None:
        token, invitation = await create_invitation(
            db,
            company_id=access.company_id,
            email=email,
            role=body.role,
            invited_by=access.caller.user_id,
            first_name=body.first_name.strip(),
            last_name=body.last_name.strip(),
        )
    else:  # inviting the same address again sends a fresh link and keeps one invitation
        invitation.role, invitation.invited_by = body.role, access.caller.user_id
        invitation.first_name, invitation.last_name = (
            body.first_name.strip(),
            body.last_name.strip(),
        )
        token = await renew_invitation(db, invitation)
    await record_audit(
        db,
        access.audit_context,
        "user.invited",
        entity_type="invitation",
        entity_id=invitation.id,
        after={"email": email, "role": body.role},
    )
    await db.commit()
    await _send_invite(access, db, auth, invitation, token)
    return _invited(invitation)


@router.post("/users/invitations/{invitation_id}/resend", response_model=AccessUser)
async def resend_invitation(
    invitation_id: uuid.UUID, access: Invites, db: GlobalDb, auth: Auth
) -> AccessUser:
    invitation = await _pending(db, access.company_id, id=invitation_id)
    if invitation is None:
        raise NotFoundError
    check_can_invite(access.role, invitation.role)
    if invitation.role in {"company_admin", "hr_admin"}:
        require_step_up(access.caller.session)
    await db.scope_to_company(access.company_id)
    token = await renew_invitation(db, invitation)
    await record_audit(
        db,
        access.audit_context,
        "user.invitation_resent",
        entity_type="invitation",
        entity_id=invitation.id,
        after={"email": str(invitation.email)},
    )
    await db.commit()
    await _send_invite(access, db, auth, invitation, token)
    return _invited(invitation)


@router.delete("/users/invitations/{invitation_id}", status_code=204)
async def cancel_invitation(invitation_id: uuid.UUID, access: Invites, db: GlobalDb) -> None:
    invitation = await _pending(db, access.company_id, id=invitation_id)
    if invitation is None:
        raise NotFoundError
    check_can_invite(access.role, invitation.role)
    await db.scope_to_company(access.company_id)
    await record_audit(
        db,
        access.audit_context,
        "user.invitation_cancelled",
        entity_type="invitation",
        entity_id=invitation.id,
        before={"email": str(invitation.email), "role": invitation.role},
    )
    await db.delete(invitation)
    await db.commit()


# --- changing someone's access ------------------------------------------------------------------


@router.patch("/users/{membership_id}/role", response_model=AccessUser)
async def change_role(membership_id: uuid.UUID, body: RoleIn, access: Assigns) -> AccessUser:
    member, user = await _target(access, membership_id)
    if body.role != member.role:
        require_step_up(access.caller.session)
        check_can_change_role(access.role, current_role=member.role, new_role=body.role)
        await ensure_company_keeps_an_admin(
            access.db, access.company_id, member.id, new_role=body.role
        )
        before, member.role = member.role, body.role
        await access.audit(
            "user.role_changed",
            entity_type="membership",
            entity_id=member.id,
            before={"role": before},
            after={"role": body.role},
            summary=f"{user.email}: {ROLE_LABELS[before]} to {ROLE_LABELS[body.role]}",
        )
        await access.db.commit()
    return _member(member, user, you=access.caller.user_id)


async def _set_status(
    access: Access, membership_id: uuid.UUID, *, to: str, action: str
) -> AccessUser:
    member, user = await _target(access, membership_id)
    check_can_change_role(access.role, current_role=member.role, new_role=member.role)
    if member.status == to:
        raise ConflictError(f"That person is already {to}.")
    if to == "suspended":
        if user.id == access.caller.user_id:
            raise ConflictError("You cannot suspend yourself.")
        await ensure_company_keeps_an_admin(
            access.db, access.company_id, member.id, new_status="suspended"
        )
    before, member.status = member.status, to
    await access.audit(
        action,
        entity_type="membership",
        entity_id=member.id,
        before={"status": before},
        after={"status": to},
        summary=str(user.email),
    )
    await access.db.commit()
    return _member(member, user, you=access.caller.user_id)


@router.post("/users/{membership_id}/suspend", response_model=AccessUser)
async def suspend_user(membership_id: uuid.UUID, access: Assigns) -> AccessUser:
    """They cannot do anything until reactivated: every request checks the membership."""
    return await _set_status(access, membership_id, to="suspended", action="user.suspended")


@router.post("/users/{membership_id}/reactivate", response_model=AccessUser)
async def reactivate_user(membership_id: uuid.UUID, access: Assigns) -> AccessUser:
    return await _set_status(access, membership_id, to="active", action="user.reactivated")


@router.post("/users/{membership_id}/reset-two-step", response_model=AccessUser)
async def reset_two_step(
    membership_id: uuid.UUID, access: Assigns, db: GlobalDb, auth: Auth
) -> AccessUser:
    """For someone who lost their phone. Needs the caller to have confirmed it is them just now. The
    person is signed out everywhere and sets two-step up again at their next sign-in."""
    require_step_up(access.caller.session)
    member, user = await _target(access, membership_id)
    check_can_change_role(access.role, current_role=member.role, new_role=member.role)
    if user.id == access.caller.user_id:
        raise ConflictError("Use your own security settings to change your two-step verification.")
    if not user.mfa_enabled:
        raise AppError(
            "NOTHING_TO_RESET", "They have not set up two-step verification.", status_code=409
        )
    # The account is the person's own, across every company (C6.1.2). One company's admin must
    # not take the second step off an account that also opens another company or the admin site.
    await db.act_as(user.id)
    elsewhere = (
        await db.execute(
            select(Membership.id).where(
                Membership.user_id == user.id, Membership.company_id != access.company_id
            )
        )
    ).first()
    staff = (
        await db.execute(select(PlatformAdmin.id).where(PlatformAdmin.user_id == user.id))
    ).first()
    await db.act_as(access.caller.user_id)
    if elsewhere is not None or staff is not None:
        raise ForbiddenError(
            "This person also has access elsewhere, so only they or support can reset their "
            "two-step verification."
        )
    company_name = (
        await access.db.execute(select(Company.name).where(Company.id == access.company_id))
    ).scalar_one()
    auth.auth.disable_mfa(user)
    await access.audit(
        "user.two_step_reset",
        entity_type="membership",
        entity_id=member.id,
        summary=str(user.email),
    )
    await access.db.commit()
    await auth.sessions.revoke_all(db, user.id)
    await db.commit()
    await auth.mailer.send_template(
        to=str(user.email),
        template="two_step_reset",
        data={"first_name": user.first_name, "company_name": company_name},
    )
    return _member(member, user, you=access.caller.user_id)


# --- the two-step policy and the role viewer ----------------------------------------------------


async def _policy(access: Access) -> TwoStepPolicy:
    policy = (
        await access.db.execute(select(Company.mfa_policy).where(Company.id == access.company_id))
    ).scalar_one()
    rows = (
        await access.db.execute(
            select(Membership.role, User.mfa_enabled)
            .join(User, User.id == Membership.user_id)
            .where(Membership.status == "active")
        )
    ).all()
    to_set_up = sum(
        1 for role, enrolled in rows if not enrolled and mfa_required(policy=policy, role=role)
    )
    return TwoStepPolicy(policy=policy, to_set_up=to_set_up)  # type: ignore[arg-type]


@router.get("/security/two-step", response_model=TwoStepPolicy)
async def read_two_step_policy(access: Reads) -> TwoStepPolicy:
    return await _policy(access)


@router.put("/security/two-step", response_model=TwoStepPolicy)
async def set_two_step_policy(body: TwoStepPolicyIn, access: Assigns) -> TwoStepPolicy:
    """Who must use two-step verification: nobody, Company Admins, or everyone. People it newly
    covers are asked to set it up on their next request."""
    company = (
        await access.db.execute(select(Company).where(Company.id == access.company_id))
    ).scalar_one()
    if company.mfa_policy != body.policy:
        require_step_up(access.caller.session)
        before, company.mfa_policy = company.mfa_policy, body.policy
        await access.audit(
            "company.mfa_policy_changed",
            entity_type="company",
            entity_id=company.id,
            before={"mfa_policy": before},
            after={"mfa_policy": body.policy},
        )
        await access.db.commit()
    return await _policy(access)


@router.get("/roles/matrix", response_model=RoleMatrix)
async def role_matrix(access: Reads) -> RoleMatrix:
    """Every role and, grouped by area, what it can do. Built from the permission matrix itself."""
    return RoleMatrix(
        roles=[
            RoleSummary.model_validate(
                {"role": role, "groups": groups_for(role), "total": len(ROLE_PERMISSIONS[role])}
            )
            for role in ROLE_LABELS
        ]
    )


@router.put("/users/{membership_id}/employee", response_model=AccessUser)
async def link_employee(
    membership_id: uuid.UUID, body: EmployeeLinkIn, access: Assigns
) -> AccessUser:
    """Linking controls self-service reach, so it needs the access-assignment permission."""
    target = (
        await access.db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.id == membership_id)
            .with_for_update(of=Membership)
        )
    ).first()
    if target is None:
        raise NotFoundError
    member, user = target
    if member.employee_id == body.employee_id:
        return _member(member, user, you=access.caller.user_id)
    if body.employee_id is not None:
        employee = (
            await access.db.execute(
                select(Employee)
                .where(Employee.id == body.employee_id, Employee.status != "archived")
                .with_for_update()
            )
        ).scalar_one_or_none()
        if employee is None:
            raise NotFoundError
        occupied = (
            await access.db.execute(
                select(Membership.id).where(
                    Membership.employee_id == employee.id, Membership.id != member.id
                )
            )
        ).first()
        if occupied:
            raise ConflictError(
                "That employee is already linked to another user.", field="employee_id"
            )
    before = member.employee_id
    if before != body.employee_id:
        member.employee_id = body.employee_id
        await access.audit(
            "user.employee_link_changed",
            entity_type="membership",
            entity_id=member.id,
            before={"employee_id": str(before) if before else None},
            after={"employee_id": str(body.employee_id) if body.employee_id else None},
        )
        for ident, action in (
            (before, "employee.user_unlinked"),
            (body.employee_id, "employee.user_linked"),
        ):
            if ident:
                await access.audit(
                    action,
                    entity_type="employee",
                    entity_id=ident,
                    after={"membership_id": str(member.id)},
                )
        await access.db.commit()
    return _member(member, user, you=access.caller.user_id)
