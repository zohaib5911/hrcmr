"""Letter drafts from placeholder templates (T10.4), and the .docx they download as.

Every draft is built from the templates below, which hold only placeholders such as
``[Employee name]``. When AI is on for the company (T14.5), Claude writes the main paragraphs from
the letter type, tone and key points only; the greeting and sign-off stay as templated. Names and
identifiers cannot be sent in: the request model refuses unknown fields, and key points with an
e-mail address or NI number are rejected.
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Annotated, Literal
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field, StringConstraints, field_validator
from sqlalchemy import select

from app.ai.redaction import find_restricted
from app.ai.service import ai_ready, generate
from app.core.errors import AppError, ForbiddenError
from app.core.rbac_matrix import Scope, scope_for
from app.core.schemas import RequestModel
from app.modules.employees.models import Employee
from app.modules.rbac.deps import Access, require

router = APIRouter(prefix="/ai/letters", tags=["ai"])
Writes = Annotated[Access, Depends(require("document.file.write"))]


def company_wide(access: Access) -> None:
    """Letters are HR work for the whole company; an employee's own-only write is not enough."""
    if access.scope is not Scope.ALL:
        raise ForbiddenError


LetterType = Literal[
    "offer",
    "welcome",
    "disciplinary",
    "written_warning",
    "policy_explainer",
    "reference",
    "termination",
]
Tone = Literal["formal", "neutral", "friendly"]
KeyPoint = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
NI_NUMBER = re.compile(
    r"(?i)\b[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b"
)

# Each letter type: its subject line and one opening paragraph. Placeholders only.
TEMPLATES: dict[LetterType, tuple[str, str]] = {
    "offer": (
        "Offer of employment",
        "Further to our discussions, we are pleased to offer you the role of [Job title] with "
        "[Company name], starting on [Start date]. The full terms are set out in your contract.",
    ),
    "welcome": (
        "Welcome to [Company name]",
        "We are delighted to welcome you to [Company name]. Your first day is [Start date]. "
        "Below is what to expect in your first weeks.",
    ),
    "disciplinary": (
        "Invitation to a disciplinary meeting",
        "We need to meet to discuss a matter concerning your conduct at work. The meeting will "
        "take place on [Date], and you may be accompanied by a colleague or a trade union representative.",  # noqa: E501
    ),
    "written_warning": (
        "Formal written warning",
        "Following the meeting on [Date], this letter confirms a formal written warning. "
        "It will remain on your record for [Warning period].",
    ),
    "policy_explainer": (
        "Changes to our policy",
        "We are writing to explain a change to our policy that affects everyone at [Company name]. "
        "Please read the points below and contact [Contact details] with any questions.",
    ),
    "reference": (
        "Employment reference",
        "This reference confirms that [Employee name] was employed by [Company name] as [Job title] "  # noqa: E501
        "from [Start date] to [End date].",
    ),
    "termination": (
        "Notice of termination of employment",
        "We write to confirm that your employment with [Company name] will end on [End date]. "
        "This letter sets out the notice period and the final arrangements.",
    ),
}

GREETING: dict[Tone, str] = {
    "formal": "Dear [Employee name],",
    "neutral": "Dear [Employee name],",
    "friendly": "Hi [Employee name],",
}
CLOSING: dict[Tone, str] = {
    "formal": "Yours sincerely,",
    "neutral": "Kind regards,",
    "friendly": "Best wishes,",
}

# Claude writes only the middle of the letter; the greeting and sign-off stay as templated above.
LETTER_TASK = (
    "Task: write the main paragraphs of one UK HR letter. The data gives the letter type, the tone "
    "and the key points to cover. Use [square-bracket] placeholders for any detail you do not "
    "have, such as [Job title], [Start date], [Date] or [Company name]. Do not invent names, "
    "dates, pay, hours, figures or policy terms. Cover every key point, in order. Do not write the "
    "greeting, "
    "the sign-off, a subject line or any commentary: return the paragraphs only."
)


class LetterDraftIn(RequestModel):
    letter_type: LetterType
    tone: Tone = "neutral"
    key_points: list[KeyPoint] = Field(default_factory=list, max_length=10)

    @field_validator("key_points")
    @classmethod
    def no_identifiers(cls, points: list[str]) -> list[str]:
        for point in points:
            if EMAIL.search(point) or NI_NUMBER.search(point):
                raise ValueError(
                    "Remove email addresses and National Insurance numbers from the key points."
                )
        return points


class LetterDraftOut(RequestModel):
    source: Literal["template", "ai"]
    letter_type: LetterType
    tone: Tone
    title: str
    body: str


class LetterDocxIn(RequestModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    body: Annotated[str, StringConstraints(min_length=1, max_length=20000)]


def _sign_off(tone: Tone) -> list[str]:
    return ["", CLOSING[tone], "[Your name]", "[Your job title]", "[Company name]"]


def draft_text(body: LetterDraftIn) -> tuple[str, str]:
    subject, opening = TEMPLATES[body.letter_type]
    lines = [GREETING[body.tone], "", opening]
    if body.key_points:
        lines += ["", "Key points:", *(f"- {point}" for point in body.key_points)]
    lines += _sign_off(body.tone)
    return subject, "\n".join(lines)


async def _ai_paragraphs(request: Request, access: Access, body: LetterDraftIn) -> str | None:
    """Claude's paragraphs for the letter, or None when AI is off, unavailable, failed or unsafe.

    Only the letter type, tone and key points are sent. Employee names typed into a key point are
    swapped for labels first (T14.5 fix C2.1.1), so no name or identifier reaches the AI. Any AI
    error, including the rate limit, falls back to the template so the draft still works.
    """
    if scope_for(access.role, "ai.letter.draft") is None or not await ai_ready(request, access):
        return None
    rows = await access.db.execute(
        select(Employee.first_name, Employee.last_name).where(
            Employee.company_id == access.company_id
        )
    )
    names = [f"{first} {last}" for first, last in rows.all()]
    try:
        reply = await generate(
            request,
            access,
            feature="letter",
            task=LETTER_TASK,
            instruction="Write the letter paragraphs described in the data.",
            data={
                "letter_type": body.letter_type,
                "tone": body.tone,
                "key_points": body.key_points,
            },
            names=names,
            max_tokens=1200,
        )
    except AppError:
        return None
    reply = reply.strip()
    # Figures or identifiers in the answer are not trusted: the template is used instead.
    if not reply or find_restricted(reply):
        return None
    return reply


def build_docx(title: str, text: str) -> bytes:
    """A minimal Word file (one paragraph per line) built without a third-party library."""
    paragraphs = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{escape(line)}</w:t></w:r></w:p>'
        for line in text.split("\n")
    )
    xml_head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    document = (
        f"{xml_head}<w:document "
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}<w:sectPr/></w:body></w:document>"
    )
    content_types = (
        f"{xml_head}<Types "
        'xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'  # noqa: E501
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'  # noqa: E501
        "</Types>"
    )
    rels = (
        f"{xml_head}<Relationships "
        'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'  # noqa: E501
        "</Relationships>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


@router.post("/draft", response_model=LetterDraftOut)
async def create_draft(body: LetterDraftIn, request: Request, access: Writes) -> LetterDraftOut:
    company_wide(access)
    subject, text = draft_text(body)
    paragraphs = await _ai_paragraphs(request, access, body)
    if paragraphs is None:
        source: Literal["template", "ai"] = "template"
    else:
        source = "ai"
        text = "\n".join([GREETING[body.tone], "", paragraphs, *_sign_off(body.tone)])
    return LetterDraftOut(
        source=source,
        letter_type=body.letter_type,
        tone=body.tone,
        title=subject,
        body=text,
    )


@router.post("/docx", response_class=Response)
async def download_docx(body: LetterDocxIn, access: Writes) -> Response:
    company_wide(access)
    filename = re.sub(r"[^A-Za-z0-9 _-]+", "", body.title).strip() or "letter"
    return Response(
        content=build_docx(body.title, body.body),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.docx"',
            "Cache-Control": "private, no-store",
        },
    )
