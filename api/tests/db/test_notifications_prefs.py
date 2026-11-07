"""T14.2 notifications: a person never sees another person's notices; personal notices reach everyone;
e-mail preferences save and validate; the daily digest is sent once per notice."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from app.core.crypto import KeyRing, set_keyring
from app.jobs.notifications import reconcile_digests
from tests.db.test_employee_documents import rig as rig

API = "/api/v1"


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
