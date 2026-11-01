"""When is two-step verification required (plan.md 4.2)?

* Platform Admins: always. It cannot be turned off.
* A company can require it of nobody (``optional``), of its Company Admins (``admins``) or of every
  user (``all``).
* A person who has set it up is asked for a code on every sign-in, whatever the policy says.
"""

from __future__ import annotations

from enum import StrEnum

from app.core.errors import AppError

COMPANY_ADMIN_ROLE = "company_admin"


class MfaState(StrEnum):
    NOT_REQUIRED = "not_required"
    CHALLENGE = "challenge"  # set up, but not yet proved in this session
    ENROL = "enrol"  # required, but not set up yet


def mfa_required(*, policy: str, role: str | None, platform_admin: bool = False) -> bool:
    if platform_admin or policy == "all":
        return True
    return policy == "admins" and role == COMPANY_ADMIN_ROLE


def mfa_state(
    *, enrolled: bool, passed: bool, policy: str, role: str | None, platform_admin: bool = False
) -> MfaState:
    if enrolled:
        return MfaState.NOT_REQUIRED if passed else MfaState.CHALLENGE
    required = mfa_required(policy=policy, role=role, platform_admin=platform_admin)
    return MfaState.ENROL if required else MfaState.NOT_REQUIRED


class MfaRequiredError(AppError):
    def __init__(self, state: MfaState) -> None:
        enrol = state is MfaState.ENROL
        super().__init__(
            "MFA_ENROLMENT_REQUIRED" if enrol else "MFA_REQUIRED",
            "Set up two-step verification to continue."
            if enrol
            else "Enter the code from your authenticator app to continue.",
            status_code=403,
        )


def require_mfa_satisfied(state: MfaState) -> None:
    """Raise unless the session may go on: used on every request that needs a company."""
    if state is not MfaState.NOT_REQUIRED:
        raise MfaRequiredError(state)
