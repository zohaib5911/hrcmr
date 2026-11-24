"""T5.1: the User Access list: who may read it, the role and status filters, search, the unlinked
count, and that another company's people never appear."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.main import create_app
from app.modules.auth.sessions import SessionStore
from tests.db.api_support import sign_in_as, two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings, csrf_ready

API = "/api/v1"


class Mail:
    """Records the e-mails the app asks for."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, dict[str, str]]] = []

    async def send_template(self, *, to: str, template: str, data: dict[str, str]) -> None:
        self.sent.append((to, template, data))

    def invites(self, to: str) -> list[dict[str, str]]:
        return [d for t, name, d in self.sent if name == "invite" and t == to]


@pytest.fixture(autouse=True)
def _keys() -> Iterator[None]:
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    yield
    set_keyring(None)


@pytest.fixture
async def rig(database: DatabaseUnderTest) -> AsyncIterator[dict[str, Any]]:
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()
    a, b = await two_companies(database)
    owner = engine_for(database.owner_url, poolclass=NullPool)
    mail = Mail()
    app = create_app(
        build_settings(database_url=database.app_url, redis_url=TEST_REDIS_URL), mailer=mail
    )
    sessions = SessionStore(redis)
    clients: list[httpx.AsyncClient] = []

    async def person(role: str, company: uuid.UUID) -> httpx.AsyncClient:
        client = await sign_in_as(database, sessions, app, role, company)
        clients.append(client)
        return client

    async with LifespanManager(app):
        yield {
            "person": person,
            "a": a,
            "b": b,
            "owner": owner,
            "mail": mail,
            "sessions": sessions,
            "app": app,
        }
    for client in clients:
        await client.aclose()
    await owner.dispose()
    await redis.flushdb()
    await redis.aclose()


async def test_concurrent_admin_demotions_keep_one_admin(rig: dict[str, Any]) -> None:
    admins = [await rig["person"]("company_admin", rig["a"]) for _ in range(2)]
    urls: list[str] = []
    for admin in admins:
        token = admin.cookies.get("brand_session")
        data = await rig["sessions"].get(token)
        await rig["sessions"].mark_step_up(token, data)
        users = (await admin.get(f"{API}/users")).json()["users"]
        membership = next(user["id"] for user in users if user["is_you"])
        urls.append(f"{API}/users/{membership}/role")
    results = await asyncio.gather(
        *(
            admin.patch(url, json={"role": "hr_admin"})
            for admin, url in zip(admins, urls, strict=True)
        )
    )
    assert sorted(result.status_code for result in results) == [200, 409]
    async with rig["owner"].connect() as db:
        count = await db.scalar(
            text(
                "select count(*) from memberships where company_id=:c and role='company_admin' "
                "and status='active'"
            ),
            {"c": rig["a"]},
        )
    assert count == 1


async def test_the_list_filters_and_counts_unlinked_users(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    await rig["person"]("hr_admin", rig["a"])
    await rig["person"]("employee", rig["a"])
    await rig["person"]("company_admin", rig["b"])  # another company: never listed

    everyone = (await admin.get(f"{API}/users")).json()
    assert everyone["total"] == 3
    assert everyone["unlinked"] == 3  # no employee records exist yet
    assert sorted(u["role"] for u in everyone["users"]) == ["company_admin", "employee", "hr_admin"]
    assert [u["is_you"] for u in everyone["users"]].count(True) == 1
    first = everyone["users"][0]
    assert set(first) >= {"two_step", "employee_id", "status", "email", "last_login_at"}
    assert "password_hash" not in str(everyone)
    assert "mfa_secret" not in str(everyone)

    only_hr = (await admin.get(f"{API}/users", params={"role": "hr_admin"})).json()
    assert [u["role"] for u in only_hr["users"]] == ["hr_admin"]
    assert only_hr["total"] == 3  # the counts ignore the filters

    async with rig["owner"].begin() as c:
        await c.execute(text("update memberships set status = 'suspended' where role = 'employee'"))
        employee = uuid.uuid4()
        await c.execute(
            text(
                "insert into employees (id, company_id, employee_number, first_name, last_name, "
                "email, hire_date) values (:e, :c, 'E1', 'Hazel', 'Admin', 'h@example.com', "
                "'2025-01-06')"
            ),
            {"e": employee, "c": rig["a"]},
        )
        await c.execute(
            text("update memberships set employee_id = :e where role = 'hr_admin'"),
            {"e": employee},
        )
    suspended = (await admin.get(f"{API}/users", params={"status": "suspended"})).json()
    assert [u["role"] for u in suspended["users"]] == ["employee"]
    after = (await admin.get(f"{API}/users")).json()
    assert after["unlinked"] == 1  # only the admin: the HR admin is linked, the employee suspended

    found = (await admin.get(f"{API}/users", params={"q": "hr_admin"})).json()
    assert [u["role"] for u in found["users"]] == ["hr_admin"]
    assert (await admin.get(f"{API}/users", params={"q": "%"})).json()["users"] == []
    assert (await admin.get(f"{API}/users", params={"role": "boss"})).status_code == 422


async def test_only_the_roles_that_hold_the_permission_may_read_the_list(
    rig: dict[str, Any],
) -> None:
    for role, allowed in (
        ("company_admin", True),
        ("hr_admin", True),
        ("read_only_auditor", True),
        ("people_manager", False),
        ("recruiter", False),
        ("employee", False),
    ):
        person = await rig["person"](role, rig["a"])
        assert (await person.get(f"{API}/users")).status_code == (200 if allowed else 403), role
    assert (
        await (await rig["person"]("employee", rig["a"])).get(f"{API}/users")
    ).status_code == 403


def _row(listing: dict[str, Any], **match: Any) -> dict[str, Any]:
    (found,) = [u for u in listing["users"] if all(u[k] == v for k, v in match.items())]
    row: dict[str, Any] = found
    return row


async def _audit_actions(rig: dict[str, Any], prefix: str = "user.") -> list[str]:
    async with rig["owner"].connect() as c:
        rows = await c.execute(
            text(
                "select action from audit_events where company_id = :c "
                "and action like :p order by created_at"
            ),
            {"c": rig["a"], "p": prefix + "%"},
        )
        return [r[0] for r in rows]


INVITE = {
    "first_name": "Nia",
    "last_name": "Clarke",
    "email": "Nia@Example.com",
    "role": "recruiter",
}


async def test_an_invitation_is_listed_resent_cancelled_and_accepted(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    made = await admin.post(f"{API}/users/invitations", json=INVITE)
    assert made.status_code == 201, made.text
    invited = made.json()
    assert (invited["status"], invited["email"], invited["user_id"]) == (
        "invited",
        "nia@example.com",
        None,
    )
    (mail,) = rig["mail"].invites("nia@example.com")
    assert mail["first_name"] == "Nia"
    assert mail["role_label"] == "Recruiter"
    first_token = mail["link"].split("token=", 1)[1]

    listing = (await admin.get(f"{API}/users")).json()
    assert _row(listing, status="invited")["id"] == invited["id"]
    assert listing["unlinked"] == 1  # the invited person is not counted until they join

    # Inviting the same address again keeps one invitation, with a new link; the old one dies.
    again = await admin.post(f"{API}/users/invitations", json={**INVITE, "role": "employee"})
    assert again.json()["id"] == invited["id"]
    assert again.json()["role"] == "employee"
    second_token = rig["mail"].invites("nia@example.com")[-1]["link"].split("token=", 1)[1]
    assert second_token != first_token
    assert (await admin.get(f"{API}/auth/invitations/{first_token}")).status_code == 410

    resent = await admin.post(f"{API}/users/invitations/{invited['id']}/resend")
    assert resent.status_code == 200
    third_token = rig["mail"].invites("nia@example.com")[-1]["link"].split("token=", 1)[1]
    assert third_token not in (first_token, second_token)

    # Accepting it makes a member; the list shows them as active with the invited role.
    newcomer = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=rig["app"], raise_app_exceptions=False),
        base_url="http://test",
    )
    csrf_ready(newcomer, rig["app"])
    accepted = await newcomer.post(
        f"{API}/auth/invitations/{third_token}/accept",
        json={
            "first_name": "Nia",
            "last_name": "Clarke",
            "password": "violet teapot ledger orchard 91",
            "accept_terms": True,
        },
    )
    await newcomer.aclose()
    assert accepted.status_code == 200, accepted.text
    after = (await admin.get(f"{API}/users")).json()
    assert _row(after, email="nia@example.com")["status"] == "active"
    assert after["total"] == 2

    cancelled = await admin.post(
        f"{API}/users/invitations", json={**INVITE, "email": "ola@example.com"}
    )
    assert (
        await admin.delete(f"{API}/users/invitations/{cancelled.json()['id']}")
    ).status_code == 204
    assert (await admin.get(f"{API}/users", params={"status": "invited"})).json()["users"] == []

    assert {"user.invited", "user.invitation_resent", "user.invitation_cancelled"} <= set(
        await _audit_actions(rig)
    )


async def test_who_may_invite_and_whom(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    hr = await rig["person"]("hr_admin", rig["a"])
    manager = await rig["person"]("people_manager", rig["a"])
    assert (await manager.post(f"{API}/users/invitations", json=INVITE)).status_code == 403
    assert (
        await hr.post(f"{API}/users/invitations", json={**INVITE, "role": "company_admin"})
    ).status_code == 403
    assert (await hr.post(f"{API}/users/invitations", json=INVITE)).status_code == 201
    await _confirm(rig, admin)
    assert (
        await admin.post(f"{API}/users/invitations", json={**INVITE, "role": "company_admin"})
    ).status_code == 201
    listing = (await admin.get(f"{API}/users")).json()
    existing = _row(listing, role="people_manager")
    taken = await admin.post(
        f"{API}/users/invitations", json={**INVITE, "email": existing["email"]}
    )
    assert taken.status_code == 409
    bad = {**INVITE, "email": "not-an-address"}
    assert (await admin.post(f"{API}/users/invitations", json=bad)).status_code == 422
    assert (
        await admin.post(f"{API}/users/invitations", json={**INVITE, "surprise": 1})
    ).status_code == 422
    other = await rig["person"]("company_admin", rig["b"])
    assert (await other.get(f"{API}/users")).json()["users"][0]["status"] == "active"
    assert (await other.get(f"{API}/users")).json()[
        "total"
    ] == 1  # company A's invitations stay in A


async def test_role_changes_and_the_last_admin_rule(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    hr = await rig["person"]("hr_admin", rig["a"])
    await rig["person"]("employee", rig["a"])
    listing = (await admin.get(f"{API}/users")).json()
    me, hr_row, emp = (_row(listing, role=r) for r in ("company_admin", "hr_admin", "employee"))

    # Only a Company Admin assigns roles; an HR Admin invites but cannot change anyone's role.
    assert (
        await hr.patch(f"{API}/users/{emp['id']}/role", json={"role": "recruiter"})
    ).status_code == 403
    await _confirm(rig, admin)
    # The only Company Admin cannot step down.
    stepping_down = await admin.patch(f"{API}/users/{me['id']}/role", json={"role": "hr_admin"})
    assert stepping_down.status_code == 409
    changed = await admin.patch(f"{API}/users/{emp['id']}/role", json={"role": "recruiter"})
    assert changed.status_code == 200
    assert changed.json()["role"] == "recruiter"
    # With a second Company Admin the first may step down, and then has no say in roles any more.
    promoted = await admin.patch(f"{API}/users/{hr_row['id']}/role", json={"role": "company_admin"})
    assert promoted.status_code == 200
    assert (
        await admin.patch(f"{API}/users/{me['id']}/role", json={"role": "hr_admin"})
    ).status_code == 200
    assert (
        await admin.patch(f"{API}/users/{emp['id']}/role", json={"role": "employee"})
    ).status_code == 403
    assert (await admin.get(f"{API}/users")).status_code == 200  # an HR Admin may still read
    await _confirm(rig, hr)
    assert (
        await hr.patch(f"{API}/users/{uuid.uuid4()}/role", json={"role": "employee"})
    ).status_code == 404
    assert "user.role_changed" in await _audit_actions(rig)


async def test_suspend_and_reactivate(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    worker = await rig["person"]("employee", rig["a"])
    listing = (await admin.get(f"{API}/users")).json()
    me, them = _row(listing, role="company_admin"), _row(listing, role="employee")

    assert (await admin.post(f"{API}/users/{me['id']}/suspend")).status_code == 409  # yourself
    assert (await worker.get(f"{API}/users")).status_code == 403  # an employee has no access
    suspended = await admin.post(f"{API}/users/{them['id']}/suspend")
    assert suspended.json()["status"] == "suspended"
    assert (await admin.post(f"{API}/users/{them['id']}/suspend")).status_code == 409
    blocked = await worker.get(f"{API}/company")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "ACCOUNT_SUSPENDED"
    assert (await admin.post(f"{API}/users/{them['id']}/reactivate")).json()["status"] == "active"
    assert (await worker.get(f"{API}/company")).status_code == 200
    assert {"user.suspended", "user.reactivated"} <= set(await _audit_actions(rig))


async def test_resetting_two_step_needs_a_recent_confirmation(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    phone_lost = await rig["person"]("employee", rig["a"])
    them = _row((await admin.get(f"{API}/users")).json(), role="employee")
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "update users set mfa_enabled = true, recovery_codes_hash = '{abc}' where id = :u"
            ),
            {"u": them["user_id"]},
        )

    refused = await admin.post(f"{API}/users/{them['id']}/reset-two-step")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "STEP_UP_REQUIRED"

    token = admin.cookies.get("brand_session")
    data = await rig["sessions"].get(token)
    await rig["sessions"].mark_step_up(token, data)
    done = await admin.post(f"{API}/users/{them['id']}/reset-two-step")
    assert done.status_code == 200, done.text
    assert done.json()["two_step"] is False
    async with rig["owner"].connect() as c:
        row = (
            await c.execute(
                text("select mfa_enabled, mfa_secret, recovery_codes_hash from users where id=:u"),
                {"u": them["user_id"]},
            )
        ).one()
    assert (row[0], row[1], list(row[2])) == (False, None, [])
    assert (await phone_lost.get(f"{API}/company")).status_code == 401  # signed out everywhere
    assert (await admin.post(f"{API}/users/{them['id']}/reset-two-step")).status_code == 409
    assert "user.two_step_reset" in await _audit_actions(rig)
    told = [d for _, name, d in rig["mail"].sent if name == "two_step_reset"]
    assert len(told) == 1  # the person is told: a reset is never silent
    assert told[0]["company_name"]


@pytest.mark.parametrize("elsewhere", ["second_company", "platform_admin"])
async def test_two_step_is_not_reset_for_someone_with_access_elsewhere(
    rig: dict[str, Any], elsewhere: str
) -> None:
    """C6.1.2: the account is global, so one company's admin must not take the second step off
    someone who also belongs to another company, or who is one of our own staff."""
    admin = await rig["person"]("company_admin", rig["a"])
    shared = await rig["person"]("employee", rig["a"])
    them = _row((await admin.get(f"{API}/users")).json(), role="employee")
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update users set mfa_enabled = true where id = :u"),
            {"u": them["user_id"]},
        )
        await c.execute(
            text("update sessions set mfa_passed_at = now() where user_id = :u"),
            {"u": them["user_id"]},
        )
        if elsewhere == "second_company":
            await c.execute(
                text("insert into memberships (user_id, company_id, role) values (:u, :c, :r)"),
                {"u": them["user_id"], "c": rig["b"], "r": "employee"},
            )
        else:
            await c.execute(
                text("insert into platform_admins (user_id, level) values (:u, 'support')"),
                {"u": them["user_id"]},
            )
    await _confirm(rig, admin)

    refused = await admin.post(f"{API}/users/{them['id']}/reset-two-step")
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "FORBIDDEN"
    async with rig["owner"].connect() as c:
        kept = (
            await c.execute(
                text("select mfa_enabled from users where id = :u"),
                {"u": them["user_id"]},
            )
        ).scalar_one()
        live = (
            await c.execute(
                text("select count(*) from sessions where user_id = :u and revoked_at is null"),
                {"u": them["user_id"]},
            )
        ).scalar_one()
    assert kept is True
    assert live >= 1  # their sessions were not ended
    assert shared is not None
    assert not [1 for _, name, _ in rig["mail"].sent if name == "two_step_reset"]


async def test_the_two_step_policy_is_read_changed_audited_and_counted(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    hr = await rig["person"]("hr_admin", rig["a"])
    assert (await admin.get(f"{API}/security/two-step")).json() == {
        "policy": "optional",
        "to_set_up": 0,
    }
    assert (await hr.put(f"{API}/security/two-step", json={"policy": "all"})).status_code == 403
    assert (
        await admin.put(f"{API}/security/two-step", json={"policy": "bogus"})
    ).status_code == 422

    await _confirm(rig, admin)
    # Not yet set up by the admin: the policy would cover them too.
    admins_only = (await admin.put(f"{API}/security/two-step", json={"policy": "admins"})).json()
    assert admins_only == {"policy": "admins", "to_set_up": 1}
    # The admin sets theirs up; now only HR is still to do.
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update users set mfa_enabled = true where email like 'company_admin%'")
        )
    everyone = (await admin.put(f"{API}/security/two-step", json={"policy": "all"})).json()
    assert everyone == {"policy": "all", "to_set_up": 1}
    await admin.put(f"{API}/security/two-step", json={"policy": "all"})  # no change: not audited
    # Switching it on is felt on the next request of anyone it newly covers.
    refused = await hr.get(f"{API}/users")
    assert refused.json()["error"]["code"] == "MFA_ENROLMENT_REQUIRED"

    other = await rig["person"]("company_admin", rig["b"])
    assert (await other.get(f"{API}/security/two-step")).json()["policy"] == "optional"
    changes = await _audit_actions(rig, "company.mfa_policy")
    assert len(changes) == 2


async def test_the_role_viewer_is_built_from_the_permission_matrix(rig: dict[str, Any]) -> None:
    from app.core.rbac_matrix import ROLE_PERMISSIONS

    admin = await rig["person"]("company_admin", rig["a"])
    matrix = (await admin.get(f"{API}/roles/matrix")).json()
    by_role = {r["role"]: r for r in matrix["roles"]}
    assert list(by_role) == [
        "company_admin",
        "hr_admin",
        "people_manager",
        "recruiter",
        "employee",
        "read_only_auditor",
    ]
    for role, summary in by_role.items():
        listed = {i["permission"] for g in summary["groups"] for i in g["items"]}
        assert listed == set(ROLE_PERMISSIONS[role])  # nothing missing, nothing invented
        assert summary["total"] == len(listed)
    employee = {i["label"]: i["scope"] for g in by_role["employee"]["groups"] for i in g["items"]}
    assert employee["See their own profile"] == "own"
    assert "Add and change company profile" not in employee
    assert (
        await (await rig["person"]("employee", rig["a"])).get(f"{API}/roles/matrix")
    ).status_code == 403


async def test_employee_links_are_unique_scoped_and_audited(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    staff = await rig["person"]("employee", rig["a"])
    hr = await rig["person"]("hr_admin", rig["a"])
    other = await rig["person"]("company_admin", rig["b"])
    made = await admin.post(
        f"{API}/employees",
        json={
            "first_name": "Amira",
            "last_name": "Hassan",
            "email": "amira@example.com",
            "employee_number": "LINK1",
            "hire_date": "2025-01-06",
        },
    )
    emp = made.json()["id"]
    foreign = (
        await other.post(
            f"{API}/employees",
            json={
                "first_name": "Other",
                "last_name": "Person",
                "email": "other@example.com",
                "employee_number": "LINK1",
                "hire_date": "2025-01-06",
            },
        )
    ).json()["id"]
    members = (await admin.get(f"{API}/users")).json()["users"]
    mine = next(u["id"] for u in members if u["is_you"])
    target = next(u["id"] for u in members if u["role"] == "employee")
    path = f"{API}/users/{target}/employee"
    assert (await admin.put(path, json={"employee_id": emp})).status_code == 200
    assert (await staff.get(f"{API}/employees/{emp}")).status_code == 200
    assert (
        await admin.put(f"{API}/users/{mine}/employee", json={"employee_id": emp})
    ).status_code == 409
    assert (await admin.put(path, json={"employee_id": foreign})).status_code == 404
    foreign_member = (await other.get(f"{API}/users")).json()["users"][0]["id"]
    assert (
        await admin.put(f"{API}/users/{foreign_member}/employee", json={"employee_id": emp})
    ).status_code == 404
    for person in (staff, hr):
        assert (await person.put(path, json={"employee_id": None})).status_code == 403
    assert (await admin.put(path, json={"employee_id": None})).json()["employee_id"] is None
    assert (await staff.get(f"{API}/employees/{emp}")).status_code == 404
    assert (
        await admin.put(f"{API}/users/{mine}/employee", json={"employee_id": emp})
    ).status_code == 200
    async with rig["owner"].connect() as c:
        events = (
            (
                await c.execute(
                    text(
                        "select action from audit_events where entity_id=:id and action like 'employee.user_%'"
                    ),
                    {"id": uuid.UUID(emp)},
                )
            )
            .scalars()
            .all()
        )
    assert events.count("employee.user_linked") == 2
    assert events.count("employee.user_unlinked") == 1


async def _confirm(rig: dict[str, Any], client: httpx.AsyncClient) -> None:
    token = client.cookies.get("brand_session")
    data = await rig["sessions"].get(token)
    await rig["sessions"].mark_step_up(token, data)


@pytest.mark.parametrize("expired", [False, True])
async def test_sensitive_access_changes_require_fresh_step_up(
    rig: dict[str, Any],
    expired: bool,
) -> None:
    from datetime import timedelta

    from app.modules.auth.sessions import utcnow

    admin = await rig["person"]("company_admin", rig["a"])
    await rig["person"]("employee", rig["a"])
    target = _row((await admin.get(f"{API}/users")).json(), role="employee")["id"]
    # Make a privileged invitation while confirmed, then remove/age that confirmation.
    await _confirm(rig, admin)
    invite = await admin.post(f"{API}/users/invitations", json={**INVITE, "role": "hr_admin"})
    assert invite.status_code == 201
    token = admin.cookies.get("brand_session")
    await rig["sessions"]._patch(
        token, "step_up_at", (utcnow() - timedelta(minutes=11)).isoformat() if expired else None
    )
    before = await _audit_actions(rig)
    calls: list[Callable[[], Awaitable[httpx.Response]]] = [
        lambda: admin.patch(f"{API}/users/{target}/role", json={"role": "recruiter"}),
        lambda: admin.post(f"{API}/users/invitations/{invite.json()['id']}/resend"),
        lambda: admin.put(f"{API}/security/two-step", json={"policy": "admins"}),
    ]
    for role in ("company_admin", "hr_admin"):
        response = await admin.post(f"{API}/users/invitations", json={**INVITE, "role": role})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "STEP_UP_REQUIRED"
    for call in calls:
        response = await call()
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "STEP_UP_REQUIRED"
    assert await _audit_actions(rig) == before
    assert _row((await admin.get(f"{API}/users")).json(), id=target)["role"] == "employee"
    assert (await admin.get(f"{API}/security/two-step")).json()["policy"] == "optional"
    # Ordinary invitations still work; a fresh confirmation allows each protected mutation.
    assert (
        await admin.post(f"{API}/users/invitations", json={**INVITE, "email": "normal@example.com"})
    ).status_code == 201
    await _confirm(rig, admin)
    for call in calls:
        assert (await call()).status_code == 200
