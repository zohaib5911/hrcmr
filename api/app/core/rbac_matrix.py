"""The permission matrix (plan.md section 7): one source of truth, kept as data.

Every protected endpoint names the permission it needs (``require("employee.profile.read")``), and
this module says which roles hold it. ``GET /auth/me`` hands the active role's list to the web app,
which hides what a person cannot use; the API still checks every request itself.

Names follow ``area.thing.action``. The action may carry a scope:

* ``read``, ``write``, ...  the whole company;
* ``read_reports``          only the person's direct and indirect reports;
* ``read_own``              only the person's own record.

The matrix is built from the plan's own wording, in the same order, so a reviewer can lay the two
side by side: the permission list (7.1), each role's explicit grants, and the two roles the plan
describes by rule (HR Admin and Read-only Auditor).
"""

from __future__ import annotations

import re
from enum import StrEnum

# --- 7.1 The permission list ---------------------------------------------------------------------

_BASE = """
attendance.record.read attendance.record.read_own attendance.record.write
attendance.record.write_own
attendance.timesheet.approve_reports
company.department.read company.department.write company.location.read company.location.write
company.overview.read company.profile.read company.profile.write
document.file.read document.file.read_own document.file.write document.file.write_own
document.report.generate
employee.change_of_circumstances.read employee.change_of_circumstances.write
employee.compensation.read employee.compensation.write
employee.org_assignment.read employee.org_assignment.write
employee.profile.delete employee.profile.read employee.profile.read_own
employee.profile.read_reports employee.profile.write employee.profile.write_own
employee.rtw.correct employee.rtw.read employee.rtw.read_own employee.rtw.write
employee.sensitive_data.read employee.sensitive_data.read_own employee.sensitive_data.write
holiday.calendar.read holiday.calendar.write holiday.type.read holiday.type.write
learning.assignment.complete_own learning.assignment.read learning.assignment.read_own
learning.assignment.read_reports learning.assignment.write
learning.certificate.read learning.certificate.read_own learning.course.read
leave.accrual.write leave.balance.read leave.balance.read_own leave.balance.read_reports
leave.config.read leave.config.write
leave.request.approve leave.request.approve_reports leave.request.create leave.request.create_own
leave.request.read leave.request.read_own leave.type.read leave.type.write
organogram.level.read organogram.level.write
policy.acceptance.read_own policy.acceptance.write_own policy.document.read policy.document.write
rbac.role.assign rbac.user.invite rbac.user.read
recruitment.application.read recruitment.application.write
recruitment.candidate.convert recruitment.candidate.read recruitment.candidate.write
recruitment.interview.read recruitment.interview.write recruitment.offer.read
recruitment.offer.write
recruitment.pipeline_stage.write recruitment.posting.read recruitment.posting.write
recruitment.requisition.approve recruitment.requisition.read recruitment.requisition.write
rota.day_off.read rota.day_off.write rota.duty_roster.read rota.duty_roster.write
rota.duty_roster.write_reports rota.late_policy.read rota.late_policy.write
rota.scheduled_shift.read_own rota.shift.read rota.shift.write
settings.designation.read settings.designation.write settings.pay_band.read settings.pay_band.write
settings.payment_type.read settings.payment_type.write settings.pay_schedule.read
settings.pay_schedule.write settings.tax_code.read settings.tax_code.write
work_log.entry.correct work_log.entry.read work_log.entry.read_own work_log.entry.write_own
"""

# The permissions marked with a star in the plan.
_ADDED = """
compliance.overview.read compliance.reminder.send compliance.audit.read compliance.audit.export
soc.check.run soc.check.read ai.ask.use ai.letter.draft
billing.manage company.delete company.export
"""

BASE_PERMISSIONS: frozenset[str] = frozenset(_BASE.split())
ADDED_PERMISSIONS: frozenset[str] = frozenset(_ADDED.split())
PERMISSIONS: frozenset[str] = BASE_PERMISSIONS | ADDED_PERMISSIONS

_PERMISSION_NAME = re.compile(r"[a-z_]+(\.[a-z_]+){1,2}")
if not all(
    _PERMISSION_NAME.fullmatch(p) for p in PERMISSIONS
):  # pragma: no cover (import-time guard)
    raise RuntimeError("a permission name in the matrix is malformed")


class Role(StrEnum):
    COMPANY_ADMIN = "company_admin"
    HR_ADMIN = "hr_admin"
    PEOPLE_MANAGER = "people_manager"
    RECRUITER = "recruiter"
    EMPLOYEE = "employee"
    READ_ONLY_AUDITOR = "read_only_auditor"


ROLES: tuple[str, ...] = tuple(role.value for role in Role)


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


def _plain(action: str) -> frozenset[str]:
    """Every permission whose action is exactly ``read`` or ``write``: company-wide, not scoped."""
    return frozenset(p for p in PERMISSIONS if p.endswith(f".{action}"))


# --- 7.2 Role grants -----------------------------------------------------------------------------

_HR_ADMIN_ADDED = _words(
    """
    employee.profile.delete leave.request.approve rbac.user.invite document.report.generate
    learning.assignment.complete_own policy.acceptance.read_own policy.acceptance.write_own
    rota.scheduled_shift.read_own
    compliance.overview.read compliance.reminder.send compliance.audit.read
    soc.check.run soc.check.read ai.ask.use ai.letter.draft
    """
)
_HR_ADMIN_NOT = _words(
    """
    company.profile.write rbac.role.assign employee.rtw.correct work_log.entry.correct
    attendance.timesheet.approve_reports billing.manage company.delete company.export
    """
)
HR_ADMIN: frozenset[str] = (
    _plain("read")
    | _plain("write")
    | frozenset(p for p in PERMISSIONS if p.startswith("recruitment."))  # incl. approve, convert
    | _HR_ADMIN_ADDED
) - _HR_ADMIN_NOT

PEOPLE_MANAGER: frozenset[str] = _words(
    """
    attendance.record.read attendance.timesheet.approve_reports company.department.read
    company.location.read company.overview.read employee.profile.read_reports holiday.calendar.read
    learning.assignment.complete_own learning.assignment.read_own learning.assignment.read_reports
    learning.certificate.read_own learning.course.read leave.balance.read_reports
    leave.request.approve_reports organogram.level.read policy.acceptance.read_own
    policy.acceptance.write_own recruitment.application.read recruitment.candidate.read
    recruitment.interview.read recruitment.interview.write recruitment.posting.read
    recruitment.requisition.read recruitment.requisition.write rota.day_off.read
    rota.duty_roster.read rota.duty_roster.write_reports rota.late_policy.read
    rota.scheduled_shift.read_own rota.shift.read settings.designation.read ai.ask.use
    """
)

RECRUITER: frozenset[str] = (
    _words(
        """
        company.department.read company.location.read company.overview.read
        settings.designation.read soc.check.run soc.check.read
        """
    )
    | frozenset(p for p in PERMISSIONS if p.startswith("recruitment."))
) - {"recruitment.requisition.approve"}

# `attendance.record.write_own` is granted for clocking in and out only; the attendance endpoints
# accept nothing else from an employee. `employee.profile.write_own` covers contact details,
# address and emergency contacts only, and the profile endpoint enforces that field list.
EMPLOYEE: frozenset[str] = _words(
    """
    attendance.record.read_own attendance.record.write_own company.overview.read
    document.file.read_own document.file.write_own employee.profile.read_own
    employee.profile.write_own employee.rtw.read_own employee.sensitive_data.read_own
    holiday.calendar.read learning.assignment.complete_own learning.assignment.read_own
    learning.certificate.read_own learning.course.read leave.balance.read_own
    leave.request.create_own leave.request.read_own leave.type.read policy.acceptance.read_own
    policy.acceptance.write_own rota.scheduled_shift.read_own work_log.entry.read_own
    work_log.entry.write_own ai.ask.use
    """
)

# Every company-wide read in these areas, and nothing that writes, reveals sensitive data or
# uses AI.
_AUDITOR_AREAS = (
    "company.",
    "employee.",
    "holiday.",
    "learning.",
    "leave.",
    "organogram.",
    "policy.document.",
    "rbac.user.",
    "recruitment.",
    "rota.",
    "settings.",
    "work_log.",
)
READ_ONLY_AUDITOR: frozenset[str] = frozenset(
    p for p in _plain("read") if p.startswith(_AUDITOR_AREAS)
) - {"employee.sensitive_data.read"} | _words(
    "compliance.overview.read compliance.audit.read compliance.audit.export soc.check.read"
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    Role.COMPANY_ADMIN: PERMISSIONS,
    Role.HR_ADMIN: HR_ADMIN,
    Role.PEOPLE_MANAGER: PEOPLE_MANAGER,
    Role.RECRUITER: RECRUITER,
    Role.EMPLOYEE: EMPLOYEE,
    Role.READ_ONLY_AUDITOR: READ_ONLY_AUDITOR,
}

# Platform Admins (our own staff) have a separate permission set on a separate API (plan 7.2). It is
# never mixed with the tenant roles above.
PLATFORM_PERMISSIONS: frozenset[str] = _words(
    """
    platform.companies.read platform.companies.write platform.billing.refund
    platform.impersonate platform.rules.publish platform.content.write platform.jobs.run
    platform.audit.read
    """
)


def permissions_for(role: str | None) -> frozenset[str]:
    return ROLE_PERMISSIONS.get(role or "", frozenset())


def has_permission(role: str | None, permission: str) -> bool:
    return permission in permissions_for(role)


class Scope(StrEnum):
    """How much of the company a permission reaches for a given role."""

    ALL = "all"
    REPORTS = "reports"
    OWN = "own"


def scope_for(role: str | None, permission: str) -> Scope | None:
    """The widest reach ``role`` has for an action, or None if it has none.

    Ask with the whole-company name (``employee.profile.read``); the ``_reports`` and ``_own``
    variants are found from it. ``require`` uses this, and an endpoint then limits what it returns.
    """
    granted = permissions_for(role)
    if permission in granted:
        if permission.endswith("_own"):
            return Scope.OWN
        return Scope.REPORTS if permission.endswith("_reports") else Scope.ALL
    if f"{permission}_reports" in granted:
        return Scope.REPORTS
    if f"{permission}_own" in granted:
        return Scope.OWN
    return None
