"""T15.6: a sponsorship check is saved as a draft, confirmed, and reported as a PDF. The disclaimer
and the rules version are always in the report, and a check is private to its company.

The SOC sample is loaded once for the module, and the rules are published for each test (the rig's
clean-up removes them, as in tests/db/test_soc_match.py)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from app.modules.soc.models import SocCheck
from app.modules.soc.report import DISCLAIMER, report_html
from tests.db.support import DatabaseUnderTest, temporary_database
from tests.db.test_employee_documents import rig as rig
from tests.db.test_soc_match import _load_sample, _publish_rules

API = "/api/v1/soc"


@pytest.fixture(scope="module")
def database(stack: None) -> Iterator[DatabaseUnderTest]:
    with temporary_database() as db:
        asyncio.run(_load_sample(db.owner_url))
        yield db


@pytest.fixture(autouse=True)
async def ready(rig: dict[str, Any], database: DatabaseUnderTest) -> None:
    await _publish_rules(database.owner_url)


def _check_body(code: str = "7111") -> dict[str, Any]:
    return {
        "job_title": "Adviser, sales",
        "job_description": "Serve customers on the shop floor.",
        "soc_code": code,
        "check": {
            "weekly_hours": "37.5",
            "offered_salary": "30000.00",
            "salary_per": "year",
            "work_nation": "England",
            "cos_assignment_date": "2026-11-01",
            "applicant": {"situation": "outside_uk"},
        },
    }


async def test_a_check_is_drafted_confirmed_and_reported_as_a_pdf(rig: dict[str, Any]) -> None:
    user = await rig["person"]("recruiter", rig["a"])
    made = await user.post(API + "/checks", json=_check_body())
    assert made.status_code == 200, made.text
    draft = made.json()
    assert draft["status"] == "draft"
    assert draft["soc_code"] == "7111"
    assert draft["rules_version_name"]
    assert draft["result"]["rules_version_id"] is not None
    assert draft["inputs"]["cos_assignment_date"] == "2026-11-01"

    listed = await user.get(API + "/checks")
    assert [item["id"] for item in listed.json()["items"]] == [draft["id"]]

    # Nothing is reported until the code is confirmed.
    early = await user.get(f"{API}/checks/{draft['id']}/report.pdf")
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "CHECK_NOT_CONFIRMED"

    confirmed = await user.post(f"{API}/checks/{draft['id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["confirmed_at"] is not None

    report = await user.get(f"{API}/checks/{draft['id']}/report.pdf")
    assert report.status_code == 200
    assert report.headers["content-type"] == "application/pdf"
    assert report.content.startswith(b"%PDF")
    assert "soc-check-7111.pdf" in report.headers["content-disposition"]


async def test_the_report_always_has_the_disclaimer_and_the_rules_version() -> None:
    row = SocCheck(
        soc_code="7111",
        soc_title="Sales and retail assistants",
        job_title="Adviser, sales",
        job_description="",
        status="draft",
        rules_version_name="Immigration Rules as updated 29 October 2026",
        rules_effective_from=date(2026, 10, 29),
        confirmed_at=None,
        inputs={"weekly_hours": "37.5", "offered_salary": "30000.00", "salary_per": "year"},
        result={
            "eligibility": {"label": "Eligible"},
            "options": [],
            "verdict": {"meets": None, "option": None},
            "dependants_allowed": False,
            "notes": [],
        },
    )
    html = report_html(row)
    assert DISCLAIMER in html
    assert "Immigration Rules as updated 29 October 2026" in html
    assert "29 October 2026" in html
    assert "Cannot be decided yet" in html


async def test_auditors_read_and_other_companies_cannot_see_a_check(rig: dict[str, Any]) -> None:
    recruiter = await rig["person"]("recruiter", rig["a"])
    auditor = await rig["person"]("read_only_auditor", rig["a"])
    other = await rig["person"]("recruiter", rig["b"])
    made = await recruiter.post(API + "/checks", json=_check_body())
    check_id = made.json()["id"]

    assert (await auditor.get(f"{API}/checks/{check_id}")).status_code == 200
    refused = await auditor.post(API + "/checks", json=_check_body())
    assert refused.status_code == 403

    # Another company gets the same answer as for a check that does not exist.
    hidden = await other.get(f"{API}/checks/{check_id}")
    assert hidden.status_code == 404
    assert (await other.get(f"{API}/checks")).json() == {"items": []}
    missing = await other.get(f"{API}/checks/{uuid.uuid4()}")
    assert missing.status_code == 404
