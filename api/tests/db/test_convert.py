"""T11.5 convert to employee: an accepted offer and a verified right-to-work check, both or nothing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from app.db.session import TenantSession
from app.modules.files.models import File
from tests.db.test_applications import open_posting
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig

API = "/api/v1"


async def application(
    admin: Any, title: str, email: str | None = "nora@example.com"
) -> tuple[str, str]:
    posting = await open_posting(admin, title)
    body: dict[str, Any] = {"first_name": "Nora", "last_name": "Kent"}
    if email is not None:
        body["email"] = email
    who = (await admin.post(API + "/candidates", json=body)).json()["id"]
    made = await admin.post(
        API + "/applications", json={"candidate_id": who, "posting_id": posting}
    )
    assert made.status_code == 201, made.text
    return str(who), str(made.json()["id"])


async def accepted_offer(admin: Any, app: str, *, status: str = "accepted") -> None:
    made = await admin.post(
        f"{API}/applications/{app}/offers",
        json={
            "role_title": "Chef",
            "salary": "30000",
            "salary_per": "year",
            "start_date": "2026-12-01",
        },
    )
    assert made.status_code == 201, made.text
    offer = made.json()["id"]
    assert (await admin.patch(f"{API}/offers/{offer}", json={"status": "sent"})).status_code == 200
    if status == "accepted":
        assert (
            await admin.patch(f"{API}/offers/{offer}", json={"status": "accepted"})
        ).status_code == 200


async def verified_check(rig: dict[str, Any], admin: Any, who: str) -> None:
    """A clean piece of evidence (inserted as a scan would leave it) and a verified check that cites it."""
    async with TenantSession(rig["owner"], company_id=rig["a"]) as db:
        proof = File(
            id=uuid.uuid4(),
            company_id=rig["a"],
            storage_key=str(uuid.uuid4()),
            original_name="passport.pdf",
            mime="application/pdf",
            size=1,
            sha256="b" * 64,
            scan_status="clean",
            owner_type="candidate",
            owner_id=uuid.UUID(who),
        )
        db.add(proof)
        await db.commit()
        proof_id = str(proof.id)
    me = (await admin.get(API + "/auth/me")).json()["user"]["id"]
    yesterday = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    recorded = await admin.post(
        f"{API}/candidates/{who}/rtw-checks",
        json={
            "check_type": "manual_list_a",
            "check_date": yesterday,
            "checked_by_user_id": me,
            "outcome": "verified",
            "evidence_file_id": proof_id,
        },
    )
    assert recorded.status_code == 201, recorded.text
    assert recorded.json()["status"] == "verified"


async def test_no_accepted_offer_or_no_verified_check_means_no_employee(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    who, app = await application(admin, "Chef de partie")
    body = {"employee_number": "CONV-0", "hire_date": "2026-12-01"}
    no_offer = await admin.post(f"{API}/applications/{app}/convert", json=body)
    assert no_offer.status_code == 422
    assert no_offer.json()["error"]["code"] == "CONVERT_NEEDS_ACCEPTED_OFFER"
    await accepted_offer(admin, app, status="sent")
    not_accepted = await admin.post(f"{API}/applications/{app}/convert", json=body)
    assert not_accepted.json()["error"]["code"] == "CONVERT_NEEDS_ACCEPTED_OFFER"
    assert (
        await admin.patch(
            f"{API}/offers/{(await admin.get(f'{API}/applications/{app}/offers')).json()[0]['id']}",
            json={"status": "accepted"},
        )
    ).status_code == 200
    no_rtw = await admin.post(f"{API}/applications/{app}/convert", json=body)
    assert no_rtw.status_code == 422
    assert no_rtw.json()["error"]["code"] == "CONVERT_NEEDS_VERIFIED_RTW"
    me = (await admin.get(API + "/auth/me")).json()["user"]["id"]
    await admin.post(
        f"{API}/candidates/{who}/rtw-checks",
        json={
            "check_type": "manual_list_a",
            "check_date": (datetime.now(UTC) - timedelta(days=1)).date().isoformat(),
            "checked_by_user_id": me,
            "outcome": "verified",
        },
    )
    without_evidence = await admin.post(f"{API}/applications/{app}/convert", json=body)
    assert without_evidence.json()["error"]["code"] == "CONVERT_NEEDS_VERIFIED_RTW"
    async with rig["owner"].connect() as db:
        count = (
            await db.execute(
                text("select count(*) from employees where company_id=:c"), {"c": rig["a"]}
            )
        ).scalar_one()
    assert count == 0


async def test_both_gates_convert_once_with_one_audit_event(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    who, app = await application(admin, "Sous chef")
    await accepted_offer(admin, app)
    await verified_check(rig, admin, who)
    body = {"employee_number": "CONV-1", "hire_date": "2026-12-01"}
    converted = await admin.post(f"{API}/applications/{app}/convert", json=body)
    assert converted.status_code == 200, converted.text
    result = converted.json()
    assert result["application"]["stage"] == "hired"
    employee = result["employee_id"]
    profile = (await admin.get(f"{API}/employees/{employee}")).json()
    assert profile["employee_number"] == "CONV-1"
    assert profile["email"] == "nora@example.com"
    checks = (await admin.get(f"{API}/employees/{employee}/rtw-checks")).json()
    assert checks["status"] == "verified"
    async with rig["owner"].connect() as db:
        moved = (
            await db.execute(
                text(
                    "select count(*) from files where company_id=:c and owner_type='employee' and owner_id=:e"
                ),
                {"c": rig["a"], "e": uuid.UUID(employee)},
            )
        ).scalar_one()
        audits = (
            await db.execute(
                text(
                    "select count(*) from audit_events where company_id=:c and action='recruitment.candidate.converted'"
                ),
                {"c": rig["a"]},
            )
        ).scalar_one()
    assert moved == 1
    assert audits == 1
    again = await admin.post(
        f"{API}/applications/{app}/convert", json={**body, "employee_number": "CONV-2"}
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ALREADY_CONVERTED"
    async with rig["owner"].connect() as db:
        numbers = (
            await db.execute(
                text("select count(*) from employees where company_id=:c"), {"c": rig["a"]}
            )
        ).scalar_one()
    assert numbers == 1


async def test_recruiters_without_employee_rights_cannot_convert(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    recruiter = await rig["person"]("recruiter", rig["a"])
    who, app = await application(admin, "Baker")
    await accepted_offer(admin, app)
    await verified_check(rig, admin, who)
    refused = await recruiter.post(
        f"{API}/applications/{app}/convert",
        json={"employee_number": "CONV-3", "hire_date": "2026-12-01"},
    )
    assert refused.status_code == 403
