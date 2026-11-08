"""Reading a CV and removing its contact details before anything is sent to AI (plan 8.17, T15.5).

``extract_text`` turns a PDF (pypdf) or a DOCX (its XML, parsed with defusedxml) into plain text.
``strip_contact_details`` replaces e-mail addresses, phone numbers, UK postcodes, street addresses
and web links with a short placeholder, and says which kinds it removed. The stripping is pattern
based: it catches the common formats, not every possible one, so the AI request is also checked by
the redaction layer (app/ai) before it leaves the server.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass

from defusedxml import ElementTree
from pypdf import PdfReader

MAX_PAGES = 30
MAX_TEXT_CHARS = 60_000
MAX_XML_BYTES = 20 * 1024 * 1024  # the uncompressed word/document.xml, a zip-bomb guard
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class CvUnreadableError(Exception):
    """The file is a CV in name only: it cannot be opened, or has no text in it."""


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
LINK = re.compile(
    r"(?:https?://|www\.)\S+|\b(?:linkedin|github|gitlab|twitter|facebook|instagram)\.com/\S*",
    re.IGNORECASE,
)
# A phone number: "+44 7700 900123", "+1 (555) 123-4567", or a UK national number of 10 or 11 digits
# that starts with 0: "07700 900 123", "(01234) 567890", "0800 123 4567". A CV date range such as
# "05 2019 - 06 2023" has 12 digits and so is not a phone number.
PHONE = re.compile(
    r"(?<![\w/])"
    r"(?:\+\d{1,3}[\s.()-]*\d(?:[\s().-]*\d){6,11}"
    r"|\(?0\d(?:[\s().-]*\d){8,9})"
    r"(?!\w)"
)
POSTCODE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b", re.IGNORECASE)
# Street types, as whole words. Words that also read as ordinary CV words (green, row, view) are
# left out, so "3 years working at green" is not taken for an address.
STREET_TYPES = (
    "street|st|road|rd|lane|ln|avenue|ave|close|drive|dr|way|gardens|gdns|terrace|court|ct|"
    "place|pl|crescent|square|grove|hill|park|walk|rise|mews|parade"
)
# A house number, then one to three capitalised words on the same line, then a street type:
# "14 Cedar Park Road", "7 Mill Lane". Only the street type is matched without regard to case.
STREET = re.compile(
    rf"\b\d{{1,4}}[A-Za-z]?[ \t]+(?:[A-Z][\w'-]*[ \t]+){{0,3}}(?i:{STREET_TYPES})\b\.?"
)

# The order matters: links and e-mails first, so their digits are not read as a phone number.
RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("link", LINK),
    ("email", EMAIL),
    ("phone", PHONE),
    ("postcode", POSTCODE),
    ("address", STREET),
)
PLACEHOLDER = {
    "link": "[link removed]",
    "email": "[email removed]",
    "phone": "[phone removed]",
    "postcode": "[postcode removed]",
    "address": "[address removed]",
}


@dataclass(frozen=True)
class Stripped:
    cleaned: str
    removed: tuple[str, ...]  # the kinds found, in the order the rules run, each at most once


def strip_contact_details(text: str) -> Stripped:
    removed: list[str] = []
    for kind, pattern in RULES:
        text, count = pattern.subn(PLACEHOLDER[kind], text)
        if count:
            removed.append(kind)
    return Stripped(cleaned=text, removed=tuple(removed))


def extract_text(data: bytes, kind: str) -> str:
    """The plain text of a PDF (``kind`` "pdf") or a DOCX (``kind`` "docx").

    Raises CvUnreadableError when the file cannot be opened or holds no text, for example a scanned
    page with no text layer.
    """
    if kind == "pdf":
        text = _pdf_text(data)
    elif kind == "docx":
        text = _docx_text(data)
    else:
        raise CvUnreadableError
    text = text.strip()
    if not text:
        raise CvUnreadableError
    return text[:MAX_TEXT_CHARS]


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")  # an empty owner password, as most CVs have; otherwise unreadable
        pages = reader.pages[:MAX_PAGES]
        return "\n".join(page.extract_text() or "" for page in pages)
    except Exception as exc:  # pypdf raises many types for a broken file; all mean "unreadable"
        raise CvUnreadableError from exc


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > MAX_XML_BYTES:
                raise CvUnreadableError
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError, ValueError, OSError) as exc:
        raise CvUnreadableError from exc
    paragraphs = ["".join(paragraph.itertext()) for paragraph in root.iter(f"{WORD_NS}p")]
    return "\n".join(paragraphs)
