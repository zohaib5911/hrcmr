"""T11.6 public careers: only open external postings, only listed fields, and an apply form that needs
consent and Turnstile and writes the candidate, the application and the messages."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import text

from app.integrations.clamav import ScanResult
from app.modules.recruitment import public as careers
from tests.db.test_applications import open_posting
from tests.db.test_company import png
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig
from tests.db.test_files import PDF

API = "/api/v1"
LIST_KEYS = {"company", "has_logo", "postings"}
ITEM_KEYS = {"slug", "title", "location", "closes_on"}
DETAIL_KEYS = {
    "company",
    "has_logo",
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
    "consent": "true",
    "turnstile_token": "test-token",
}
NO_TOKEN = {key: value for key, value in APPLY.items() if key != "turnstile_token"}


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
    refused = await public.post(f"{API}/public/postings/{slug}/porter-careers/apply", data=APPLY)
    assert refused.status_code == 404, refused.text
    await public.aclose()


async def test_applying_needs_consent_and_turnstile_and_creates_the_application(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    slug = await company_slug(rig, rig["a"])
    await open_posting(admin, "Chef careers")
    public = anonymous(rig)
    url = f"{API}/public/postings/{slug}/chef-careers/apply"
    assert (await public.post(url, data=NO_TOKEN)).status_code == 422
    assert (await public.post(url, data={**APPLY, "consent": "false"})).status_code == 422
    sent = await public.post(url, data=APPLY)
    assert sent.status_code == 202, sent.text
    assert sent.json() == {"received": True}
    again = await public.post(url, data=APPLY)
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


async def applications_for(rig: dict[str, Any], company: Any) -> int:
    async with rig["owner"].connect() as db:
        return int(
            (
                await db.execute(
                    text("select count(*) from applications where company_id=:c"), {"c": company}
                )
            ).scalar_one()
        )


async def test_a_cv_is_scanned_and_kept_with_the_candidate(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    slug = await company_slug(rig, rig["a"])
    await open_posting(admin, "Waiter careers")
    url = f"{API}/public/postings/{slug}/waiter-careers/apply"
    public = anonymous(rig)
    wrong = await public.post(url, data=APPLY, files={"cv": ("cv.csv", b"a,b\n1,2\n")})
    assert wrong.status_code == 415, wrong.text

    async def infected(*args: Any, **kwargs: Any) -> ScanResult:
        return ScanResult("infected", "test")

    with monkeypatch.context() as patch:
        patch.setattr(rig["app"].state.files.scanner, "scan", infected)
        refused = await public.post(
            url, data=APPLY, files={"cv": ("cv.pdf", PDF, "application/pdf")}
        )
    assert refused.status_code == 422, refused.text
    assert await applications_for(rig, rig["a"]) == 0
    # About 3 MB: bigger than the 1 MB body limit most endpoints have.
    large = PDF + b"\n%" + b"0" * 3_000_000
    sent = await public.post(url, data=APPLY, files={"cv": ("cv.pdf", large, "application/pdf")})
    assert sent.status_code == 202, sent.text
    await public.aclose()
    async with rig["owner"].connect() as db:
        kept = (
            await db.execute(
                text(
                    "select f.scan_status, f.uploaded_by from files f join candidates c "
                    "on c.id = f.owner_id where f.owner_type='candidate' and c.email=:e "
                    "and f.company_id=:c"
                ),
                {"e": APPLY["email"], "c": rig["a"]},
            )
        ).all()
    assert [(row[0], row[1]) for row in kept] == [("clean", None)]
    assert await applications_for(rig, rig["a"]) == 1


async def test_a_failed_turnstile_check_saves_nothing(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    slug = await company_slug(rig, rig["a"])
    await open_posting(admin, "Host careers")

    async def refusing(token: str | None, remote_ip: str | None = None) -> bool:
        return False

    public = anonymous(rig)
    with monkeypatch.context() as patch:
        patch.setattr(rig["app"].state.auth.turnstile, "verify", refusing)
        refused = await public.post(f"{API}/public/postings/{slug}/host-careers/apply", data=APPLY)
    await public.aclose()
    assert refused.status_code == 400, refused.text
    assert refused.json()["error"]["code"] == "TURNSTILE_FAILED"
    assert await applications_for(rig, rig["a"]) == 0
    async with rig["owner"].connect() as db:
        people = (
            await db.execute(
                text("select count(*) from candidates where company_id=:c"), {"c": rig["a"]}
            )
        ).scalar_one()
    assert people == 0


async def test_internal_and_other_company_postings_take_no_applications(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    foreign = await rig["person"]("company_admin", rig["b"])
    slug = await company_slug(rig, rig["a"])
    other_slug = await company_slug(rig, rig["b"])
    internal = (await admin.post(API + "/requisitions", json={"job_title": "Staff only"})).json()[
        "id"
    ]
    await admin.patch(f"{API}/requisitions/{internal}/status", json={"status": "open"})
    made = await admin.post(
        API + "/postings",
        json={
            "requisition_id": internal,
            "title": "Staff only",
            "visibility": "internal",
            "vacancies": 1,
        },
    )
    await admin.patch(f"{API}/postings/{made.json()['id']}/status", json={"status": "open"})
    await open_posting(foreign, "Elsewhere careers")
    public = anonymous(rig)
    staff_only = await public.post(f"{API}/public/postings/{slug}/staff-only/apply", data=APPLY)
    assert staff_only.status_code == 404
    assert (
        await public.get(f"{API}/public/postings/{other_slug}/elsewhere-careers")
    ).status_code == 200
    assert (await public.get(f"{API}/public/postings/{slug}/elsewhere-careers")).status_code == 404
    crossed = await public.post(f"{API}/public/postings/{slug}/elsewhere-careers/apply", data=APPLY)
    assert crossed.status_code == 404
    await public.aclose()
    assert await applications_for(rig, rig["a"]) == 0
    assert await applications_for(rig, rig["b"]) == 0


async def test_too_many_applications_from_one_connection_are_refused(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    slug = await company_slug(rig, rig["a"])
    await open_posting(admin, "Runner careers")
    # A name of its own, so other tests' attempts do not count towards this limit.
    monkeypatch.setattr(careers, "APPLY_PER_CONNECTION", (f"careers.apply.{uuid.uuid4()}", 2, 3600))
    url = f"{API}/public/postings/{slug}/runner-careers/apply"
    public = anonymous(rig)
    for _ in range(2):
        assert (await public.post(url, data=APPLY)).status_code == 202
    blocked = await public.post(url, data=APPLY)
    await public.aclose()
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"


async def test_the_logo_shows_on_the_careers_pages_once_uploaded(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    slug = await company_slug(rig, rig["a"])
    await open_posting(admin, "Bartender careers")
    public = anonymous(rig)
    assert (await public.get(f"{API}/public/careers/{slug}")).json()["has_logo"] is False
    assert (await public.get(f"{API}/public/careers/{slug}/logo")).status_code == 404
    picture = png()
    uploaded = await admin.post(
        API + "/company/logo", files={"file": ("logo.png", picture, "image/png")}
    )
    assert uploaded.status_code == 204, uploaded.text
    assert (await public.get(f"{API}/public/careers/{slug}")).json()["has_logo"] is True
    detail = await public.get(f"{API}/public/postings/{slug}/bartender-careers")
    assert detail.json()["has_logo"] is True
    logo = await public.get(f"{API}/public/careers/{slug}/logo")
    await public.aclose()
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/png"
    assert logo.content == picture


async def test_too_many_logo_fetches_from_one_connection_are_refused(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    slug = await company_slug(rig, rig["a"])
    uploaded = await admin.post(
        API + "/company/logo", files={"file": ("logo.png", png(), "image/png")}
    )
    assert uploaded.status_code == 204, uploaded.text
    monkeypatch.setattr(careers, "READ_PER_CONNECTION", (f"careers.read.{uuid.uuid4()}", 2, 60))
    public = anonymous(rig)
    for _ in range(2):
        assert (await public.get(f"{API}/public/careers/{slug}/logo")).status_code == 200
    blocked = await public.get(f"{API}/public/careers/{slug}/logo")
    # The server-rendered list shares the web server's address, so it is not limited here.
    listed = await public.get(f"{API}/public/careers/{slug}")
    await public.aclose()
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    assert listed.status_code == 200


async def test_a_cv_over_the_limit_is_refused_before_it_is_read(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    slug = await company_slug(rig, rig["a"])
    await open_posting(admin, "Cashier careers")
    public = anonymous(rig)
    huge = PDF + b"\n%" + b"0" * int(11.5 * 1024 * 1024)
    refused = await public.post(
        f"{API}/public/postings/{slug}/cashier-careers/apply",
        data=APPLY,
        files={"cv": ("cv.pdf", huge, "application/pdf")},
    )
    await public.aclose()
    assert refused.status_code == 413
    assert await applications_for(rig, rig["a"]) == 0


async def test_existing_candidate_public_application_needs_review(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    slug = await company_slug(rig, rig["a"])
    await open_posting(admin, "First careers")
    await open_posting(admin, "Second careers")
    async with anonymous(rig) as public:
        first = await public.post(f"{API}/public/postings/{slug}/first-careers/apply", data=APPLY)
        assert first.status_code == 202
        second = await public.post(
            f"{API}/public/postings/{slug}/second-careers/apply",
            data={**APPLY, "first_name": "Imposter", "phone": "0000000000"},
        )
        assert second.status_code == 202
    apps = (await admin.get(API + "/applications")).json()["items"]
    assert len(apps) == 2
    assert len({row["candidate_id"] for row in apps}) == 1
    assert all(row["candidate_name"] == "Ivy Stone" for row in apps)
    assert {row["posting_title"]: row["needs_review"] for row in apps} == {
        "First careers": False,
        "Second careers": True,
    }
