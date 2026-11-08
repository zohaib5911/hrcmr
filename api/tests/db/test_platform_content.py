"""T17.5: platform owners publish a new terms version, which everyone must accept before using the
product; platform admins manage the feature flags, the dossier links and the announcement banner.
Every change is audited under the platform admin. Only an owner publishes terms.

The rig gives two companies, "a" and "b". Terms versions are global, so the tests use their own
version names and never assume the table is empty."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
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


async def _flag_value(rig: dict[str, Any], key: str) -> Any:
    async with rig["owner"].connect() as c:
        return (
            await c.execute(text("select enabled from feature_flags where key = :k"), {"k": key})
        ).scalar_one_or_none()


async def _flag_reasons(rig: dict[str, Any], key: str) -> list[str | None]:
    async with rig["owner"].connect() as c:
        rows = await c.execute(
            text(
                "select reason from audit_events where action = 'platform.feature_flag_changed' "
                "and after->>'key' = :k order by created_at"
            ),
            {"k": key},
        )
        return [reason for (reason,) in rows.all()]


async def test_only_platform_admins_read_and_set_feature_flags(rig: dict[str, Any]) -> None:
    company_admin = await rig["person"]("company_admin", rig["a"])
    assert (await company_admin.get(f"{API}/platform/feature-flags")).status_code == 403
    refused = await company_admin.put(
        f"{API}/platform/feature-flags/ai_drafts", json={"enabled": True, "reason": "Trial start"}
    )
    assert refused.status_code == 403
    assert await _flag_value(rig, "ai_drafts") is None


async def test_a_flag_is_set_read_and_audited_only_when_it_changes(rig: dict[str, Any]) -> None:
    admin = await _platform_admin(rig, "support")
    made = await admin.put(
        f"{API}/platform/feature-flags/new_courses",
        json={
            "enabled": True,
            "description": "New course editor",
            "reason": "Pilot with two firms",
        },
    )
    assert made.status_code == 200, made.text
    assert made.json()["enabled"] is True
    assert await _flag_value(rig, "new_courses") is True
    listed = (await admin.get(f"{API}/platform/feature-flags")).json()
    assert [item["key"] for item in listed["items"]] == ["new_courses"]
    same = await admin.put(
        f"{API}/platform/feature-flags/new_courses",
        json={
            "enabled": True,
            "description": "New course editor",
            "reason": "Pilot with two firms",
        },
    )
    assert same.status_code == 200
    off = await admin.put(
        f"{API}/platform/feature-flags/new_courses",
        json={"enabled": False, "reason": "Pilot over"},
    )
    assert off.json()["enabled"] is False
    assert await _flag_value(rig, "new_courses") is False
    # The unchanged save is not audited; the two real changes are, with their reasons.
    assert await _flag_reasons(rig, "new_courses") == ["Pilot with two firms", "Pilot over"]


async def test_a_bad_flag_name_is_refused(rig: dict[str, Any]) -> None:
    admin = await _platform_admin(rig, "support")
    bad = await admin.put(
        f"{API}/platform/feature-flags/Bad-Name", json={"enabled": True, "reason": "Trial start"}
    )
    assert bad.status_code == 422, bad.text
    assert await _flag_value(rig, "Bad-Name") is None


def _at(hours: float) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def _banner(region: str, title: str, starts: float, ends: float) -> dict[str, Any]:
    return {
        "region": region,
        "title": title,
        "body": "Planned work on Saturday.",
        "starts_at": _at(starts),
        "ends_at": _at(ends),
        "reason": "Planned maintenance notice",
    }


async def test_banners_are_scheduled_per_region_and_companies_see_only_their_live_ones(
    rig: dict[str, Any],
) -> None:
    company_admin = await rig["person"]("company_admin", rig["a"])
    refused = await company_admin.post(
        f"{API}/platform/announcements", json=_banner("uk", "Refused", -1, 24)
    )
    assert refused.status_code == 403
    admin = await _platform_admin(rig, "support")
    for body in (
        _banner("uk", "Live for uk", -1, 24),
        _banner("uk", "Scheduled for uk", 24, 48),
        _banner("us", "Live for us", -1, 24),
    ):
        made = await admin.post(f"{API}/platform/announcements", json=body)
        assert made.status_code == 201, made.text
    listed = (await admin.get(f"{API}/platform/announcements")).json()
    assert {item["title"]: item["status"] for item in listed["items"]} == {
        "Live for uk": "live",
        "Scheduled for uk": "scheduled",
        "Live for us": "live",
    }
    employee = await rig["person"]("employee", rig["a"])
    seen = (await employee.get(f"{API}/company/announcements")).json()
    assert [item["title"] for item in seen["items"]] == ["Live for uk"]


async def test_ending_a_banner_removes_it_and_is_audited(rig: dict[str, Any]) -> None:
    admin = await _platform_admin(rig, "support")
    made = await admin.post(
        f"{API}/platform/announcements", json=_banner("uk", "Ends early", -1, 24)
    )
    assert made.status_code == 201, made.text
    banner = uuid.UUID(made.json()["id"])
    ended = await admin.post(
        f"{API}/platform/announcements/{banner}/end",
        json={"reason": "Notice no longer needed"},
    )
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "ended"
    employee = await rig["person"]("employee", rig["a"])
    assert (await employee.get(f"{API}/company/announcements")).json()["items"] == []
    again = await admin.post(
        f"{API}/platform/announcements/{banner}/end", json={"reason": "Ending twice"}
    )
    assert again.status_code == 409, again.text
    assert again.json()["error"]["code"] == "ALREADY_ENDED"
    assert await _audit(rig, banner) == [
        ("platform.announcement_created", "Planned maintenance notice"),
        ("platform.announcement_ended", "Notice no longer needed"),
    ]


async def test_a_banner_needs_a_time_zone_a_period_and_an_end_in_the_future(
    rig: dict[str, Any],
) -> None:
    admin = await _platform_admin(rig, "support")
    naive = _banner("uk", "Naive", -1, 24) | {"ends_at": "2030-01-01T10:00:00"}
    no_zone = await admin.post(f"{API}/platform/announcements", json=naive)
    assert no_zone.json()["error"]["code"] == "NEEDS_TIME_ZONE"
    backwards = await admin.post(
        f"{API}/platform/announcements", json=_banner("uk", "Backwards", 24, 2)
    )
    assert backwards.status_code == 422
    assert backwards.json()["error"]["code"] == "INVALID_PERIOD"
    past = await admin.post(f"{API}/platform/announcements", json=_banner("uk", "Past", -48, -24))
    assert past.json()["error"]["code"] == "ENDS_IN_PAST"
