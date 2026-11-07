"""T11.6 public careers: only open external postings, only listed fields, and an apply form that needs
consent and Turnstile and writes the candidate, the application and the messages."""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import text

from tests.db.test_applications import open_posting
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig

API = "/api/v1"
LIST_KEYS = {"company", "postings"}
ITEM_KEYS = {"slug", "title", "location", "closes_on"}
DETAIL_KEYS = {
    "company",
    "slug",
    "title",
    "location",
    "salary_from",
    "salary_to",
    "salary_per",
    "weekly_hours",
    "description",
    "visa_sponsorship",
    "closes_on",
}
APPLY = {
    "first_name": "Ivy",
    "last_name": "Stone",
    "email": "ivy@example.com",
    "what_you_bring": "Five years of kitchen experience",
    "consent": True,
    "turnstile_token": "test-token",
}


async def company_slug(rig: dict[str, Any], company: Any) -> str:
    async with rig["owner"].connect() as db:
        return str(
            (
                await db.execute(text("select slug from companies where id=:c"), {"c": company})
            ).scalar_one()
        )


CSRF = "careers-test-csrf"


def anonymous(rig: dict[str, Any]) -> httpx.AsyncClient:
    """A visitor who is not signed in; the CSRF cookie and header match, as a browser sends them."""
    browser = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=rig["app"]), base_url="http://test"
    )
    browser.cookies.set("csrf", CSRF)
    browser.headers["X-CSRF-Token"] = CSRF
    return browser


async def test_only_open_external_postings_are_public_and_show_only_listed_fields(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    slug = await company_slug(rig, rig["a"])
    await open_posting(admin, "Barista careers")
    internal = (
        await admin.post(API + "/requisitions", json={"job_title": "Internal only"})
    ).json()["id"]
    await admin.patch(f"{API}/requisitions/{internal}/status", json={"status": "open"})
    made = await admin.post(
        API + "/postings",
        json={
            "requisition_id": internal,
            "title": "Internal only",
            "visibility": "internal",
            "vacancies": 1,
        },
    )
    await admin.patch(f"{API}/postings/{made.json()['id']}/status", json={"status": "open"})
    public = anonymous(rig)
    listed = await public.get(f"{API}/public/careers/{slug}")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert set(body) == LIST_KEYS
    assert [item["title"] for item in body["postings"]] == ["Barista careers"]
    assert set(body["postings"][0]) == ITEM_KEYS
    slugs = [item["slug"] for item in body["postings"]]
    detail = await public.get(f"{API}/public/postings/{slug}/{slugs[0]}")
    assert detail.status_code == 200, detail.text
    assert set(detail.json()) == DETAIL_KEYS
    assert (await public.get(f"{API}/public/postings/{slug}/internal-only")).status_code == 404
    assert (await public.get(f"{API}/public/careers/no-such-company")).status_code == 404
    await public.aclose()


async def test_a_closed_posting_is_not_public_and_cannot_be_applied_to(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    slug = await company_slug(rig, rig["a"])
    await open_posting(admin, "Porter careers")
    public = anonymous(rig)
    assert (await public.get(f"{API}/public/postings/{slug}/porter-careers")).status_code == 200
    posting = (await admin.get(API + "/postings", params={"search": "Porter careers"})).json()[
        "items"
    ][0]
    await admin.patch(f"{API}/postings/{posting['id']}/status", json={"status": "closed"})
    assert (await public.get(f"{API}/public/postings/{slug}/porter-careers")).status_code == 404
    refused = await public.post(f"{API}/public/postings/{slug}/porter-careers/apply", json=APPLY)
    assert refused.status_code == 404
    await public.aclose()


async def test_applying_needs_consent_and_turnstile_and_creates_the_application(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    slug = await company_slug(rig, rig["a"])
    await open_posting(admin, "Chef careers")
    public = anonymous(rig)
    url = f"{API}/public/postings/{slug}/chef-careers/apply"
    assert (await public.post(url, json={**APPLY, "turnstile_token": None})).status_code == 422
    assert (await public.post(url, json={**APPLY, "consent": False})).status_code == 422
    sent = await public.post(url, json=APPLY)
    assert sent.status_code == 202, sent.text
    assert sent.json() == {"received": True}
    again = await public.post(url, json=APPLY)
    assert again.status_code == 202
    await public.aclose()
    apps = (await admin.get(API + "/applications")).json()
    assert apps["total"] == 1
    assert apps["items"][0]["candidate_name"] == "Ivy Stone"
    async with rig["owner"].connect() as db:
        via = (
            await db.execute(
                text("select applied_via from applications where company_id=:c"), {"c": rig["a"]}
            )
        ).scalar_one()
        mail = (
            (
                await db.execute(
                    text(
                        "select to_address from email_outbox where template='application_received'"
                    )
                )
            )
            .scalars()
            .all()
        )
        notices = (
            await db.execute(
                text(
                    "select count(*) from notifications where company_id=:c and kind='recruitment.application_received'"
                ),
                {"c": rig["a"]},
            )
        ).scalar_one()
    assert via == "careers_page"
    assert "ivy@example.com" in mail
    assert notices >= 1
