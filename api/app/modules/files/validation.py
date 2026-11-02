"""Checking an upload before anything is stored (plan.md 4.5).

Three separate questions, because a file can lie about each of them:

1. Is this kind of file allowed at all? (the extension, against a short list)
2. Is it really that kind of file? (its first bytes, which a person renaming ``.exe`` to ``.pdf``
   does not change)
3. Is it safe? (the virus scan, in the service)
"""

from __future__ import annotations

import re
import unicodedata
import zipfile
from typing import BinaryIO

MAX_BYTES = 25 * 1024 * 1024

# extension -> (kind it must really be, the MIME type we store and serve)
ALLOWED: dict[str, tuple[str, str]] = {
    "pdf": ("pdf", "application/pdf"),
    "jpg": ("jpg", "image/jpeg"),
    "jpeg": ("jpg", "image/jpeg"),
    "png": ("png", "image/png"),
    "doc": ("doc", "application/msword"),
    "docx": (
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    "xlsx": ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "csv": ("csv", "text/csv"),
}
_ZIP_LIMITS = {"entries": 10_000, "uncompressed": 200 * 1024 * 1024}
_NOT_FILENAME = re.compile(r"[\x00-\x1f\x7f/\\:*?\"<>|]+")


def extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def safe_filename(name: str | None) -> str:
    """A name fit to show and to put in a header: no path, no control characters, not too long."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = unicodedata.normalize("NFC", _NOT_FILENAME.sub("_", base)).strip(" .")
    if not base:
        return "file"
    if len(base) > 150:
        stem, dot, ext = base.rpartition(".")
        base = (stem[: 150 - len(ext) - 1] + dot + ext) if dot and len(ext) < 10 else base[:150]
    return base


def _looks_like_text(sample: bytes) -> bool:
    if b"\x00" in sample:
        return False
    if sample.startswith(b"\xef\xbb\xbf"):
        sample = sample[3:]
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError as error:
        # A multi-byte character cut by the end of the sample is fine; anything else is not text.
        if error.start < len(sample) - 4:
            return False
    controls = sum(1 for byte in sample if byte < 9 or 13 < byte < 32)
    return controls == 0


def sniff(stream: BinaryIO) -> str | None:
    """What the content really is (a key of the kinds in ``ALLOWED``), or None if unrecognised."""
    stream.seek(0)
    head = stream.read(16)
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "doc"
    if head.startswith(b"PK\x03\x04"):
        return _office_kind(stream)
    stream.seek(0)
    sample = stream.read(64 * 1024)
    return "csv" if sample and _looks_like_text(sample) else None


def _office_kind(stream: BinaryIO) -> str | None:
    stream.seek(0)
    try:
        with zipfile.ZipFile(stream) as archive:
            infos = archive.infolist()
            if len(infos) > _ZIP_LIMITS["entries"]:
                return None
            if sum(info.file_size for info in infos) > _ZIP_LIMITS["uncompressed"]:
                return None  # a zip bomb
            names = {info.filename for info in infos}
    except (zipfile.BadZipFile, OSError, ValueError):
        return None
    if "[Content_Types].xml" not in names:
        return None
    if "word/document.xml" in names:
        return "docx"
    if "xl/workbook.xml" in names:
        return "xlsx"
    return None
