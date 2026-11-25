"""T14.2 notifications: a person never sees another person's notices; personal notices reach everyone;
e-mail preferences save and validate; the daily digest is sent once per notice."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import text

from app.core.crypto import KeyRing, set_keyring
from app.jobs.notifications import reconcile_digests
from tests.db.test_employee_documents import rig as rig
from tests.db.test_leave_requests import BASE, linked
from tests.db.test_leave_requests import ready as ready
from tests.db.test_leave_settings import seeded as seeded
from tests.db.test_reminders import _keys as _keys

API = "/api/v1"
ROTA = "/api/v1/rota"


async def _me(client: Any) -> dict[str, Any]:
    """The signed-in person, from the sign-in profile (open to every role, unlike the user list)."""
    user = (await client.get(API + "/auth/me")).json()["user"]
    return {"user_id": str(user["id"])}


async def _notice(
    rig: dict[str, Any], user_id: str, company: uuid.UUID, kind: str, title: str
) -> str:
    ident = uuid.uuid4()
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into notifications (id, company_id, user_id, kind, title) "
                "values (:i, :c, :u, :k, :t)"
            ),
            {"i": ident, "c": company, "u": user_id, "k": kind, "t": title},
        )
    return str(ident)


async def test_a_person_never_sees_another_persons_notices(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    employee = await rig["person"]("employee", rig["a"])
    other_company = await rig["person"]("company_admin", rig["b"])
    admin_user = (await _me(admin))["user_id"]
    employee_user = (await _me(employee))["user_id"]
    mine = await _notice(rig, employee_user, rig["a"], "learning.overdue", "Only mine")
    await _notice(rig, admin_user, rig["a"], "learning.overdue", "Not for the employee")

    shown = (await employee.get(API + "/notifications")).json()["items"]
    assert [item["id"] for item in shown] == [mine]
    assert "Not for the employee" not in (await employee.get(API + "/notifications")).text

    other = await admin.patch(API + f"/notifications/{mine}", json={"read": True})
    assert other.status_code == 404, other.text
    assert (await other_company.get(API + "/notifications")).json()["items"] == []


async def test_personal_notices_reach_every_role_including_employees(rig: dict[str, Any]) -> None:
    employee = await rig["person"]("employee", rig["a"])
    employee_user = (await _me(employee))["user_id"]
    policy = await _notice(rig, employee_user, rig["a"], "policy.assigned", "Please read a policy")
    rota = await _notice(rig, employee_user, rig["a"], "rota.published", "Your rota is out")
    shown = {item["id"] for item in (await employee.get(API + "/notifications")).json()["items"]}
    assert {policy, rota} <= shown


async def test_preferences_default_to_immediate_save_and_refuse_nonsense(
    rig: dict[str, Any],
) -> None:
    employee = await rig["person"]("employee", rig["a"])
    assert (await employee.get(API + "/me/notification-preferences")).json() == {
        "mode": "immediate"
    }
    saved = await employee.put(API + "/me/notification-preferences", json={"mode": "daily"})
    assert saved.status_code == 200, saved.text
    assert (await employee.get(API + "/me/notification-preferences")).json() == {"mode": "daily"}
    assert (
        await employee.put(API + "/me/notification-preferences", json={"mode": "weekly"})
    ).status_code == 422


async def test_the_daily_digest_is_sent_once_per_notice(rig: dict[str, Any]) -> None:
    employee = await rig["person"]("employee", rig["a"])
    me = await _me(employee)
    await employee.put(API + "/me/notification-preferences", json={"mode": "daily"})
    await _notice(rig, me["user_id"], rig["a"], "learning.overdue", "One")
    await _notice(rig, me["user_id"], rig["a"], "rota.published", "Two")
    async with rig["owner"].connect() as c:
        email = (
            await c.execute(text("select email from users where id = :u"), {"u": me["user_id"]})
        ).scalar_one()

    # A digest only goes to a verified address, so the test person has verified theirs.
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update users set email_verified_at = now() where id = :u"), {"u": me["user_id"]}
        )
    # The notices were just written, so the digest runs at the present moment, as the daily job does.
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    try:
        now = datetime.now(UTC)
        first = await reconcile_digests(rig["owner"], "http://web.test", now=now)
    finally:
        set_keyring(None)
    assert first >= 1
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    try:
        second = await reconcile_digests(rig["owner"], "http://web.test", now=now)
    finally:
        set_keyring(None)
    assert second == 0  # nothing new: the notices were marked as digested
    async with rig["owner"].connect() as c:
        sent = (
            await c.execute(
                text(
                    "select count(*) from email_outbox where to_address = :e "
                    "and template = 'notifications_digest'"
                ),
                {"e": email},
            )
        ).scalar_one()
        waiting = (
            await c.execute(
                text(
                    "select count(*) from notifications where user_id = :u and digested_at is null"
                ),
                {"u": me["user_id"]},
            )
        ).scalar_one()
    assert sent == 1
    assert waiting == 0


async def _delivery(
    ready: dict[str, Any], user_id: str, kind: str, template: str
) -> tuple[int, int]:
    """(in-app notices, e-mails queued to that person's address) for one kind of notice."""
    async with ready["owner"].connect() as c:
        notices = (
            await c.execute(
                text("select count(*) from notifications where user_id = :u and kind = :k"),
                {"u": user_id, "k": kind},
            )
        ).scalar_one()
        emails = (
            await c.execute(
                text(
                    "select count(*) from email_outbox where template = :t "
                    "and to_address = (select email from users where id = :u)"
                ),
                {"t": template, "u": user_id},
            )
        ).scalar_one()
    return int(notices), int(emails)


@pytest.mark.parametrize("mode", ["off", "daily"])
async def test_leave_decision_e_mail_follows_the_preference(
    ready: dict[str, Any], mode: str
) -> None:
    quiet = await linked(ready, "employee", ready["employee"])
    plain = await linked(ready, "employee", ready["other"])
    quiet_user = (await _me(quiet))["user_id"]
    plain_user = (await _me(plain))["user_id"]
    saved = await quiet.put(API + "/me/notification-preferences", json={"mode": mode})
    assert saved.status_code == 200, saved.text
    body = {"leave_type_id": ready["annual"], "start_date": "2026-01-05", "end_date": "2026-01-09"}
    for client in (quiet, plain):
        made = await client.post(BASE + "/requests/own", json=body)
        assert made.status_code == 201, made.text
        decided = await ready["admin"].post(
            BASE + f"/requests/{made.json()['id']}/approve", json={"note": "Approved"}
        )
        assert decided.status_code == 200, decided.text
    # The in-app notice always goes; the e-mail goes only to a person on "immediate".
    assert await _delivery(ready, quiet_user, "leave.decision", "leave_decision") == (1, 0)
    assert await _delivery(ready, plain_user, "leave.decision", "leave_decision") == (1, 1)


@pytest.mark.parametrize("mode", ["off", "daily"])
async def test_rota_publish_e_mail_follows_the_preference(ready: dict[str, Any], mode: str) -> None:
    admin = ready["admin"]
    quiet = await linked(ready, "employee", ready["employee"])
    plain = await linked(ready, "employee", ready["other"])
    quiet_user = (await _me(quiet))["user_id"]
    plain_user = (await _me(plain))["user_id"]
    saved = await quiet.put(API + "/me/notification-preferences", json={"mode": mode})
    assert saved.status_code == 200, saved.text
    for version, employee in enumerate((ready["employee"], ready["other"])):
        made = await admin.post(
            ROTA + "/scheduled-shifts",
            json={
                "employee_id": str(employee),
                "date": "2026-01-05",
                "starts_at": "09:00",
                "ends_at": "17:00",
                "version": version,
            },
        )
        assert made.status_code == 201, made.text
    published = await admin.post(ROTA + "/weeks/2026-01-05/publish", json={"version": 2})
    assert published.status_code == 200, published.text
    assert await _delivery(ready, quiet_user, "rota.published", "rota_published") == (1, 0)
    assert await _delivery(ready, plain_user, "rota.published", "rota_published") == (1, 1)


async def test_a_suspended_member_gets_no_digest_for_that_company_only(
    rig: dict[str, Any],
) -> None:
    """ISS-08: the suspended membership stops company A's digest; company B's still goes."""
    employee = await rig["person"]("employee", rig["a"])
    me = await _me(employee)
    await employee.put(API + "/me/notification-preferences", json={"mode": "daily"})
    await _notice(rig, me["user_id"], rig["a"], "learning.overdue", "A notice")
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update users set email_verified_at = now() where id = :u"), {"u": me["user_id"]}
        )
        await c.execute(
            text(
                "update memberships set status = 'suspended' where user_id = :u and company_id = :c"
            ),
            {"u": me["user_id"], "c": rig["a"]},
        )
        await c.execute(
            text(
                "insert into memberships (user_id, company_id, role, status) "
                "values (:u, :c, 'employee', 'active')"
            ),
            {"u": me["user_id"], "c": rig["b"]},
        )
        await c.execute(
            text(
                "insert into notification_preferences (user_id, company_id, mode) "
                "values (:u, :c, 'daily')"
            ),
            {"u": me["user_id"], "c": rig["b"]},
        )
    await _notice(rig, me["user_id"], rig["b"], "learning.overdue", "B notice")
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    try:
        await reconcile_digests(rig["owner"], "http://web.test", now=datetime.now(UTC))
    finally:
        set_keyring(None)
    async with rig["owner"].connect() as c:
        rows = dict(
            (
                await c.execute(
                    text(
                        "select company_id, count(*) filter (where digested_at is null) "
                        "from notifications where user_id = :u group by company_id"
                    ),
                    {"u": me["user_id"]},
                )
            ).all()
        )
        sent = (
            await c.execute(
                text(
                    "select count(*) from email_outbox o join users u on u.email = o.to_address "
                    "where u.id = :u and o.template = 'notifications_digest'"
                ),
                {"u": me["user_id"]},
            )
        ).scalar_one()
    assert rows[rig["a"]] == 1  # A's notice is not digested: no digest for company A
    assert rows[rig["b"]] == 0  # B's was
    assert sent == 1


async def test_payment_and_deletion_notices_reach_the_bell_of_those_who_may_act(
    rig: dict[str, Any],
) -> None:
    """ISS-15: the three account notices are listed, counted and can be marked read."""
    admin = await rig["person"]("company_admin", rig["a"])
    employee = await rig["person"]("employee", rig["a"])
    admin_user = (await _me(admin))["user_id"]
    employee_user = (await _me(employee))["user_id"]
    kinds = ("billing.payment_failed", "account.deletion_scheduled", "account.deletion_withdrawn")
    ids = [await _notice(rig, admin_user, rig["a"], kind, kind) for kind in kinds]
    for kind in kinds:  # the same kinds for someone who may not act on them
        await _notice(rig, employee_user, rig["a"], kind, kind)

    feed = (await admin.get(API + "/notifications")).json()
    assert set(ids) <= {item["id"] for item in feed["items"]}
    assert feed["unread"] >= 3
    read = await admin.patch(API + f"/notifications/{ids[0]}", json={"read": True})
    assert read.status_code == 200, read.text
    assert (await admin.post(API + "/notifications/read-all")).status_code in (200, 204)
    after = (await admin.get(API + "/notifications")).json()
    assert after["unread"] == 0

    hidden = (await employee.get(API + "/notifications")).json()
    assert not {item["kind"] for item in hidden["items"]} & set(kinds)
