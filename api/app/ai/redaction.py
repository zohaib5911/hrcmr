"""What may leave the server for the AI provider (plan.md 8.12): the redaction layer.

Everything sent to Anthropic goes through ``scrub`` first and ``assert_clean`` last:

- restricted fields (NI number, bank details, passport, visa, share code, CoS number, health or
  sickness, salary, home address, date of birth) are dropped by key, whatever their value;
- names are swapped for labels (``Employee A``) by a ``Pseudonymiser``, which maps them back in the
  answer the user sees;
- any text that still looks like one of those identifiers is replaced with ``[redacted]``.

``assert_clean`` runs on the exact request body just before it is sent, and refuses to send it if
a restricted pattern survived. It names the pattern, never the value.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[redacted]"

# Keys are compared after lower-casing and turning every non-alphanumeric run into "_".
# A key is restricted when any of these fragments appears in it.
RESTRICTED_KEY_FRAGMENTS = (
    "ni_number",
    "national_insurance",
    "nino",
    "bank",
    "sort_code",
    "account_number",
    "account_no",
    "iban",
    "passport",
    "visa",
    "brp",
    "share_code",
    "cos_number",
    "cos_ref",
    "certificate_of_sponsorship",
    "health",
    "sick",
    "medical",
    "salary",
    "wage",
    "pay_rate",
    "hourly_rate",
    "annual_pay",
    "address",
    "postcode",
    "date_of_birth",
    "birth",
    "dob",
    "email",
    "phone",
    "mobile",
)
NAME_KEYS = frozenset(
    {"name", "full_name", "employee_name", "display_name", "preferred_name", "manager_name"}
)
NAME_PART_KEYS = frozenset({"first_name", "last_name", "middle_name", "surname", "given_name"})

# Value patterns, named so a refusal can say which kind of identifier was caught.
PATTERNS: dict[str, re.Pattern[str]] = {
    "ni_number": re.compile(
        r"(?i)\b[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b"
    ),
    "salary": re.compile(
        r"(?i)(?:£|\bGBP\s?)\s?\d[\d,]*(?:\.\d+)?k?"
        r"|\b\d[\d,]*(?:\.\d+)?k?\s?(?:GBP|pounds?|per\s(?:annum|year|hour|week|month)|p\.a\.|pa\b"
        r"|/\s?(?:yr|year|hr|hour|week|month))"
    ),
    "sort_code": re.compile(r"\b\d{2}[- ]\d{2}[- ]\d{2}\b|\b\d{6}\b"),
    "account_number": re.compile(r"\b\d{8}\b"),
    "passport": re.compile(r"(?i)\b(?:[A-Z]{2}\d{7}|\d{9})\b"),
    "share_code": re.compile(
        r"\b(?=[A-Z0-9 -]{0,10}\d)[A-Z][A-Z0-9]{2}[ -]?[A-Z0-9]{3}[ -]?[A-Z0-9]{3}\b"
    ),
    "cos_number": re.compile(r"\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{10,12}\b"),
    "email": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    "phone": re.compile(r"(?<!\w)(?:\+44\s?|0)\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}\b"),
}


class RestrictedDataError(Exception):
    """An outgoing AI request still held restricted data. ``kinds`` names the patterns found."""

    def __init__(self, kinds: list[str]) -> None:
        super().__init__(f"Restricted data in the AI request: {', '.join(kinds)}")
        self.kinds = kinds


def _norm_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def is_restricted_key(key: str) -> bool:
    norm = _norm_key(key)
    return any(fragment in norm for fragment in RESTRICTED_KEY_FRAGMENTS)


def find_restricted(text: str) -> list[str]:
    """The kinds of restricted identifier that appear in ``text`` (empty when clean)."""
    return [kind for kind, pattern in PATTERNS.items() if pattern.search(text)]


def redact_text(text: str) -> str:
    for pattern in PATTERNS.values():
        text = pattern.sub(REDACTED, text)
    return text


def _label(index: int) -> str:
    """A, B, ... Z, AA, AB, ..."""
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return f"Employee {letters}"


class Pseudonymiser:
    """Swaps employee names for stable labels within one request, and back again afterwards."""

    def __init__(self) -> None:
        self._labels: dict[str, str] = {}  # name (folded) -> label
        self._names: dict[str, str] = {}  # label -> name as first seen

    def label(self, name: str) -> str:
        clean = " ".join(name.split())
        if not clean:
            return clean
        key = clean.casefold()
        if key not in self._labels:
            label = _label(len(self._labels))
            self._labels[key] = label
            self._names[label] = clean
        return self._labels[key]

    def name_for(self, label: str) -> str | None:
        return self._names.get(label)

    def replace_names(self, text: str) -> str:
        """Replace every known name in free text with its label (longest names first)."""
        for label, name in sorted(self._names.items(), key=lambda item: -len(item[1])):
            text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", label, text, flags=re.IGNORECASE)
        return text

    def restore(self, text: str) -> str:
        """Map labels in the model's answer back to names, for the user's eyes only."""
        if not self._names:
            return text
        labels = sorted(self._names, key=len, reverse=True)
        pattern = re.compile(r"\b(?:" + "|".join(re.escape(label) for label in labels) + r")\b")
        return pattern.sub(lambda match: self._names[match.group(0)], text)


def scrub(value: Any, pseudonymiser: Pseudonymiser | None = None) -> Any:
    """A safe-to-send copy: restricted keys dropped, names labelled, text redacted."""
    pseudo = pseudonymiser or Pseudonymiser()
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            norm = _norm_key(name)
            if norm in NAME_PART_KEYS or is_restricted_key(name):
                continue
            if norm in NAME_KEYS and isinstance(item, str):
                result[name] = pseudo.label(item)
                continue
            result[name] = scrub(item, pseudo)
        return result
    if isinstance(value, list | tuple | set | frozenset):
        return [scrub(item, pseudo) for item in value]
    if isinstance(value, str):
        return redact_text(pseudo.replace_names(value))
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int | float):
        # Figures go as numbers; one that reads like an identifier (8-digit account) is dropped.
        return REDACTED if find_restricted(str(value)) else value
    return redact_text(pseudo.replace_names(str(value)))


def assert_clean(body: str) -> None:
    """Refuse an outgoing request body that still holds a restricted pattern."""
    kinds = find_restricted(body)
    if kinds:
        raise RestrictedDataError(kinds)
