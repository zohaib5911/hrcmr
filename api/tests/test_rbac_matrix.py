"""The permission matrix against the plan's own wording (section 7)."""

from __future__ import annotations

import pytest

from app.core.rbac_matrix import (
    ADDED_PERMISSIONS,
    BASE_PERMISSIONS,
    HR_ADMIN,
    PEOPLE_MANAGER,
    PERMISSIONS,
    PLATFORM_PERMISSIONS,
    READ_ONLY_AUDITOR,
    RECRUITER,
    ROLE_PERMISSIONS,
    ROLES,
    Scope,
    has_permission,
    scope_for,
)


def words(text: str) -> set[str]:
    return set(text.split())


def test_the_list_has_109_permissions_plus_the_11_new_ones() -> None:
    assert len(BASE_PERMISSIONS) == 109
    assert len(ADDED_PERMISSIONS) == 11
    assert not BASE_PERMISSIONS & ADDED_PERMISSIONS
    assert len(PERMISSIONS) == 120


def test_there_are_six_tenant_roles_and_platform_permissions_are_kept_apart() -> None:
    assert set(ROLES) == {
        "company_admin",
        "hr_admin",
        "people_manager",
        "recruiter",
        "employee",
        "read_only_auditor",
    }
    assert all(perms <= PERMISSIONS for perms in ROLE_PERMISSIONS.values())
    assert not PLATFORM_PERMISSIONS & PERMISSIONS


def test_a_company_admin_can_do_everything() -> None:
    assert ROLE_PERMISSIONS["company_admin"] == PERMISSIONS


# Copied from the plan's role grants, so a change to the matrix has to be a deliberate edit here too.
PLAN_PEOPLE_MANAGER = words(
    """attendance.record.read attendance.timesheet.approve_reports company.department.read
    company.location.read company.overview.read employee.profile.read_reports holiday.calendar.read
    learning.assignment.complete_own learning.assignment.read_own learning.assignment.read_reports
    learning.certificate.read_own learning.course.read leave.balance.read_reports
    leave.request.approve_reports organogram.level.read policy.acceptance.read_own
    policy.acceptance.write_own recruitment.application.read recruitment.candidate.read
    recruitment.interview.read recruitment.interview.write recruitment.posting.read
    recruitment.requisition.read recruitment.requisition.write rota.day_off.read
    rota.duty_roster.read rota.duty_roster.write_reports rota.late_policy.read
    rota.scheduled_shift.read_own rota.shift.read settings.designation.read ai.ask.use"""
)
PLAN_RECRUITER = words(
    """company.department.read company.location.read company.overview.read
    recruitment.application.read recruitment.application.write recruitment.candidate.convert
    recruitment.candidate.read recruitment.candidate.write recruitment.interview.read
    recruitment.interview.write recruitment.offer.read recruitment.offer.write
    recruitment.pipeline_stage.write recruitment.posting.read recruitment.posting.write
    recruitment.requisition.read recruitment.requisition.write settings.designation.read
    soc.check.run soc.check.read"""
)
PLAN_EMPLOYEE = words(
    """attendance.record.read_own attendance.record.write_own company.overview.read
    document.file.read_own document.file.write_own employee.profile.read_own
    employee.profile.write_own employee.rtw.read_own employee.sensitive_data.read_own
    holiday.calendar.read learning.assignment.complete_own learning.assignment.read_own
    learning.certificate.read_own learning.course.read leave.balance.read_own
    leave.request.create_own leave.request.read_own leave.type.read policy.acceptance.read_own
    policy.acceptance.write_own rota.scheduled_shift.read_own work_log.entry.read_own
    work_log.entry.write_own ai.ask.use"""
)


def test_the_roles_the_plan_lists_exactly_hold_exactly_those_permissions() -> None:
    assert set(PEOPLE_MANAGER) == PLAN_PEOPLE_MANAGER
    assert set(RECRUITER) == PLAN_RECRUITER
    assert set(ROLE_PERMISSIONS["employee"]) == PLAN_EMPLOYEE


def test_an_hr_admin_has_the_company_wide_reads_and_writes_except_the_eight_the_plan_names() -> (
    None
):
    must_not = words(
        """company.profile.write rbac.role.assign employee.rtw.correct work_log.entry.correct
        attendance.timesheet.approve_reports billing.manage company.delete company.export"""
    )
    assert not HR_ADMIN & must_not
    must = words(
        """employee.profile.delete employee.sensitive_data.read employee.sensitive_data.write
        employee.rtw.read employee.rtw.write employee.change_of_circumstances.read
        employee.change_of_circumstances.write employee.compensation.read employee.compensation.write
        employee.org_assignment.read employee.org_assignment.write leave.request.approve
        leave.accrual.write recruitment.requisition.approve recruitment.candidate.convert
        rbac.user.invite rbac.user.read document.report.generate work_log.entry.read
        learning.assignment.complete_own policy.acceptance.read_own policy.acceptance.write_own
        rota.scheduled_shift.read_own compliance.overview.read compliance.reminder.send
        compliance.audit.read soc.check.run soc.check.read ai.ask.use ai.letter.draft
        company.department.write holiday.calendar.write settings.tax_code.write"""
    )
    assert must <= HR_ADMIN
    # Apart from the four own-record permissions listed, an HR Admin holds no scoped permission.
    scoped = {p for p in HR_ADMIN if p.endswith(("_own", "_reports"))}
    assert scoped == {
        "learning.assignment.complete_own",
        "policy.acceptance.read_own",
        "policy.acceptance.write_own",
        "rota.scheduled_shift.read_own",
    }
    assert "compliance.audit.export" not in HR_ADMIN


def test_a_recruiter_cannot_approve_a_requisition() -> None:
    assert not has_permission("recruiter", "recruitment.requisition.approve")
    assert has_permission("recruiter", "recruitment.candidate.convert")


def test_a_read_only_auditor_reads_and_never_writes_reveals_or_asks_the_ai() -> None:
    assert not any(
        p.endswith(".write") or "_own" in p or "_reports" in p for p in READ_ONLY_AUDITOR
    )
    assert not any(
        p.endswith((".write", ".delete", ".approve", ".send", ".run")) for p in READ_ONLY_AUDITOR
    )
    assert "employee.sensitive_data.read" not in READ_ONLY_AUDITOR
    assert not any(p.startswith("ai.") for p in READ_ONLY_AUDITOR)
    assert (
        words(
            """employee.compensation.read employee.rtw.read employee.change_of_circumstances.read
        employee.org_assignment.read compliance.overview.read compliance.audit.read
        compliance.audit.export soc.check.read rbac.user.read work_log.entry.read
        leave.config.read leave.request.read leave.type.read policy.document.read
        recruitment.offer.read rota.shift.read settings.pay_band.read holiday.type.read
        organogram.level.read learning.certificate.read company.profile.read"""
        )
        <= READ_ONLY_AUDITOR
    )
    # Not in the plan's list of areas: attendance and documents.
    assert "attendance.record.read" not in READ_ONLY_AUDITOR
    assert "document.file.read" not in READ_ONLY_AUDITOR


@pytest.mark.parametrize(
    ("role", "permission", "scope"),
    [
        ("company_admin", "employee.profile.read", Scope.ALL),
        ("hr_admin", "employee.profile.read", Scope.ALL),
        ("people_manager", "employee.profile.read", Scope.REPORTS),
        ("employee", "employee.profile.read", Scope.OWN),
        ("recruiter", "employee.profile.read", None),
        ("employee", "leave.request.create", Scope.OWN),
        ("people_manager", "leave.request.approve", Scope.REPORTS),
        ("hr_admin", "leave.request.approve", Scope.ALL),
        ("people_manager", "attendance.timesheet.approve_reports", Scope.REPORTS),
        ("employee", "work_log.entry.read_own", Scope.OWN),
        ("nobody", "employee.profile.read", None),
        (None, "employee.profile.read", None),
    ],
)
def test_the_scope_a_role_has_for_an_action(
    role: str | None, permission: str, scope: Scope | None
) -> None:
    assert scope_for(role, permission) is scope
