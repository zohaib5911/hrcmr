"""T7.6: own compliance messages, unread state and permission-gated live attention."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text

from tests.db.test_compliance_hub import _employee
from tests.db.test_compliance_hub import rig as rig

API = "/api/v1"


async def test_bell_messages_and_read_state_are_own_and_company_scoped(rig: dict[str, Any]) -> None:
    own = await rig["person"]("employee", rig["a"])
    admin = await rig["person"]("company_admin", rig["a"])
    other = await rig["person"]("employee", rig["a"])
    own_id = uuid.UUID((await own.get(API + "/auth/me")).json()["user"]["id"])
    other_id = uuid.UUID((await other.get(API + "/auth/me")).json()["user"]["id"])
    own_messages = [uuid.uuid4() for _ in range(25)]
    foreign_message = uuid.uuid4()
    other_message = uuid.uuid4()
    async with rig["owner"].begin() as c:
        for ident in own_messages:
            await c.execute(
                text(
                    "insert into notifications (id,company_id,user_id,kind,title,body,link) values (:i,:c,:u,'compliance.reminder_received','Passport reminder','Please review your message','/my-documents')"
                ),
                {"i": ident, "c": rig["a"], "u": own_id},
            )
        for ident, company, user in (
            (foreign_message, rig["b"], own_id),
            (other_message, rig["a"], other_id),
        ):
            await c.execute(
                text(
                    "insert into notifications (id,company_id,user_id,kind,title,body) values (:i,:c,:u,'compliance.reminder_received','Private recipient message','Not for this caller')"
                ),
                {"i": ident, "c": company, "u": user},
            )
        # An old admin notice must disappear after a role loses overview access.
        await c.execute(
            text(
                "insert into notifications (company_id,user_id,kind,title) values (:c,:u,'compliance.reminders_due','Private company notice')"
            ),
            {"c": rig["a"], "u": own_id},
        )
    emp = await _employee(rig, rig["a"], "Missing")
    admin_feed = await admin.get(API + "/notifications")
    assert admin_feed.status_code == 200, admin_feed.text
    assert admin_feed.json()["attention_count"] == 1
    assert admin_feed.json()["needs_attention"][0]["href"] == f"/employees/{emp}?tab=rtw"
    assert admin_feed.json()["items"] == []
    feed = await own.get(API + "/notifications", params={"limit": 1})
    assert feed.status_code == 200, feed.text
    first = feed.json()
    assert first["unread"] == 25
    assert first["attention_count"] == 0
    assert first["needs_attention"] == []
    assert "Private" not in feed.text
    second = (
        await own.get(API + "/notifications", params={"cursor": first["next_cursor"], "limit": 1})
    ).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]
    for ident in (other_message, foreign_message, uuid.uuid4()):
        assert (
            await own.patch(f"{API}/notifications/{ident}", json={"read": True})
        ).status_code == 404
    marked = await own.patch(f"{API}/notifications/{own_messages[0]}", json={"read": True})
    assert marked.status_code == 200, marked.text
    assert marked.json()["read_at"] is not None
    assert (await own.get(API + "/notifications")).json()["unread"] == 24
    assert (await own.post(API + "/notifications/read-all")).json() == {"marked": 24}
    assert (await own.post(API + "/notifications/read-all")).json() == {"marked": 0}
    assert (await own.get(API + "/notifications")).json()["unread"] == 0
    assert (
        await own.patch(f"{API}/notifications/{own_messages[0]}", json={"read": False})
    ).status_code == 422
    async with rig["owner"].connect() as c:
        unchanged = (
            await c.execute(
                text("select count(*) from notifications where id in (:o,:f) and read_at is null"),
                {"o": other_message, "f": foreign_message},
            )
        ).scalar_one()
        assert unchanged == 2
    for role in ("hr_admin", "read_only_auditor"):
        client = await rig["person"](role, rig["a"])
        assert (await client.get(API + "/notifications")).json()["attention_count"] == 1
    for role in ("people_manager", "recruiter"):
        client = await rig["person"](role, rig["a"])
        assert (await client.get(API + "/notifications")).json()["attention_count"] == 0
