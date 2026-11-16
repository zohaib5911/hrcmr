"""T17.6: the platform audit log. Platform admins read the company-less trail (their own actions and
page views, and the job runs), filter it, and export it as CSV; the export is itself recorded. A
tenant event never appears here, and a company administrator reads none of it.

The rig gives two companies, "a" and "b", both active. The audit trail is append-only and is not
cleared between tests, so every test tells its own rows apart with a unique reason."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text

from tests.db.test_employee_documents import rig as rig
from tests.support import step_up

API = "/api/v1"


async def _platform_admin(rig: dict[str, Any], level: str) -> Any:
    """A signed-in company administrator made a platform admin at ``level``, with MFA, and the
    platform cookie started, as the admin pages need (T17.1)."""
    admin = await rig["person"]("company_admin", rig["a"])
    me = uuid.UUID((await admin.get(f"{API}/auth/me")).json()["user"]["id"])
    async with rig["owner"].begin() as c:
        await c.execute(
            text("insert into platform_admins (user_id, level) values (:u, :l)"),
            {"u": me, "l": level},
        )
        await c.execute(text("update users set mfa_enabled=true where id=:u"), {"u": me})
    await step_up(admin)
    started = await admin.post(f"{API}/auth/platform-session")
    assert started.status_code == 201, started.text
    return admin


async def _exports(rig: dict[str, Any]) -> int:
    async with rig["owner"].connect() as c:
        return int(
            (
                await c.execute(
                    text(
                        "select count(*) from audit_events where action = 'platform.audit_exported'"
                    )
                )
            ).scalar_one()
        )


async def _suspend(admin: Any, company: uuid.UUID, reason: str) -> None:
    suspended = await admin.post(
        f"{API}/platform/companies/{company}/suspend", json={"reason": reason}
    )
    assert suspended.status_code == 200, suspended.text


async def test_only_a_platform_admin_reads_or_exports_the_audit_log(rig: dict[str, Any]) -> None:
    company_admin = await rig["person"]("company_admin", rig["a"])
    assert (await company_admin.get(f"{API}/platform/audit")).status_code == 403
    assert (await company_admin.get(f"{API}/platform/audit/export")).status_code == 403


async def test_the_log_holds_platform_events_with_who_and_why_and_never_tenant_events(
    rig: dict[str, Any],
) -> None:
    tenant_note = f"Tenant only {uuid.uuid4().hex[:8]}"
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into audit_events (id, company_id, actor_type, action, entity_type, "
                "entity_id, summary) values (:i, :c, 'user', 'employee.created', 'employee', "
                ":e, :s)"
            ),
            {"i": uuid.uuid4(), "c": rig["a"], "e": uuid.uuid4(), "s": tenant_note},
        )
    admin = await _platform_admin(rig, "support")
    reason = f"Unpaid invoice {uuid.uuid4().hex[:8]}"
    await _suspend(admin, rig["b"], reason)
    found = (
        await admin.get(f"{API}/platform/audit?action=platform.company_suspended&limit=200")
    ).json()
    [row] = [item for item in found["items"] if item["reason"] == reason]
    assert "@" in row["actor"]
    assert row["actor_type"] == "platform_admin"
    everything = (await admin.get(f"{API}/platform/audit?limit=200")).json()
    assert tenant_note not in str(everything)
    family = (
        await admin.get(f"{API}/platform/audit?action=platform.&actor_type=platform_admin")
    ).json()
    assert family["total"] >= 2  # at least the suspension and its page view


async def test_the_export_is_csv_and_is_itself_recorded(rig: dict[str, Any]) -> None:
    admin = await _platform_admin(rig, "support")
    reason = f"Unpaid invoice {uuid.uuid4().hex[:8]}"
    await _suspend(admin, rig["b"], reason)
    before = await _exports(rig)
    exported = await admin.get(f"{API}/platform/audit/export?action=platform.company_suspended")
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("text/csv")
    lines = exported.text.lstrip("﻿").splitlines()
    assert lines[0].startswith("Time (UTC),Who,Action")
    assert [line for line in lines[1:] if reason in line], exported.text
    assert await _exports(rig) == before + 1  # the export is recorded, once
