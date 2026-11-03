"""T9.4 settings CRUD, prerequisite scope, overnight validation and atomic audit."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from sqlalchemy import text

from app.modules.rbac.deps import Access
from tests.db.test_compliance_hub import rig as rig
from tests.db.test_reminders import _keys as _keys

API = "/api/v1/rota"
SHIFT = {
    "name": "Night",
    "starts_at": "22:00",
    "ends_at": "06:00",
    "break_start": "02:00",
    "break_end": "02:30",
}


@pytest.fixture
async def settings(rig: dict[str, Any]) -> dict[str, Any]:
    admin = await rig["person"]("company_admin", rig["a"])
    department = await admin.post("/api/v1/departments", json={"name": "Care"})
    assert department.status_code == 201, department.text
    dept = department.json()["id"]
    designation = await admin.post(
        "/api/v1/designations", json={"title": "Carer", "department_id": dept}
    )
    assert designation.status_code == 201, designation.text
    shift = await admin.post(API + "/shift-types", json=SHIFT)
    assert shift.status_code == 201, shift.text
    scope = {
        "department_id": dept,
        "designation_id": designation.json()["id"],
        "shift_type_id": shift.json()["id"],
    }
    return {**rig, "admin": admin, "scope": scope, "shift": shift.json()}


async def test_shift_crud_unique_races_and_role_tenant_boundaries(settings: dict[str, Any]) -> None:
    admin = settings["admin"]
    first, second = await asyncio.gather(
        *[
            admin.post(
                API + "/shift-types",
                json={
                    **SHIFT,
                    "name": "Morning",
                    "starts_at": "06:00",
                    "ends_at": "14:00",
                    "break_start": None,
                    "break_end": None,
                },
            )
            for _ in range(2)
        ]
    )
    assert sorted([first.status_code, second.status_code]) == [201, 409]
    assert (
        await admin.post(API + "/shift-types", json={**SHIFT, "name": "nIgHt"})
    ).status_code == 409
    path = API + f"/shift-types/{settings['shift']['id']}"
    foreign = await settings["person"]("company_admin", settings["b"])
    assert (await foreign.get(API + "/shift-types")).json() == []
    assert (await foreign.put(path, json=SHIFT)).status_code == 404
    assert (await foreign.delete(path)).status_code == 404
    manager = await settings["person"]("people_manager", settings["a"])
    assert (await manager.get(API + "/shift-types")).status_code == 200
    assert (await manager.put(path, json=SHIFT)).status_code == 403
    employee = await settings["person"]("employee", settings["a"])
    assert (await employee.get(API + "/shift-types")).status_code == 403
    changed = await admin.put(path, json={**SHIFT, "name": "Night cover"})
    assert changed.status_code == 200, changed.text
    assert (await admin.delete(path)).status_code == 204
    assert (await admin.put(path, json=SHIFT)).status_code == 404
    assert (await admin.post(API + "/shift-types", json=SHIFT)).status_code == 201


async def test_policies_patterns_prerequisites_uniqueness_archives_and_audit(
    settings: dict[str, Any],
) -> None:
    admin, scope = settings["admin"], settings["scope"]
    policy = {
        **scope,
        "grace_minutes": 5,
        "allowed_late_days_per_month": 2,
        "deduction_type": "none",
        "deduction_value": "0",
    }
    created = await admin.post(API + "/late-policies", json=policy)
    assert created.status_code == 201, created.text
    assert (await admin.post(API + "/late-policies", json=policy)).status_code == 409
    pattern = {**scope, "weekdays_off": [7, 6], "works_public_holidays": False}
    off = await admin.post(API + "/day-off-patterns", json=pattern)
    assert off.status_code == 201, off.text
    assert off.json()["weekdays_off"] == [6, 7]
    assert (await admin.delete(API + f"/shift-types/{scope['shift_type_id']}")).status_code == 409
    other_department = (await admin.post("/api/v1/departments", json={"name": "Office"})).json()[
        "id"
    ]
    assert (
        await admin.put(
            API + f"/late-policies/{created.json()['id']}",
            json={**policy, "department_id": other_department},
        )
    ).status_code == 404
    foreign = await settings["person"]("company_admin", settings["b"])
    assert (await foreign.post(API + "/late-policies", json=policy)).status_code == 404
    for endpoint, row, body in [
        (
            "late-policies",
            created.json(),
            {**policy, "deduction_type": "percentage_of_day", "deduction_value": "10"},
        ),
        (
            "day-off-patterns",
            off.json(),
            {**pattern, "weekdays_off": [7], "works_public_holidays": True},
        ),
    ]:
        path = API + f"/{endpoint}/{row['id']}"
        assert (await admin.put(path, json=body)).status_code == 200
        assert len((await admin.get(API + f"/{endpoint}")).json()) == 1
        assert (await foreign.put(path, json=body)).status_code == 404
        assert (await foreign.delete(path)).status_code == 404
        assert (await admin.delete(path)).status_code == 204
        assert (await admin.get(API + f"/{endpoint}")).json() == []
    assert (await admin.delete(API + f"/shift-types/{scope['shift_type_id']}")).status_code == 204
    async with settings["owner"].connect() as c:
        actions = set(
            (
                await c.execute(text("select action from audit_events where action like 'rota.%'"))
            ).scalars()
        )
    assert {
        "rota.shift_type_created",
        "rota.shift_type_archived",
        "rota.late_policy_updated",
        "rota.day_off_pattern_updated",
        "rota.late_policy_archived",
        "rota.day_off_pattern_archived",
    } <= actions


@pytest.mark.parametrize(
    "changes",
    [
        {"starts_at": "06:00", "ends_at": "06:00"},
        {"break_start": "21:30", "break_end": "22:30"},
        {"break_start": "05:30", "break_end": "06:30"},
        {"break_start": "02:00", "break_end": None},
        {"starts_at": "22:00:01"},
        {"starts_at": "22:00+01:00"},
        {"name": "  "},
        {"colour": "red; color:blue"},
    ],
)
async def test_invalid_shift_does_not_write(rig: dict[str, Any], changes: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    assert (await admin.post(API + "/shift-types", json={**SHIFT, **changes})).status_code == 422
    assert (await admin.get(API + "/shift-types")).json() == []


async def test_invalid_config_and_audit_failure_rollback(
    settings: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin, scope = settings["admin"], settings["scope"]
    invalid: list[dict[str, Any]] = [
        {"deduction_type": "none", "deduction_value": "1"},
        {"deduction_type": "percentage_of_day", "deduction_value": "101"},
        {"grace_minutes": -1},
        {"allowed_late_days_per_month": 32},
    ]
    for changes in invalid:
        response = await admin.post(
            API + "/late-policies",
            json={
                **scope,
                "grace_minutes": 0,
                "allowed_late_days_per_month": 0,
                "deduction_type": "none",
                "deduction_value": "0",
                **changes,
            },
        )
        assert response.status_code == 422
    assert (
        await admin.post(API + "/day-off-patterns", json={**scope, "weekdays_off": [1, 1]})
    ).status_code == 422
    assert (
        await admin.post(API + "/day-off-patterns", json={**scope, "weekdays_off": [0]})
    ).status_code == 422

    async def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("audit failed")

    monkeypatch.setattr(Access, "audit", fail)
    assert (
        await admin.post(API + "/day-off-patterns", json={**scope, "weekdays_off": []})
    ).status_code == 500
    assert (await admin.get(API + "/day-off-patterns")).json() == []
