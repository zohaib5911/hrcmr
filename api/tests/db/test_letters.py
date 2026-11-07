"""T10.4 letter drafts from placeholder templates: no AI call, no names or identifiers accepted."""

from __future__ import annotations

import io
import zipfile
from typing import Any

from tests.db.test_employee_documents import rig as rig

API = "/api/v1/ai"


async def test_template_draft_uses_placeholders_and_works_without_a_key(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    made = await admin.post(
        API + "/letters/draft",
        json={
            "letter_type": "offer",
            "tone": "formal",
            "key_points": ["Probation lasts six months", "Hours are 37.5 a week"],
        },
    )
    assert made.status_code == 200, made.text
    body = made.json()
    assert body["source"] == "template"
    assert body["title"] == "Offer of employment"
    assert body["body"].startswith("Dear [Employee name],")
    assert "[Start date]" in body["body"]
    assert "- Probation lasts six months" in body["body"]
    assert "@" not in body["body"]
    me = (await admin.get(API.replace("/ai", "/auth") + "/me")).json()
    assert isinstance(me["ai_available"], bool)


async def test_names_identifiers_and_too_many_points_are_refused(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    named = await admin.post(
        API + "/letters/draft",
        json={"letter_type": "termination", "employee_name": "Amira Hassan"},
    )
    assert named.status_code == 422
    email = await admin.post(
        API + "/letters/draft",
        json={"letter_type": "reference", "key_points": ["Contact amira@example.com"]},
    )
    assert email.status_code == 422
    ni = await admin.post(
        API + "/letters/draft",
        json={"letter_type": "reference", "key_points": ["NI number AB 12 34 56 C"]},
    )
    assert ni.status_code == 422
    many = await admin.post(
        API + "/letters/draft",
        json={"letter_type": "welcome", "key_points": [f"Point {n}" for n in range(11)]},
    )
    assert many.status_code == 422
    unknown_type = await admin.post(API + "/letters/draft", json={"letter_type": "fine"})
    assert unknown_type.status_code == 422


async def test_employees_cannot_draft_and_docx_is_a_word_package(rig: dict[str, Any]) -> None:
    employee = await rig["person"]("employee", rig["a"])
    denied = await employee.post(
        API + "/letters/draft", json={"letter_type": "welcome", "tone": "friendly"}
    )
    assert denied.status_code == 403
    assert (
        await employee.post(API + "/letters/docx", json={"title": "x", "body": "y"})
    ).status_code == 403
    admin = await rig["person"]("company_admin", rig["a"])
    made = await admin.post(
        API + "/letters/docx",
        json={"title": "Welcome letter", "body": "Hi [Employee name],\n\nWelcome & thanks"},
    )
    assert made.status_code == 200, made.text
    assert made.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    with zipfile.ZipFile(io.BytesIO(made.content)) as archive:
        assert {"[Content_Types].xml", "_rels/.rels", "word/document.xml"} <= set(
            archive.namelist()
        )
        assert "Welcome &amp; thanks" in archive.read("word/document.xml").decode()
