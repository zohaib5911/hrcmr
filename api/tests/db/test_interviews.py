"""T11.4 interviews: invites go to the panel and the candidate, the .ics is valid, and tenants stay apart."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text

from tests.db.test_applications import candidate, open_posting
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig

API = "/api/v1"


async def test_an_interview_sends_invites_and_an_ics_file(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    # Unique addresses: the outbox is shared by every test in the run.
    stamp = uuid.uuid4().hex[:8]
    candidate_mail = f"gia-{stamp}@example.com"
    panel_mail = f"sam-panel-{stamp}@example.com"
    posting = await open_posting(admin, "Sous chef")
    who = (
        await admin.post(
            API + "/candidates",
            json={"first_name": "Gia", "last_name": "Mendes", "email": candidate_mail},
        )
    ).json()["id"]
    app = (
        await admin.post(API + "/applications", json={"candidate_id": who, "posting_id": posting})
    ).json()
    panel = (
        await admin.post(
            API + "/employees",
            json={
                "first_name": "Sam",
                "last_name": "Lee",
                "employee_number": "PANEL1",
                "email": panel_mail,
                "hire_date": "2025-01-01",
            },
        )
    ).json()["id"]
    made = await admin.post(
        f"{API}/applications/{app['id']}/interviews",
        json={
            "scheduled_at": "2026-11-12T14:30:00+00:00",
            "duration_minutes": 45,
            "mode": "video",
            "location_or_link": "https://meet.example.test/gia",
            "interviewer_employee_ids": [panel],
            "notes": "Ask about rota planning",
        },
    )
    assert made.status_code == 201, made.text
    interview = made.json()
    assert interview["outcome"] == "pending"
    assert interview["interviewers"][0]["name"] == "Sam Lee"
    async with rig["owner"].connect() as db:
        sent = (
            await db.execute(
                text(
                    "select template, to_address from email_outbox "
                    "where template like 'interview_invite%' and to_address in (:panel, :candidate) "
                    "order by template"
                ),
                {"panel": panel_mail, "candidate": candidate_mail},
            )
        ).all()
    assert [(row[0], row[1]) for row in sent] == [
        ("interview_invite", panel_mail),
        ("interview_invite_candidate", candidate_mail),
    ]
    ics = await admin.get(f"{API}/applications/{app['id']}/interviews/{interview['id']}/invite.ics")
    assert ics.status_code == 200, ics.text
    assert ics.headers["content-type"].startswith("text/calendar")
    body = ics.text
    assert "BEGIN:VEVENT" in body
    assert "END:VEVENT" in body
    assert f"UID:interview-{interview['id']}@" in body
    assert "DTSTART:20261112T143000Z" in body
    assert "DTEND:20261112T151500Z" in body
    assert f"ATTENDEE;CN=Gia Mendes;RSVP=TRUE:mailto:{candidate_mail}" in body
    assert "Ask about rota planning" not in body
    patched = await admin.patch(
        f"{API}/applications/{app['id']}/interviews/{interview['id']}", json={"outcome": "passed"}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["outcome"] == "passed"


async def test_bad_times_strangers_and_other_companies_are_refused(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    foreign = await rig["person"]("company_admin", rig["b"])
    posting = await open_posting(admin, "Host")
    who = await candidate(admin, "Hal")
    app = (
        await admin.post(API + "/applications", json={"candidate_id": who, "posting_id": posting})
    ).json()
    base = {"mode": "phone", "scheduled_at": "2026-11-12T09:00:00+00:00"}
    naive = await admin.post(
        f"{API}/applications/{app['id']}/interviews",
        json={**base, "scheduled_at": "2026-11-12T09:00:00"},
    )
    assert naive.status_code == 422
    stranger = await admin.post(
        f"{API}/applications/{app['id']}/interviews",
        json={**base, "interviewer_employee_ids": ["00000000-0000-7000-8000-000000000001"]},
    )
    assert stranger.status_code == 422
    assert (await foreign.get(f"{API}/applications/{app['id']}/interviews")).status_code == 404
