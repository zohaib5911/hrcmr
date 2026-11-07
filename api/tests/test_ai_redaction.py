"""Phase 14 gate (plan.md L1440-1441): no restricted field ever appears in an outgoing AI request.

Tool-style outputs are fuzzed with identifiers under restricted keys, under harmless keys, inside
free text, in lists and nested records. The request body is captured on the wire and checked with
patterns written here, independently of the redaction module's own.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import string
from typing import Any

import httpx
import pytest

from app.ai.redaction import Pseudonymiser, RestrictedDataError, scrub
from app.ai.service import build_prompt
from app.integrations.anthropic import Anthropic

# Independent checks, deliberately broad.
WIRE_PATTERNS = {
    "ni_number": re.compile(r"(?i)\b[A-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b"),
    "sort_code": re.compile(r"\b\d{2}[- ]?\d{2}[- ]?\d{2}\b"),
    "account_number": re.compile(r"\b\d{8}\b"),
    "passport": re.compile(r"(?i)\b(?:[A-Z]{2}\d{7}|\d{9})\b"),
    "share_code": re.compile(r"\b[A-Z][A-Z0-9]{2}\s?[A-Z0-9]{3}\s?[A-Z0-9]{3}\b"),
    "salary": re.compile(r"(?i)£\s?\d|\d\s?(?:GBP|per (?:annum|hour|year)|pa\b|k pa)"),
}
NI_FIRST = "ABCEGHJKLMNOPRSTWXYZ"
NI_SECOND = "ABCEGHJKLMNPRSTWXYZ"
FIRST = ["Amara", "Bilal", "Chloe", "Dariusz", "Ewa", "Farah", "Grace", "Hamza", "Isla", "Jonah"]
LAST = ["Okafor", "Khan", "Smith", "Nowak", "Patel", "Hughes", "Reid", "Ahmed", "Evans", "Lee"]


def digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.digits) for _ in range(n))


def ni(rng: random.Random) -> str:
    sep = rng.choice(["", " "])
    return (
        sep.join(
            [
                rng.choice(NI_FIRST) + rng.choice(NI_SECOND),
                digits(rng, 2),
                digits(rng, 2),
                digits(rng, 2),
            ]
        )
        + sep
        + rng.choice("ABCD")
    )


def sort_code(rng: random.Random) -> str:
    sep = rng.choice(["-", " ", ""])
    return sep.join(digits(rng, 2) for _ in range(3))


def passport(rng: random.Random) -> str:
    if rng.random() < 0.5:
        return digits(rng, 9)
    return rng.choice(string.ascii_uppercase) + rng.choice(string.ascii_uppercase) + digits(rng, 7)


def share_code(rng: random.Random) -> str:
    body = [rng.choice(string.ascii_uppercase + string.digits) for _ in range(8)]
    body[rng.randrange(8)] = rng.choice(string.digits)
    code = rng.choice("WRS") + "".join(body)
    return f"{code[:3]} {code[3:6]} {code[6:]}" if rng.random() < 0.5 else code


def salary(rng: random.Random) -> str:
    amount = rng.randint(12, 120) * 1000 + rng.choice([0, 250, 500])
    return rng.choice(
        [
            f"£{amount:,}",
            f"£{amount}",
            f"£{rng.randint(11, 40)}.{digits(rng, 2)} per hour",
            f"{amount} GBP",
            f"{amount // 1000}k pa",
            f"{amount:,} per annum",
        ]
    )


GENERATORS = {
    "ni_number": ni,
    "sort_code": sort_code,
    "account_number": lambda rng: digits(rng, 8),
    "passport": passport,
    "share_code": share_code,
    "salary": salary,
}
RESTRICTED_KEYS = {
    "ni_number": ["ni_number", "nationalInsuranceNumber", "NI number"],
    "sort_code": ["sort_code", "bankSortCode", "bank_details"],
    "account_number": ["account_number", "bank_account_number", "accountNo"],
    "passport": ["passport_number", "passportNo", "visa_number", "brp_number"],
    "share_code": ["share_code", "shareCode", "rtw_share_code"],
    "salary": ["salary", "annual_salary", "hourlyRate", "pay_rate", "wage"],
}
OTHER_RESTRICTED = {
    "home_address": "12 Acacia Avenue, Leeds",
    "postcode": "LS1 4AP",
    "date_of_birth": "1990-04-12",
    "sickness_notes": "back pain, 3 days",
    "health_condition": "asthma",
    "cos_number": "C2G8X12345Y",
}
HARMLESS_KEYS = ["note", "summary", "comment", "detail", "status_text", "label"]


def fuzz_record(rng: random.Random) -> tuple[dict[str, Any], list[str]]:
    """One tool-style output, plus the names placed in it."""
    names = [f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(rng.randint(1, 3))]
    record: dict[str, Any] = {
        "employee_name": names[0],
        "first_name": names[0].split()[0],
        "last_name": names[0].split()[1],
        "headcount": rng.randint(1, 400),
        "on_leave_today": rng.randint(0, 20),
    }
    for kind, make in GENERATORS.items():
        # Under its own restricted key...
        record[rng.choice(RESTRICTED_KEYS[kind])] = make(rng)
        # ...hidden in free text under a harmless key...
        record[f"{rng.choice(HARMLESS_KEYS)}_{kind}"] = (
            f"{rng.choice(names)} said {make(rng)} was on the form"
        )
    record.update(rng.sample(sorted(OTHER_RESTRICTED.items()), k=3))
    # ...and nested inside lists of records.
    record["team"] = [
        {"name": name, "detail": f"ref {rng.choice(list(GENERATORS.values()))(rng)}"}
        for name in names
    ]
    return record, names


def capture_body(data: Any) -> str:
    sent: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.content)
        return httpx.Response(
            200, json={"model": "m", "content": [{"type": "text", "text": "ok"}], "usage": {}}
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = Anthropic("k", model_main="m", model_fast="m", client=http)
            prompt = build_prompt("Summarise this for HR.", data, Pseudonymiser())
            await client.complete(system="s", messages=[{"role": "user", "content": prompt}])

    asyncio.run(run())
    assert len(sent) == 1
    return sent[0].decode("utf-8")


@pytest.mark.parametrize("seed", range(200))
def test_fuzzed_tool_output_never_leaks_restricted_fields(seed: int) -> None:
    rng = random.Random(seed)  # noqa: S311  (seeded so a failure can be replayed)
    record, names = fuzz_record(rng)
    body = capture_body(record)
    for kind, pattern in WIRE_PATTERNS.items():
        assert not pattern.search(body), f"{kind} reached the wire (seed {seed})"
    for value in OTHER_RESTRICTED.values():
        assert value not in body
    for name in names:
        for part in name.split():
            assert part not in body, f"name reached the wire (seed {seed})"
    # Aggregate figures still go through.
    assert str(record["headcount"]) in json.loads(body)["messages"][0]["content"]


def test_unscrubbed_body_is_refused_before_sending() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"content": []})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = Anthropic("k", model_main="m", model_fast="m", client=http)
            await client.complete(system="s", messages=[{"role": "user", "content": "AB123456C"}])

    with pytest.raises(RestrictedDataError) as error:
        asyncio.run(run())
    assert "ni_number" in error.value.kinds
    assert not called


def test_labels_map_back_to_names_for_the_user() -> None:
    pseudo = Pseudonymiser()
    safe = scrub({"name": "Amara Okafor", "items": [{"employee_name": "Bilal Khan"}]}, pseudo)
    assert safe == {"name": "Employee A", "items": [{"employee_name": "Employee B"}]}
    assert (
        pseudo.restore("Employee B covers for Employee A.") == "Bilal Khan covers for Amara Okafor."
    )
