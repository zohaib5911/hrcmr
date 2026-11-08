"""T17.5: platform owners publish a new terms version, which everyone must accept before using the
product; platform admins manage the feature flags, the dossier links and the announcement banner.
Every change is audited under the platform admin. Only an owner publishes terms.

The rig gives two companies, "a" and "b". Terms versions are global, so the tests use their own
version names and never assume the table is empty."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text

from tests.db.test_employee_documents import rig as rig

API = "/api/v1"
BILLING = f"{API}/billing/subscription"  # needs billing.manage, so the terms check applies


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


async def _accept(client: Any, version: str) -> None:
    """The person accepts the current terms, as the app asks after a publish."""
    accepted = await client.post(f"{API}/auth/accept-terms", json={"version": version})
    assert accepted.status_code == 204, accepted.text


def _terms(version: str, **extra: Any) -> dict[str, Any]:
    body = {"version": version, "url": "https://example.com/terms", "reason": "Annual refresh"}
    return body | extra


async def test_only_an_owner_publishes_terms(rig: dict[str, Any]) -> None:
    company_admin = await rig["person"]("company_admin", rig["a"])
    refused = await company_admin.post(f"{API}/platform/terms-versions", json=_terms("t-plain"))
    assert refused.status_code == 403
    support = await _platform_admin(rig, "support")
    refused = await support.post(f"{API}/platform/terms-versions", json=_terms("t-support"))
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["message"].startswith("Only an owner")


async def test_publishing_a_version_makes_everyone_accept_it_again(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    assert (await admin.get(BILLING)).status_code == 200
    owner = await _platform_admin(rig, "owner")
    published = await owner.post(f"{API}/platform/terms-versions", json=_terms("2026-11-09"))
    assert published.status_code == 201, published.text
    assert published.json()["current"] is True
    await _accept(owner, "2026-11-09")
    # The company administrator has not accepted this version yet, so every request is refused.
    refused = await admin.get(BILLING)
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "TERMS_ACCEPTANCE_REQUIRED"


async def test_a_version_name_can_be_used_once(rig: dict[str, Any]) -> None:
    owner = await _platform_admin(rig, "owner")
    first = await owner.post(f"{API}/platform/terms-versions", json=_terms("t-once"))
    assert first.status_code == 201, first.text
    await _accept(owner, "t-once")
    again = await owner.post(f"{API}/platform/terms-versions", json=_terms("t-once"))
    assert again.status_code == 409, again.text
    assert again.json()["error"]["code"] == "VERSION_EXISTS"


async def test_the_list_marks_the_newest_version_current_and_audits_the_publish(
    rig: dict[str, Any],
) -> None:
    owner = await _platform_admin(rig, "owner")
    made = await owner.post(f"{API}/platform/terms-versions", json=_terms("t-listed"))
    assert made.status_code == 201, made.text
    await _accept(owner, "t-listed")
    listed = (await owner.get(f"{API}/platform/terms-versions")).json()
    assert listed["items"][0]["version"] == "t-listed"
    assert listed["items"][0]["current"] is True
    assert [item["current"] for item in listed["items"][1:]] == [False] * (len(listed["items"]) - 1)
    assert await _audit(rig, uuid.UUID(made.json()["id"])) == [
        ("platform.terms_published", "Annual refresh")
    ]
