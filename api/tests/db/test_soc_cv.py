"""T15.5: the CV match endpoint. Contact details never reach Claude, and the feature is hidden
(409) when AI is off. The file scanner and Claude are fakes; the SOC sample is loaded so that the
occupation exists."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from typing import Any, BinaryIO

import pytest

from app.ai.redaction import find_restricted
from app.integrations.clamav import ScanResult
from tests.db.api_support import fake_claude
from tests.db.support import DatabaseUnderTest, temporary_database
from tests.db.test_employee_documents import rig as rig
from tests.db.test_soc_match import _load_sample
from tests.test_soc_cv import DOCX_MIME, cv_docx

API = "/api/v1/soc"
CV_LINES = [
    "Ann Smith",
    "Email ann.smith@example.com or call 07700 900123.",
    "Address: 14 Cedar Park Road, Leeds LS1 4AP",
    "LinkedIn: https://www.linkedin.com/in/ann-smith",
    "Served customers at the till for three years.",
]


class CleanScanner:
    async def scan(self, stream: BinaryIO) -> ScanResult:
        return ScanResult(status="clean")


@pytest.fixture(scope="module")
def database(stack: None) -> Iterator[DatabaseUnderTest]:
    """A fresh database with the SOC sample loaded, for this module only."""
    with temporary_database() as db:
        asyncio.run(_load_sample(db.owner_url))
        yield db


@pytest.fixture(autouse=True)
def clean_scanner(rig: dict[str, Any]) -> None:
    rig["app"].state.files.scanner = CleanScanner()


async def _upload(user: Any, cv: bytes, **form: str) -> Any:
    return await user.post(
        API + "/resume-match",
        data={"soc_code": "7111", **form},
        files={"cv": ("cv.docx", cv, DOCX_MIME)},
    )


async def test_the_cv_match_is_hidden_when_ai_is_off(rig: dict[str, Any]) -> None:
    user = await rig["person"]("recruiter", rig["a"])
    made = await _upload(user, cv_docx(CV_LINES))
    assert made.status_code == 409
    assert made.json()["error"]["code"] == "AI_UNAVAILABLE"


async def test_contact_details_never_reach_claude_and_only_quotes_from_the_cv_are_shown(
    rig: dict[str, Any],
) -> None:
    reply = {
        "score": 72,
        "evidence": [
            {"quote": "Served customers at the till", "point": "Shop-floor service"},
            {"quote": "Managed a team of twelve", "point": "Not in the CV"},
        ],
        "gaps": ["No food hygiene certificate shown"],
        "suggestions": ["Ask for a reference on till work"],
    }
    sent = fake_claude(rig["app"], reply=json.dumps(reply))
    user = await rig["person"]("recruiter", rig["a"])
    made = await _upload(user, cv_docx(CV_LINES), job_description="Serve customers in a shop.")
    assert made.status_code == 200, made.text
    body = made.json()
    assert body["soc_code"] == "7111"
    assert body["score"] == 72
    assert body["low_confidence"] is False
    assert body["removed"] == ["link", "email", "phone", "postcode", "address"]
    assert [item["quote"] for item in body["evidence"]] == ["Served customers at the till"]
    assert body["gaps"] == ["No food hygiene certificate shown"]
    # The payload to Claude: the job and the cleaned CV, with no contact details.
    assert len(sent) == 1
    for secret in (
        "ann.smith@example.com",
        "07700 900123",
        "14 Cedar Park Road",
        "LS1 4AP",
        "linkedin.com",
    ):
        assert secret not in sent[0]
    assert find_restricted(sent[0]) == []
    assert "Served customers at the till" in sent[0]
    assert "Serve customers in a shop." in sent[0]
