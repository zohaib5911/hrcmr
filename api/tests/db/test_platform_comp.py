"""T17.6, owner answer 5: a platform admin gives a company free access for some days, separately
from its Stripe plan. The access lasts until the comp end date; Stripe's records are not touched.
Each grant is audited with its reason. A free company goes from read-only to writable the moment a
comp is granted, and back to read-only when it ends.

The entitlement rules are also checked as plain functions, so the plan logic is tested without a
database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy import text

from app.modules.billing.entitlements import is_entitled
from tests.db.test_employee_documents import rig as rig

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
    started = await admin.post(f"{API}/auth/platform-session")
    assert started.status_code == 201, started.text
    return admin


async def _make_free(rig: dict[str, Any]) -> None:
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "update companies set plan='free', subscription_status=null, "
                "subscription_ends_at=null, payment_grace_ends_at=null, comp_until=null where id=:c"
            ),
            {"c": rig["a"]},
        )


async def test_a_comp_turns_a_free_company_writable_until_it_ends(rig: dict[str, Any]) -> None:
    await _make_free(rig)
    company_admin = await rig["person"]("company_admin", rig["a"])
    refused = await company_admin.post(f"{API}/departments", json={"name": "Sales"})
    assert refused.status_code == 402
    assert refused.json()["error"]["code"] == "PLAN_REQUIRED"

    support = await _platform_admin(rig, "support")
    granted = await support.post(
        f"{API}/platform/companies/{rig['a']}/extend-plan",
        json={"days": 30, "reason": "Goodwill comp for the outage"},
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["events"][0]["reason"] == "Goodwill comp for the outage"
    assert (
        await company_admin.post(f"{API}/departments", json={"name": "Sales"})
    ).status_code == 201
    billing = (await company_admin.get(f"{API}/billing/subscription")).json()
    assert billing["comp_until"] is not None

    # The comp ends: the company is read-only again, and its plan was never changed.
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update companies set comp_until = now() - interval '1 day' where id = :c"),
            {"c": rig["a"]},
        )
    again = await company_admin.post(f"{API}/departments", json={"name": "Ops"})
    assert again.status_code == 402
    assert again.json()["error"]["code"] == "PLAN_REQUIRED"


def _company(**values: Any) -> Any:
    base = {
        "plan": "free",
        "subscription_status": None,
        "subscription_ends_at": None,
        "payment_grace_ends_at": None,
        "comp_until": None,
    }
    return SimpleNamespace(**(base | values))


def test_a_comp_counts_for_writes_and_not_for_the_paid_count() -> None:
    now = datetime.now(UTC)
    comped = _company(comp_until=now + timedelta(days=5))
    assert is_entitled(comped, now) is True
    assert is_entitled(comped, now, include_comp=False) is False
    expired = _company(comp_until=now - timedelta(seconds=1))
    assert is_entitled(expired, now) is False
    assert is_entitled(_company(), now) is False
