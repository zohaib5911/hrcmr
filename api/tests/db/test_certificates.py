"""T13.4 certificates: a completed course gets a certificate with an unguessable reference; the PDF is
for its holder and administrators; the public check returns exactly four fields, a generic answer for
anything unknown, and is rate limited."""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.learning.loader import load_courses
from tests.db.test_employee_documents import rig as rig

API = "/api/v1"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "courses"
SLUG = "e2e-test-course"
GENERIC = "We could not find a certificate with that reference."


async def _course(rig: dict[str, Any]) -> str:
    async with AsyncSession(rig["owner"]) as db:
        await load_courses(db, FIXTURES)
        await db.commit()
    courses = (
        await (await rig["person"]("company_admin", rig["a"])).get(API + "/learning/courses")
    ).json()
    return str(next(course["id"] for course in courses if course["slug"] == SLUG))


async def _completed(rig: dict[str, Any], admin: Any, course: str) -> tuple[str, str, str]:
    """A linked employee who passes the check and completes the course. Returns the employee's name,
    the assignment id and the certificate's reference."""
    number = uuid.uuid4().hex[:10]
    made = await admin.post(
        API + "/employees",
        json={
            "first_name": "Ruth",
            "last_name": f"Holder{number}",
            "employee_number": number,
            "email": f"{number}@example.com",
            "hire_date": "2025-01-01",
        },
    )
    assert made.status_code == 201, made.text
    employee = made.json()["id"]
    me = next(u for u in (await admin.get(API + "/users")).json()["users"] if u["is_you"])
    assert (
        await admin.put(f"{API}/users/{me['id']}/employee", json={"employee_id": employee})
    ).status_code == 200
    assigned = await admin.post(
        API + "/learning/assignments",
        json={
            "course_ids": [course],
            "scope": "named",
            "employee_ids": [employee],
            "due_on": "2026-12-01",
        },
    )
    assert assigned.status_code == 201, assigned.text
    assignment = (await admin.get(API + "/learning/assignments/own")).json()[0]["id"]
    base = f"{API}/learning/assignments/{assignment}"
    assert (await admin.post(base + "/quiz", json={"answers": [2, 1]})).json()["passed"] is True
    done = await admin.post(base + "/complete")
    assert done.status_code == 200, done.text
    cert = (await admin.get(base + "/certificate")).json()
    assert len(cert["reference"]) >= 10
    return f"Ruth Holder{number}", assignment, cert["reference"]


async def test_a_completed_course_gets_a_certificate_only_its_holder_and_admins_can_download(
    rig: dict[str, Any],
) -> None:
    course = await _course(rig)
    admin = await rig["person"]("company_admin", rig["a"])
    name, assignment, reference = await _completed(rig, admin, course)
    cert_id = (await admin.get(f"{API}/learning/assignments/{assignment}/certificate")).json()["id"]

    pdf = await admin.get(f"{API}/certificates/{cert_id}.pdf")
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert "no-store" in pdf.headers["cache-control"]
    text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
    assert name in text
    assert reference in text

    stranger = await rig["person"]("company_admin", rig["b"])
    assert (await stranger.get(f"{API}/certificates/{cert_id}.pdf")).status_code == 404
    employee = await rig["person"]("employee", rig["a"])
    assert (await employee.get(f"{API}/certificates/{cert_id}.pdf")).status_code == 404


async def test_the_public_check_returns_exactly_four_fields_and_a_generic_not_found(
    rig: dict[str, Any],
) -> None:
    course = await _course(rig)
    admin = await rig["person"]("company_admin", rig["a"])
    name, _, reference = await _completed(rig, admin, course)

    # No session at all: the check is public.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=rig["app"]), base_url="http://test"
    ) as anonymous:
        found = await anonymous.get(API + "/public/certificates/verify", params={"ref": reference})
        assert found.status_code == 200, found.text
        body = found.json()
        assert set(body) == {"holder_name", "course_title", "completed_on", "status"}
        assert body["holder_name"] == name
        assert body["course_title"] == "Test course for the player"
        assert body["status"] == "valid"
        # Typed in lower case, with spaces around it, the same certificate still verifies.
        typed = f"  {reference.lower()} "
        lower = await anonymous.get(API + "/public/certificates/verify", params={"ref": typed})
        assert lower.status_code == 200, lower.text
        assert lower.json()["holder_name"] == name

        for ref in ("NOSUCHREFERENCE1", "x", "A" * 40):
            missing = await anonymous.get(API + "/public/certificates/verify", params={"ref": ref})
            assert missing.status_code == 404, ref
            assert missing.json()["error"]["message"] == GENERIC


async def test_the_public_check_is_rate_limited(rig: dict[str, Any]) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=rig["app"]), base_url="http://test"
    ) as anonymous:
        codes = []
        for number in range(31):
            response = await anonymous.get(
                API + "/public/certificates/verify", params={"ref": f"UNKNOWN{number:04d}"}
            )
            codes.append(response.status_code)
    assert codes[-1] == 429
    assert set(codes[:30]) == {404}
