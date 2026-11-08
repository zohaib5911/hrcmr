"""T17.2: platform admins read the overview numbers, search and change companies, and search and lock
users. A company administrator gets 403 on all of it. A suspended company's people are refused on
the tenant routes; a locked person cannot keep a session. Every change is audited under the
platform admin, with its reason.

The rig empties the companies and people for every test, so the counts below are exact: two
annual companies, "a" and "b", both active and entitled."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from tests.db.test_employee_documents import rig as rig

API = "/api/v1"
ANNUAL_PENCE = 5000


async def _platform_admin(rig: dict[str, Any], level: str) -> tuple[Any, uuid.UUID]:
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
    started = await admin.post(f"{API}/auth/platform-session")
    assert started.status_code == 201, started.text
    return admin, me


async def _audit(rig: dict[str, Any], entity: uuid.UUID) -> list[tuple[str, str | None]]:
    async with rig["owner"].connect() as c:
        rows = await c.execute(
            text(
                "select action, reason from audit_events where entity_id = :e "
                "and action like 'platform.%' order by created_at"
            ),
            {"e": entity},
        )
        return [(str(action), reason) for action, reason in rows.all()]


async def test_only_a_platform_admin_reads_the_overview_and_the_companies(
    rig: dict[str, Any],
) -> None:
    company_admin = await rig["person"]("company_admin", rig["a"])
    for path in (
        "/platform/metrics",
        "/platform/companies",
        f"/platform/companies/{rig['a']}",
        "/platform/users?q=abc",
    ):
        assert (await company_admin.get(f"{API}{path}")).status_code == 403, path


async def test_the_overview_counts_companies_plans_and_money(rig: dict[str, Any]) -> None:
    admin, _ = await _platform_admin(rig, "support")
    body = (await admin.get(f"{API}/platform/metrics")).json()
    assert body["companies_active"] == 2
    assert body["plans_active"] == {"free": 0, "annual": 2, "ten_year": 0}
    assert body["signups_24h"] == 2
    assert body["signups_7d"] == 2
    assert body["paid_entitled"] == 2
    assert body["arr_pence"] == 2 * ANNUAL_PENCE
    assert body["mrr_pence"] == round(2 * ANNUAL_PENCE / 12)
    assert body["churn_30d"] == 0
    assert body["refunds_30d"] == 0

    # "b" lapses 5 days ago and is refunded 2 days ago: one churned plan, one refund.
    now = datetime.now(UTC)
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "update companies set subscription_status='canceled', "
                "subscription_ends_at=:e where id=:c"
            ),
            {"e": now - timedelta(days=5), "c": rig["b"]},
        )
        await c.execute(
            text(
                "insert into subscriptions (id, company_id, plan, status, "
                "stripe_payment_intent_id, refunded_at) "
                "values (:i, :c, 'ten_year', 'refunded', :p, :r)"
            ),
            {
                "i": uuid.uuid4(),
                "c": rig["b"],
                "p": f"pi_{uuid.uuid4().hex}",
                "r": now - timedelta(days=2),
            },
        )
    body = (await admin.get(f"{API}/platform/metrics")).json()
    assert body["paid_entitled"] == 1
    assert body["arr_pence"] == ANNUAL_PENCE
    assert body["mrr_pence"] == round(ANNUAL_PENCE / 12)
    assert body["churn_30d"] == 1
    assert body["refunds_30d"] == 1


async def test_companies_search_filter_and_detail(rig: dict[str, Any]) -> None:
    admin, _ = await _platform_admin(rig, "support")
    listed = (await admin.get(f"{API}/platform/companies")).json()
    assert listed["total"] == 2

    by_name = (await admin.get(f"{API}/platform/companies", params={"q": "Company a"})).json()
    assert by_name["total"] == 1
    assert by_name["items"][0]["slug"] == "a"

    # A wildcard is plain text: "%" matches no company name.
    assert (await admin.get(f"{API}/platform/companies", params={"q": "%"})).json()["total"] == 0
    assert (await admin.get(f"{API}/platform/companies", params={"plan": "free"})).json()[
        "total"
    ] == 0
    assert (await admin.get(f"{API}/platform/companies", params={"status": "suspended"})).json()[
        "total"
    ] == 0

    page = (await admin.get(f"{API}/platform/companies", params={"limit": 1})).json()
    assert page["total"] == 2
    assert len(page["items"]) == 1

    detail = (await admin.get(f"{API}/platform/companies/{rig['a']}")).json()
    assert detail["members"] == 1
    assert detail["people"][0]["role"] == "company_admin"
    assert detail["people"][0]["locked"] is False
    assert detail["events"] == []
    assert (await admin.get(f"{API}/platform/companies/{uuid.uuid4()}")).status_code == 404


async def test_suspend_stops_the_company_and_reactivate_restores_it(
    rig: dict[str, Any],
) -> None:
    admin, _ = await _platform_admin(rig, "support")
    company = str(rig["a"])
    assert (await admin.get(f"{API}/users")).status_code == 200

    too_short = await admin.post(
        f"{API}/platform/companies/{company}/suspend", json={"reason": "no"}
    )
    assert too_short.status_code == 422

    done = await admin.post(
        f"{API}/platform/companies/{company}/suspend",
        json={"reason": "Chargeback under review"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "suspended"
    refused = await admin.get(f"{API}/users")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "ACCOUNT_SUSPENDED"
    again = await admin.post(
        f"{API}/platform/companies/{company}/suspend", json={"reason": "Chargeback under review"}
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "NOT_ACTIVE"

    back = await admin.post(
        f"{API}/platform/companies/{company}/reactivate",
        json={"reason": "Review closed, no action"},
    )
    assert back.status_code == 200, back.text
    assert back.json()["status"] == "active"
    assert (await admin.get(f"{API}/users")).status_code == 200
    assert [event["action"] for event in back.json()["events"]] == [
        "platform.company_reactivated",
        "platform.company_suspended",
    ]
    assert await _audit(rig, rig["a"]) == [
        ("platform.company_suspended", "Chargeback under review"),
        ("platform.company_reactivated", "Review closed, no action"),
    ]


async def test_extend_plan_comps_days_on_any_plan_and_moves_a_ten_year_end_date(
    rig: dict[str, Any],
) -> None:
    admin, _ = await _platform_admin(rig, "support")
    company = str(rig["a"])
    body = {"days": 30, "reason": "Goodwill comp for the outage"}

    # An annual company gets a complimentary end date, separate from Stripe (owner answer 5).
    annual = await admin.post(f"{API}/platform/companies/{company}/extend-plan", json=body)
    assert annual.status_code == 200, annual.text
    assert annual.json()["events"][0]["action"] == "platform.company_comp_granted"
    assert annual.json()["events"][0]["summary"] == "Complimentary access extended by 30 days"

    end = datetime.now(UTC) + timedelta(days=365 * 9)
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "update companies set plan='ten_year', subscription_status='active', "
                "subscription_ends_at=:e where id=:c"
            ),
            {"e": end, "c": rig["a"]},
        )
    too_many = await admin.post(
        f"{API}/platform/companies/{company}/extend-plan", json={**body, "days": 400}
    )
    assert too_many.status_code == 422

    done = await admin.post(f"{API}/platform/companies/{company}/extend-plan", json=body)
    assert done.status_code == 200, done.text
    new_end = datetime.fromisoformat(done.json()["subscription_ends_at"])
    assert new_end - end == timedelta(days=30)
    assert done.json()["events"][0]["action"] == "platform.company_plan_extended"
    assert done.json()["events"][0]["summary"] == "Extended by 30 days"


async def test_marking_for_deletion_is_owner_only_and_removes_nothing(
    rig: dict[str, Any],
) -> None:
    support, _ = await _platform_admin(rig, "support")
    owner, _ = await _platform_admin(rig, "owner")
    company = str(rig["a"])
    body = {"reason": "Owner asked for the account to close"}

    refused = await support.post(f"{API}/platform/companies/{company}/mark-for-deletion", json=body)
    assert refused.status_code == 403

    marked = await owner.post(f"{API}/platform/companies/{company}/mark-for-deletion", json=body)
    assert marked.status_code == 200, marked.text
    assert marked.json()["status"] == "pending_deletion"
    again = await owner.post(f"{API}/platform/companies/{company}/mark-for-deletion", json=body)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "NOT_MARKABLE"

    # The company's people are refused, and its rows stay in place (nothing is purged here).
    assert (await support.get(f"{API}/users")).json()["error"]["code"] == "ACCOUNT_SUSPENDED"
    async with rig["owner"].connect() as c:
        remaining = await c.execute(
            text("select count(*) from memberships where company_id = :c"), {"c": rig["a"]}
        )
        assert remaining.scalar_one() == 2


async def test_users_search_lock_and_unlock(rig: dict[str, Any]) -> None:
    admin, me = await _platform_admin(rig, "support")
    employee = await rig["person"]("employee", rig["a"])
    person = uuid.UUID((await employee.get(f"{API}/auth/me")).json()["user"]["id"])

    assert (await admin.get(f"{API}/platform/users", params={"q": "ab"})).status_code == 422
    found = (await admin.get(f"{API}/platform/users", params={"q": "employee-"})).json()["items"]
    assert [item["id"] for item in found] == [str(person)]
    assert found[0]["locked"] is False
    assert found[0]["companies"] == [
        {"id": str(rig["a"]), "name": "Company a", "role": "employee", "status": "active"}
    ]

    own = await admin.post(f"{API}/platform/users/{me}/lock", json={})
    assert own.status_code == 409
    assert own.json()["error"]["code"] == "SELF_LOCK"

    locked = await admin.post(
        f"{API}/platform/users/{person}/lock", json={"reason": "Suspected account sharing"}
    )
    assert locked.status_code == 200, locked.text
    assert locked.json()["locked"] is True
    assert (await employee.get(f"{API}/auth/me")).status_code == 401
    twice = await admin.post(f"{API}/platform/users/{person}/lock", json={})
    assert twice.json()["error"]["code"] == "ALREADY_LOCKED"

    restored = await admin.post(f"{API}/platform/users/{person}/unlock", json={})
    assert restored.status_code == 200, restored.text
    assert restored.json()["locked"] is False
    assert (await employee.get(f"{API}/auth/me")).status_code == 200
    again = await admin.post(f"{API}/platform/users/{person}/unlock", json={})
    assert again.json()["error"]["code"] == "NOT_LOCKED"

    assert await _audit(rig, person) == [
        ("platform.user_locked", "Suspected account sharing"),
        ("platform.user_unlocked", None),
    ]


async def test_a_support_admin_cannot_lock_a_platform_admin_but_an_owner_can_lock_support(
    rig: dict[str, Any],
) -> None:
    owner, owner_id = await _platform_admin(rig, "owner")
    support, support_id = await _platform_admin(rig, "support")
    refused = await support.post(f"{API}/platform/users/{owner_id}/lock", json={"reason": "test"})
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["message"] == "Only an owner can lock a platform admin."
    async with rig["owner"].connect() as c:
        active = (
            await c.execute(text("select is_active from users where id = :u"), {"u": owner_id})
        ).scalar_one()
    assert active is True
    allowed = await owner.post(f"{API}/platform/users/{support_id}/lock", json={})
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["locked"] is True
