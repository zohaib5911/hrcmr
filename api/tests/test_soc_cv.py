"""T15.5, no database: contact details are taken out of a CV before anything is sent to AI, CVs are
read from PDF and DOCX, and a quote Claude invents is dropped. The endpoint, with the AI mocked, is
in tests/db/test_soc_cv.py."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from app.modules.soc.cv import CvUnreadableError, extract_text, strip_contact_details
from app.modules.soc.cv_match import parse_cv_reply

PDF_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cv" / "sample-cv.pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def cv_docx(paragraphs: list[str]) -> bytes:
    """A minimal DOCX with one paragraph per line, enough for the reader and the file check."""
    body = "".join(f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>" for text in paragraphs)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("kind", "detail"),
    [
        ("email", "ann.smith@example.com"),
        ("email", "a_b+cv@mail.co.uk"),
        ("email", "J.DOE@Company-Name.org"),
        ("phone", "07700 900123"),
        ("phone", "07700900123"),
        ("phone", "07700 900 123"),
        ("phone", "020 7946 0958"),
        ("phone", "(01234) 567890"),
        ("phone", "0800 123 4567"),
        ("phone", "+44 7700 900123"),
        ("phone", "+44 (0)7700 900123"),
        ("phone", "+1 (555) 123-4567"),
        ("postcode", "SW1A 1AA"),
        ("postcode", "M1 1AE"),
        ("postcode", "B33 8TH"),
        ("postcode", "cr2 6xh"),
        ("postcode", "DN55 1PT"),
        ("address", "14 Cedar Park Road"),
        ("address", "7 Mill Lane"),
        ("address", "Flat 3, 12 Oak Street"),
        ("address", "221 Baker Street"),
        ("link", "https://www.linkedin.com/in/ann-smith"),
        ("link", "www.example.com/cv"),
        ("link", "linkedin.com/in/annsmith"),
        ("link", "github.com/annsmith"),
    ],
)
def test_each_kind_of_contact_detail_is_taken_out(kind: str, detail: str) -> None:
    stripped = strip_contact_details(f"Contact: {detail}, thanks.")
    assert detail not in stripped.cleaned
    assert kind in stripped.removed
    assert f"[{kind} removed]" in stripped.cleaned


def test_contact_details_are_taken_out_together_and_each_kind_is_reported_once() -> None:
    cv = (
        "Ann Smith, ann@example.com, 07700 900123.\n"
        "14 Cedar Park Road, Leeds LS1 4AP\n"
        "https://www.linkedin.com/in/ann-smith\n"
        "Second e-mail: other@example.com"
    )
    stripped = strip_contact_details(cv)
    assert stripped.removed == ("link", "email", "phone", "postcode", "address")
    for secret in ("ann@example.com", "other@example.com", "07700 900123", "LS1 4AP", "Cedar"):
        assert secret not in stripped.cleaned


@pytest.mark.parametrize(
    "line",
    [
        "05 2019 - 06 2023",
        "2019 - 2023",
        "Sales assistant since 2019",
        "3 years working at green",
        "Salary of £30,000 a year",
        "Level 3 diploma in 2021",
        "Worked 37.5 hours a week",
        "ISO 9001 certified",
        "BSc Hons 2:1",
    ],
)
def test_ordinary_cv_text_is_left_alone(line: str) -> None:
    stripped = strip_contact_details(line)
    assert stripped.cleaned == line
    assert stripped.removed == ()


def test_a_docx_gives_its_paragraphs() -> None:
    text = extract_text(cv_docx(["Ann Smith", "Served customers & stocked shelves."]), "docx")
    assert text == "Ann Smith\nServed customers & stocked shelves."


def test_a_pdf_gives_its_text_and_its_contact_details_are_removed() -> None:
    text = extract_text(PDF_FIXTURE.read_bytes(), "pdf")
    assert "Served customers at the till" in text
    stripped = strip_contact_details(text)
    assert "ann.smith@example.com" not in stripped.cleaned
    assert "07700 900123" not in stripped.cleaned
    assert stripped.removed == ("email", "phone")


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        (b"not a pdf at all", "pdf"),
        (cv_docx(["   "]), "docx"),  # no text, for example a scanned page
        (b"", "docx"),
        (b"%PDF-1.4 truncated", "pdf"),
    ],
)
def test_a_file_without_readable_text_is_refused(data: bytes, kind: str) -> None:
    with pytest.raises(CvUnreadableError):
        extract_text(data, kind)


def test_a_quote_that_is_not_in_the_cv_is_dropped() -> None:
    cv = "Served customers at the till for three years."
    reply = json.dumps(
        {
            "score": 64,
            "evidence": [
                {"quote": "served customers at the till", "point": "Retail service"},
                {"quote": "Managed a team of twelve", "point": "Invented by the model"},
                {"quote": "   ", "point": "Blank"},
            ],
            "gaps": ["No food hygiene certificate shown"],
            "suggestions": ["Ask for a reference on till work"],
        }
    )
    parsed = parse_cv_reply(reply, cv)
    assert parsed is not None
    assert parsed.score == 64
    assert [item.quote for item in parsed.evidence] == ["served customers at the till"]
    assert parsed.gaps == ["No food hygiene certificate shown"]


def test_a_reply_that_is_not_the_json_asked_for_is_not_trusted() -> None:
    assert parse_cv_reply("Here is my view: a good match.", "Served customers.") is None
    assert parse_cv_reply('{"score": 120, "evidence": []}', "Served customers.") is None
