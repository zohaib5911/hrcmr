"""T14.3 search: a person without employee.profile.read gets no employees; another company's names are
never returned; a query needs two characters; each group is capped at eight."""

from __future__ import annotations

import uuid
from typing import Any

from tests.db.test_employee_documents import rig as rig

API = "/api/v1"


async def _staff(admin: Any, first: str, last: str) -> str:
    number = uuid.uuid4().hex[:10]
    made = await admin.post(
        API + "/employees",
        json={
            "first_name": first,
            "last_name": last,
            "employee_number": number,
            "email": f"{number}@example.com",
            "hire_date": "2025-01-01",
        },
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


async def test_a_short_query_finds_nothing(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    await _staff(admin, "Zara", "Uniq")
    assert (await admin.get(API + "/search", params={"q": "z"})).json() == {
        "people": [],
        "candidates": [],
    }
    assert (await admin.get(API + "/search", params={"q": " "})).json() == {
        "people": [],
        "candidates": [],
    }


async def test_a_person_without_employee_profile_read_gets_no_employees(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    ident = await _staff(admin, "Yara", "Hidden")
    found = (await admin.get(API + "/search", params={"q": "yara"})).json()
    assert [person["id"] for person in found["people"]] == [ident]
    assert found["people"][0]["link"] == f"/employees/{ident}"
    employee = await rig["person"]("employee", rig["a"])
    assert (await employee.get(API + "/search", params={"q": "yara"})).json()["people"] == []
    assert (await employee.get(API + "/search", params={"q": "yara"})).json()["candidates"] == []


async def test_other_companies_names_are_never_returned(rig: dict[str, Any]) -> None:
    admin_a = await rig["person"]("company_admin", rig["a"])
    await _staff(admin_a, "Xenia", "Private")
    admin_b = await rig["person"]("company_admin", rig["b"])
    assert (await admin_b.get(API + "/search", params={"q": "xenia"})).json()["people"] == []
    assert (await admin_a.get(API + "/search", params={"q": "xenia"})).json()["people"] != []


async def test_each_group_is_capped_at_eight(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    for number in range(10):
        await _staff(admin, f"Wilma{number}", "Capped")
    found = (await admin.get(API + "/search", params={"q": "capped"})).json()
    assert len(found["people"]) == 8
