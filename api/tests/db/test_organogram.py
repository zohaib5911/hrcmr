"""T12.1 org chart: the tree follows Reporting Authority, a loop cannot hang it, RTW chips need
employee.rtw.read, hierarchy levels are CRUD with their own permissions, and tenants stay apart."""

from __future__ import annotations

import io
import uuid
from typing import Any

from pypdf import PdfReader
from sqlalchemy import text

from tests.db.test_employee_documents import rig as rig

API = "/api/v1"
ROLE = {"employment_type": "full_time", "effective_from": "2025-01-06"}


async def _person(
    rig: dict[str, Any],
    company: uuid.UUID,
    first: str,
    last: str,
    *,
    manager: uuid.UUID | None = None,
    level: str | None = None,
    status: str = "active",
) -> uuid.UUID:
    """A person with one current assignment, written straight to the database (as the owner)."""
    ident = uuid.uuid4()
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into employees (id, company_id, employee_number, first_name, last_name, "
                "email, hire_date, status) values (:i, :c, :n, :f, :l, :e, '2025-01-06', :s)"
            ),
            {
                "i": ident,
                "c": company,
                "n": uuid.uuid4().hex[:12],
                "f": first,
                "l": last,
                "e": f"{ident.hex}@example.com",
                "s": status,
            },
        )
        await c.execute(
            text(
                "insert into employee_assignments (company_id, employee_id, employment_type, "
                "effective_from, reporting_authority_employee_id, organogram_level_id) "
                "values (:c, :i, 'full_time', '2025-01-01', :m, :lv)"
            ),
            {"c": company, "i": ident, "m": manager, "lv": level},
        )
    return ident


async def _point_at(rig: dict[str, Any], person: uuid.UUID, manager: uuid.UUID) -> None:
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "update employee_assignments set reporting_authority_employee_id = :m "
                "where employee_id = :i and ended_at is null"
            ),
            {"m": manager, "i": person},
        )


def _ids(nodes: list[dict[str, Any]]) -> list[str]:
    """Every person in a list of top nodes and everyone below them, depth first."""
    found: list[str] = []
    stack = list(nodes)
    while stack:
        node = stack.pop()
        found.append(node["id"])
        stack.extend(node["reports"])
    return found


def _node(nodes: list[dict[str, Any]], ident: str) -> dict[str, Any]:
    stack = list(nodes)
    while stack:
        node = stack.pop()
        if node["id"] == ident:
            return node
        stack.extend(node["reports"])
    raise AssertionError(f"{ident} is not in the chart")


async def test_the_tree_follows_reporting_lines_and_loose_people_sit_under_unassigned(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    company = rig["a"]
    stamp = uuid.uuid4().hex[:6]
    head = (await admin.post(f"{API}/organogram/levels", json={"name": f"Head {stamp}"})).json()
    boss = await _person(rig, company, "Ada", f"Boss{stamp}", level=head["id"])
    mid_one = await _person(rig, company, "Bea", f"Mid{stamp}", manager=boss)
    mid_two = await _person(rig, company, "Cal", f"Mid2{stamp}", manager=boss)
    dee = await _person(rig, company, "Dee", f"Dee{stamp}", manager=mid_one)
    eli = await _person(rig, company, "Eli", f"Eli{stamp}", manager=mid_one)
    fay = await _person(rig, company, "Fay", f"Fay{stamp}", manager=mid_two)
    loner = await _person(rig, company, "Gus", f"Loner{stamp}")
    leaver = await _person(rig, company, "Hal", f"Hal{stamp}", manager=boss, status="leaver")

    response = await admin.get(f"{API}/organogram")
    assert response.status_code == 200, response.text
    chart = response.json()
    assert chart["rtw_visible"] is True
    top = {node["id"] for node in chart["unassigned"]}
    assert top == {str(boss), str(loner)}
    everyone = _ids(chart["unassigned"])
    assert len(everyone) == len(set(everyone)) == 7  # each person once; the leaver is not charted
    assert str(leaver) not in everyone

    boss_node = _node(chart["unassigned"], str(boss))
    assert boss_node["level"] == f"Head {stamp}"
    assert {node["id"] for node in boss_node["reports"]} == {str(mid_one), str(mid_two)}
    assert {node["id"] for node in _node(chart["unassigned"], str(mid_one))["reports"]} == {
        str(dee),
        str(eli),
    }
    assert [node["id"] for node in _node(chart["unassigned"], str(mid_two))["reports"]] == [
        str(fay)
    ]
    assert _node(chart["unassigned"], str(dee))["reports"] == []


async def test_a_loop_of_managers_neither_hangs_nor_drops_anyone(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    company = rig["a"]
    stamp = uuid.uuid4().hex[:6]
    first = await _person(rig, company, "Ian", f"Loop{stamp}")
    second = await _person(rig, company, "Jo", f"Loop2{stamp}", manager=first)
    await _point_at(rig, first, second)  # first reports to second, second to first
    third = await _person(rig, company, "Kit", f"Under{stamp}", manager=second)

    response = await admin.get(f"{API}/organogram")
    assert response.status_code == 200, response.text
    chart = response.json()
    everyone = _ids(chart["unassigned"])
    assert sorted(everyone) == sorted([str(first), str(second), str(third)])


async def test_rtw_chips_only_for_people_who_may_read_rtw(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    manager = await rig["person"]("people_manager", rig["a"])
    await _person(rig, rig["a"], "Lou", f"Rtw{uuid.uuid4().hex[:6]}")

    seen = (await admin.get(f"{API}/organogram")).json()
    assert seen["rtw_visible"] is True
    assert {node["rtw_status"] for node in seen["unassigned"]} == {"not_recorded"}

    hidden = (await manager.get(f"{API}/organogram")).json()
    assert hidden["rtw_visible"] is False
    assert {node["rtw_status"] for node in hidden["unassigned"]} == {None}


async def test_levels_are_crud_with_their_own_permissions(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    manager = await rig["person"]("people_manager", rig["a"])
    employee = await rig["person"]("employee", rig["a"])
    stamp = uuid.uuid4().hex[:6]
    base = f"{API}/organogram/levels"

    assert (await employee.get(f"{API}/organogram")).status_code == 403
    assert (await employee.get(base)).status_code == 403
    assert (await manager.get(f"{API}/organogram")).status_code == 200
    assert (await manager.post(base, json={"name": f"Lead {stamp}"})).status_code == 403

    made = await admin.post(base, json={"name": f"Lead {stamp}"})
    assert made.status_code == 201, made.text
    level = made.json()
    assert level["rank"] >= 1
    assert (await admin.post(base, json={"name": f"lead {stamp}"})).status_code == 409

    patched = await admin.patch(f"{base}/{level['id']}", json={"rank": 500})
    assert patched.status_code == 200, patched.text
    assert patched.json()["rank"] == 500
    listed = (await manager.get(base)).json()
    assert [row["id"] for row in listed] == [level["id"]]

    await _person(rig, rig["a"], "Mia", f"Used{stamp}", level=level["id"])
    blocked = await admin.delete(f"{base}/{level['id']}")
    assert blocked.status_code == 409, blocked.text

    spare = (await admin.post(base, json={"name": f"Spare {stamp}"})).json()
    assert (await admin.delete(f"{base}/{spare['id']}")).status_code == 204
    assert (await admin.patch(f"{base}/{spare['id']}", json={"rank": 2})).status_code == 404


async def test_a_role_cannot_use_another_companys_level(rig: dict[str, Any]) -> None:
    admin_a = await rig["person"]("company_admin", rig["a"])
    admin_b = await rig["person"]("company_admin", rig["b"])
    stamp = uuid.uuid4().hex[:6]
    foreign = await admin_b.post(f"{API}/organogram/levels", json={"name": f"Foreign {stamp}"})
    own = (await admin_a.post(f"{API}/organogram/levels", json={"name": f"Own {stamp}"})).json()
    person = await _person(rig, rig["a"], "Nia", f"Role{stamp}")

    refused = await admin_a.post(
        f"{API}/employees/{person}/assignments",
        json={**ROLE, "effective_from": "2026-01-06", "organogram_level_id": foreign.json()["id"]},
    )
    assert refused.status_code == 404, refused.text
    accepted = await admin_a.post(
        f"{API}/employees/{person}/assignments",
        json={**ROLE, "effective_from": "2026-01-06", "organogram_level_id": own["id"]},
    )
    assert accepted.status_code == 201, accepted.text


async def test_another_company_sees_no_one_here_and_cannot_touch_the_levels(
    rig: dict[str, Any],
) -> None:
    admin_a = await rig["person"]("company_admin", rig["a"])
    admin_b = await rig["person"]("company_admin", rig["b"])
    stamp = uuid.uuid4().hex[:6]
    level = (await admin_a.post(f"{API}/organogram/levels", json={"name": f"Mine {stamp}"})).json()
    mine = await _person(rig, rig["a"], "Oli", f"Hidden{stamp}", level=level["id"])

    chart = (await admin_b.get(f"{API}/organogram")).json()
    assert str(mine) not in _ids(chart["unassigned"])
    assert all("Hidden" not in node["name"] for node in chart["unassigned"])
    listed = (await admin_b.get(f"{API}/organogram/levels")).json()
    assert level["id"] not in [row["id"] for row in listed]

    base = f"{API}/organogram/levels/{level['id']}"
    assert (await admin_b.patch(base, json={"rank": 9})).status_code == 404
    assert (await admin_b.delete(base)).status_code == 404
    still = (await admin_a.get(f"{API}/organogram/levels")).json()
    assert level["id"] in [row["id"] for row in still]


async def test_the_org_chart_pdf_runs_over_pages_and_names_everyone(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    manager = await rig["person"]("people_manager", rig["a"])
    employee = await rig["person"]("employee", rig["a"])
    stamp = uuid.uuid4().hex[:6]
    boss = await _person(rig, rig["a"], "Top", f"Boss{stamp}")
    for number in range(59):  # 60 people in all
        await _person(rig, rig["a"], "Staff", f"Member{number:02d}x{stamp}", manager=boss)

    response = await admin.get(f"{API}/organogram.pdf")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "no-store" in response.headers["cache-control"]
    reader = PdfReader(io.BytesIO(response.content))
    assert len(reader.pages) >= 2
    text_out = "\n".join(page.extract_text() for page in reader.pages)
    assert f"Member00x{stamp}" in text_out
    assert f"Member58x{stamp}" in text_out
    assert (await manager.get(f"{API}/organogram.pdf")).status_code == 200
    assert (await employee.get(f"{API}/organogram.pdf")).status_code == 403
