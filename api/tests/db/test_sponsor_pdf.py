"""Sponsor PDF retains versions and change snapshots without exposing identifiers or secrets."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from typing import Any

from pypdf import PdfReader
from sqlalchemy import text

from tests.db.test_sponsor_documents import COS, REFERENCE, _employee
from tests.db.test_sponsor_documents import _keys as _keys
from tests.db.test_sponsor_documents import rig as rig
from tests.reporting_calendar import seed_reporting_calendar

API = "/api/v1"


async def test_sponsor_pdf_versions_rtw_reporting_snapshots_masking_and_permissions(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "PDF100")
    other = await _employee(rig, rig["b"], "OTHER")
    user = next(
        u["user_id"] for u in (await admin.get(API + "/users")).json()["users"] if u["is_you"]
    )
    await seed_reporting_calendar(rig["owner"])
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update employees set first_name='<script>Employee</script>' where id=:i"),
            {"i": emp},
        )
    today = datetime.now(UTC).date()
    visa = {
        "doc_type": "visa",
        "visa_route": "skilled_worker",
        "reference_number": REFERENCE,
        "cos_number": COS,
        "sponsored_salary": "37000.00",
        "expiry_date": str(today + timedelta(days=21)),
    }
    first = await admin.post(f"{API}/employees/{emp}/sponsor-documents", json=visa)
    assert first.status_code == 201, first.text
    change = await admin.post(
        f"{API}/employees/{emp}/changes",
        json={
            "change_type": "salary_reduced",
            "change_date": "2026-08-28",
            "job_title": "Original role snapshot",
            "ack_inform_hr": True,
            "ack_home_office_interview": True,
            "documents_snapshot": [first.json()["id"]],
        },
    )
    assert change.status_code == 201, change.text
    reported = await admin.post(
        f"{API}/changes/{change.json()['id']}/mark-reported",
        json={"reported_date": "2026-09-14", "reference": "SMS-PDF-100"},
    )
    assert reported.status_code == 200, reported.text
    version = await admin.post(
        f"{API}/sponsor-documents/{first.json()['id']}/versions",
        json={**visa, "expiry_date": str(today + timedelta(days=120))},
    )
    assert version.status_code == 201, version.text
    withdrawn = await admin.post(
        f"{API}/sponsor-documents/{version.json()['id']}/withdraw",
        json={"reason": "Sponsorship ended"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    rtw = await admin.post(
        f"{API}/employees/{emp}/rtw-checks",
        json={
            "check_type": "online_share_code",
            "share_code": "W12345678",
            "check_date": str(today),
            "checked_by_user_id": user,
            "outcome": "verified",
        },
    )
    assert rtw.status_code == 201, rtw.text
    for role in ("company_admin", "hr_admin"):
        client = await rig["person"](role, rig["a"])
        response = await client.get(f"{API}/employees/{emp}/sponsor-record.pdf")
        assert response.status_code == 200, response.text
        assert response.content.startswith(b"%PDF-")
        assert "no-store" in response.headers["cache-control"]
        output = "\n".join(
            page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages
        )
        assert "Sponsor compliance record" in output
        assert "Original role snapshot" in output
        assert "SMS-PDF-100" in output
        assert "Visa · version 1" in output
        assert "Sponsorship ended" in output
        assert "superseded" in output
        assert "withdrawn" in output
        assert "37000.00" in output
        for private in (REFERENCE, COS, "W12345678", str(emp), first.json()["id"], user):
            assert private not in output
        assert (await client.get(f"{API}/employees/{other}/sponsor-record.pdf")).status_code == 404
    for role in ("employee", "people_manager", "recruiter", "read_only_auditor"):
        client = await rig["person"](role, rig["a"])
        assert (await client.get(f"{API}/employees/{emp}/sponsor-record.pdf")).status_code == 403
    async with rig["owner"].connect() as c:
        assert (
            await c.execute(
                text(
                    "select count(*) from audit_events where action='employee.sponsor_record_exported' and entity_id=:e"
                ),
                {"e": emp},
            )
        ).scalar_one() == 2
