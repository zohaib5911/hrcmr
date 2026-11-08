"""T17.3: support mode. A platform admin opens a company with a reason and a ticket reference and,
for 30 minutes, sees it in the tenant app as its administrator does. It is read-only until an
owner-level admin turns changes on with a second confirmation. The company's audit trail records
each step; the admin's own tenant session comes back when support mode ends or runs out.

The platform admin is a company administrator of "a"; support mode opens "b"."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from tests.db.test_employee_documents import rig as rig
from tests.db.test_platform_admin import _platform_admin

API = "/api/v1"
START = {"reason": "Customer cannot see their rota", "ticket_ref": "SUP-1042"}


async def _start(admin: Any, company: uuid.UUID) -> dict[str, Any]:
    started = await admin.post(f"{API}/platform/companies/{company}/impersonate", json=START)
    assert started.status_code == 201, started.text
    body: dict[str, Any] = started.json()
    return body


async def _company_audit(rig: dict[str, Any], company: uuid.UUID) -> list[tuple[Any, ...]]:
    async with rig["owner"].connect() as c:
        rows = await c.execute(
            text(
                "select action, actor_type, reason, impersonation_session_id from audit_events "
                "where company_id = :c and (action like 'support.%' or action like 'department.%') "
                "order by created_at"
            ),
            {"c": company},
        )
        return [tuple(row) for row in rows.all()]


async def test_only_a_platform_admin_starts_it_and_a_reason_and_ticket_are_required(
    rig: dict[str, Any],
) -> None:
    company_admin = await rig["person"]("company_admin", rig["a"])
    path = f"{API}/platform/companies/{rig['b']}/impersonate"
    assert (await company_admin.post(path, json=START)).status_code == 403

    admin, _ = await _platform_admin(rig, "support")
    assert (await admin.post(path, json={"ticket_ref": "SUP-1"})).status_code == 422
    assert (await admin.post(path, json={**START, "ticket_ref": ""})).status_code == 422
    assert (await admin.post(path, json={**START, "reason": "no"})).status_code == 422
    missing = await admin.post(f"{API}/platform/companies/{uuid.uuid4()}/impersonate", json=START)
    assert missing.status_code == 404


async def test_support_mode_is_read_only_and_the_company_sees_it(rig: dict[str, Any]) -> None:
    admin, me = await _platform_admin(rig, "support")
    before = await rig["person"]("company_admin", rig["b"])  # gives "b" an administrator
    del before
    session = await _start(admin, rig["b"])
    assert session["write_enabled"] is False
    expires = datetime.fromisoformat(session["expires_at"])
    assert timedelta(minutes=29) < expires - datetime.now(UTC) <= timedelta(minutes=30)

    whoami = (await admin.get(f"{API}/auth/me")).json()
    assert whoami["active_company_id"] == str(rig["b"])
    assert whoami["role"] == "company_admin"
    assert [c["company_id"] for c in whoami["companies"]] == [str(rig["b"])]
    assert whoami["support"]["id"] == session["id"]
    assert whoami["support"]["company_name"] == "Company b"
    assert whoami["support"]["ticket_ref"] == "SUP-1042"
    assert whoami["support"]["write_enabled"] is False

    # Company "b"'s data is readable; nothing can be changed, on company or account routes.
    assert (await admin.get(f"{API}/departments")).status_code == 200
    blocked = await admin.post(f"{API}/departments", json={"name": "Support made"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "SUPPORT_READ_ONLY"
    for path in ("/auth/logout", "/auth/switch-company", "/auth/mfa/disable"):
        refused = await admin.post(f"{API}{path}", json={})
        assert refused.status_code == 403, path
        assert refused.json()["error"]["code"] == "SUPPORT_READ_ONLY", path

    # The company's own audit trail shows who looked, why, under which session.
    assert await _company_audit(rig, rig["b"]) == [
        ("support.session.started", "platform_admin", START["reason"], uuid.UUID(session["id"]))
    ]
    async with rig["owner"].connect() as c:
        row = (
            await c.execute(
                text(
                    "select started_by, ticket_ref, ended_at from impersonation_sessions "
                    "where id = :i"
                ),
                {"i": session["id"]},
            )
        ).one()
    assert (row.started_by, row.ticket_ref, row.ended_at) == (me, "SUP-1042", None)

    # The platform's company page lists it too (the platform cookie is still separate).
    detail = (await admin.get(f"{API}/platform/companies/{rig['b']}")).json()
    assert detail["events"][0]["action"] == "platform.support_started"


async def test_only_an_owner_turns_changes_on_with_a_confirmation(rig: dict[str, Any]) -> None:
    support, _ = await _platform_admin(rig, "support")
    owner, _ = await _platform_admin(rig, "owner")
    theirs = await _start(support, rig["b"])
    mine = await _start(owner, rig["b"])
    on = {"enabled": True, "confirm": True}

    refused = await support.post(f"{API}/platform/impersonation/{theirs['id']}/writes", json=on)
    assert refused.status_code == 403
    not_own = await owner.post(f"{API}/platform/impersonation/{theirs['id']}/writes", json=on)
    assert not_own.status_code == 403
    unconfirmed = await owner.post(
        f"{API}/platform/impersonation/{mine['id']}/writes", json={"enabled": True}
    )
    assert unconfirmed.status_code == 422
    assert unconfirmed.json()["error"]["code"] == "CONFIRMATION_REQUIRED"

    enabled = await owner.post(f"{API}/platform/impersonation/{mine['id']}/writes", json=on)
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["write_enabled"] is True
    assert (await owner.get(f"{API}/auth/me")).json()["support"]["write_enabled"] is True

    made = await owner.post(f"{API}/departments", json={"name": "Support made"})
    assert made.status_code == 201, made.text
    # Account routes stay closed even with changes on: they would change the admin's own account.
    assert (await owner.post(f"{API}/auth/logout", json={})).status_code == 403

    off = await owner.post(
        f"{API}/platform/impersonation/{mine['id']}/writes", json={"enabled": False}
    )
    assert off.json()["write_enabled"] is False
    again = await owner.post(f"{API}/departments", json={"name": "Second"})
    assert again.json()["error"]["code"] == "SUPPORT_READ_ONLY"

    events = await _company_audit(rig, rig["b"])
    session = uuid.UUID(mine["id"])
    assert ("support.session.writes_changed", "platform_admin", None, session) in events
    # The change itself is the platform admin's, marked with the support session.
    assert ("department.created", "platform_admin", None, session) in events


async def test_ending_or_running_out_brings_back_the_admins_own_company(
    rig: dict[str, Any],
) -> None:
    admin, _ = await _platform_admin(rig, "support")
    first = await _start(admin, rig["b"])

    # Run out: the 30 minutes pass. Reading falls back to the admin's own company ("a"); a change
    # is refused so it cannot land in "a" by mistake.
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update impersonation_sessions set expires_at = :t where id = :i"),
            {"t": datetime.now(UTC) - timedelta(seconds=1), "i": first["id"]},
        )
    whoami = (await admin.get(f"{API}/auth/me")).json()
    assert whoami["support"] is None
    assert whoami["active_company_id"] == str(rig["a"])
    late = await admin.post(f"{API}/departments", json={"name": "Late form"})
    assert late.status_code == 401
    assert late.json()["error"]["code"] == "SUPPORT_SESSION_ENDED"

    # The banner's button clears the cookie; the admin works in "a" again.
    assert (await admin.delete(f"{API}/auth/support-session")).status_code == 204
    assert (await admin.post(f"{API}/departments", json={"name": "Own"})).status_code == 201

    # Ending a live one from the tenant side records it for the company.
    second = await _start(admin, rig["b"])
    assert (await admin.get(f"{API}/auth/me")).json()["support"]["id"] == second["id"]
    assert (await admin.delete(f"{API}/auth/support-session")).status_code == 204
    assert (await admin.get(f"{API}/auth/me")).json()["support"] is None

    # Ending from the admin side stops it at once, even for a browser that kept the cookie.
    third = await _start(admin, rig["b"])
    kept = admin.cookies.get("brand_support_session")
    ended = await admin.post(f"{API}/platform/impersonation/{third['id']}/end")
    assert ended.status_code == 200, ended.text
    assert ended.json()["ended_at"] is not None
    admin.cookies.set("brand_support_session", kept)
    assert (await admin.get(f"{API}/auth/me")).json()["support"] is None

    actions = [event[0] for event in await _company_audit(rig, rig["b"])]
    assert actions == [
        "support.session.started",
        "support.session.started",
        "support.session.ended",
        "support.session.started",
        "support.session.ended",
    ]


async def test_a_new_support_session_ends_the_admins_previous_one(rig: dict[str, Any]) -> None:
    admin, _ = await _platform_admin(rig, "support")
    first = await _start(admin, rig["b"])
    second = await _start(admin, rig["a"])
    async with rig["owner"].connect() as c:
        ended = (
            await c.execute(
                text("select ended_at is not null from impersonation_sessions where id = :i"),
                {"i": first["id"]},
            )
        ).scalar_one()
    assert ended is True
    assert (await admin.get(f"{API}/auth/me")).json()["support"]["id"] == second["id"]
