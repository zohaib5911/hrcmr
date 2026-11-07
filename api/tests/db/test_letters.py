"""T10.4 letter drafts from placeholder templates; T14.5 Claude paragraphs with a template fallback."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from sqlalchemy import text

from app.ai.redaction import find_restricted
from tests.db.api_support import fake_claude
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


async def test_ai_draft_wraps_claude_paragraphs_and_sends_only_type_tone_and_points(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    sent = fake_claude(
        rig["app"], reply="Your first day is [Start date].\n\nProbation lasts six months."
    )
    made = await admin.post(
        API + "/letters/draft",
        json={
            "letter_type": "welcome",
            "tone": "friendly",
            "key_points": ["Probation lasts six months"],
        },
    )
    assert made.status_code == 200, made.text
    body = made.json()
    assert body["source"] == "ai"
    assert body["title"] == "Welcome to [Company name]"
    assert body["body"] == (
        "Hi [Employee name],\n\nYour first day is [Start date].\n\n"
        "Probation lasts six months.\n\nBest wishes,\n[Your name]\n[Your job title]\n[Company name]"
    )
    assert len(sent) == 1
    # Only the letter type, tone and key points leave the server: no names, e-mails or figures.
    assert find_restricted(sent[0]) == []
    assert "@" not in sent[0]
    user_message = json.loads(sent[0])["messages"][0]["content"]
    assert "welcome" in user_message
    assert "friendly" in user_message
    assert "Probation lasts six months" in user_message


async def test_ai_failure_and_unsafe_answers_fall_back_to_the_template(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    fake_claude(rig["app"], status=500)
    down = await admin.post(API + "/letters/draft", json={"letter_type": "offer"})
    assert down.status_code == 200, down.text
    assert down.json()["source"] == "template"
    assert down.json()["body"].startswith("Dear [Employee name],")
    fake_claude(rig["app"], reply="The pay is £45,000 a year.")
    unsafe = await admin.post(API + "/letters/draft", json={"letter_type": "offer"})
    assert unsafe.status_code == 200, unsafe.text
    assert unsafe.json()["source"] == "template"
    assert "£" not in unsafe.json()["body"]


async def test_company_ai_switch_off_means_template_and_no_call(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    async with rig["owner"].begin() as connection:
        await connection.execute(
            text("update companies set ai_features_enabled = false where id = :c"),
            {"c": rig["a"]},
        )
    sent = fake_claude(rig["app"], reply="Anything at all.")
    made = await admin.post(API + "/letters/draft", json={"letter_type": "termination"})
    assert made.status_code == 200, made.text
    assert made.json()["source"] == "template"
    assert sent == []
    async with rig["owner"].begin() as connection:
        await connection.execute(
            text("update companies set ai_features_enabled = true where id = :c"),
            {"c": rig["a"]},
        )
