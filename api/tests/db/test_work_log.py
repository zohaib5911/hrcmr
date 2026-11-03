"""T9.6 own daily entries, scoped projections, retained corrections and soft removal."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import text

from app.modules.rbac.deps import Access
from app.modules.work_log import service
from tests.db.test_compliance_hub import rig as rig
from tests.db.test_leave_requests import linked
from tests.db.test_leave_requests import ready as ready
from tests.db.test_leave_settings import seeded as seeded
from tests.db.test_reminders import _keys as _keys

API = "/api/v1/work-log"


def body(**changes: Any) -> dict[str, Any]:
    return {
        "date": "2026-01-05",
        "from_time": "09:00",
        "to_time": "17:00",
        "responsibility_text": "Reception",
        "description": "Completed 100% of front desk checks",
        **changes,
    }


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "now", lambda: datetime.fromisoformat("2026-01-05T12:00:00+00:00"))


async def test_own_day_edit_revision_overnight_scope_and_filtered_kpis(
    ready: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    me = await linked(ready, "employee", ready["employee"])
    another = await linked(ready, "employee", ready["other"])
    assert (await ready["admin"].post(API + "/own", json=body())).status_code == 403
    assert (
        await me.post(API + "/own", json=body(employee_id=str(ready["other"])))
    ).status_code == 422
    created = await me.post(API + "/own", json=body())
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["hours"] == "8.00"
    assert row["can_edit"]
    edit = await me.patch(
        API + f"/own/{row['id']}", json=body(to_time="16:00", revision=row["revision"])
    )
    assert edit.status_code == 200, edit.text
    assert edit.json()["hours"] == "7.00"
    assert (
        await me.patch(API + f"/own/{row['id']}", json=body(revision=row["revision"]))
    ).status_code == 409
    assert (
        await another.patch(API + f"/own/{row['id']}", json=body(revision=edit.json()["revision"]))
    ).status_code == 404
    assert (
        await another.post(
            API + "/own",
            json=body(
                date="2026-01-04", from_time="22:00", to_time="06:00", description="Night checks"
            ),
        )
    ).status_code == 201
    admin = ready["admin"]
    listed = await admin.get(API + "?start=2026-01-01&end=2026-01-05&limit=1")
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 2
    assert listed.json()["hours"] == "15.00"
    assert listed.json()["employees"] == 2
    assert listed.json()["next_offset"] == 1
    assert (await me.get(API + "?start=2026-01-01&end=2026-01-05")).json()["total"] == 1
    assert (await admin.get(API + "?start=2026-01-01&end=2026-01-05&search=%25")).json()[
        "total"
    ] == 1
    foreign = await ready["person"]("company_admin", ready["b"])
    assert (await foreign.get(API + "?start=2026-01-01&end=2026-01-05")).json()["items"] == []
    monkeypatch.setattr(service, "now", lambda: datetime.fromisoformat("2026-01-06T00:00:00+00:00"))
    assert (
        await me.patch(API + f"/own/{row['id']}", json=body(revision=edit.json()["revision"]))
    ).status_code == 403


async def test_responsibility_snapshot_survives_profile_deletion_and_foreign_choice(
    ready: dict[str, Any],
) -> None:
    admin = ready["admin"]
    me = await linked(ready, "employee", ready["employee"])
    key = await admin.post(
        f"/api/v1/employees/{ready['employee']}/responsibilities",
        json={"text": "Coordinate handovers", "sort": 0},
    )
    assert key.status_code == 201, key.text
    other = await admin.post(
        f"/api/v1/employees/{ready['other']}/responsibilities",
        json={"text": "Other person's responsibility", "sort": 0},
    )
    assert (
        await me.post(
            API + "/own", json=body(responsibility_id=other.json()["id"], responsibility_text=None)
        )
    ).status_code == 404
    options = await me.get(API + "/own/responsibilities")
    assert options.json() == [{"id": key.json()["id"], "text": "Coordinate handovers"}]
    result = await me.post(
        API + "/own", json=body(responsibility_id=key.json()["id"], responsibility_text=None)
    )
    assert result.status_code == 201, result.text
    assert result.json()["responsibility_text"] == "Coordinate handovers"
    assert (
        await admin.delete(
            f"/api/v1/employees/{ready['employee']}/responsibilities/{key.json()['id']}"
        )
    ).status_code == 204
    current = (await me.get(API + "/own?start=2026-01-05&end=2026-01-05")).json()["items"][0]
    assert current["responsibility_id"] is None
    assert current["responsibility_text"] == "Coordinate handovers"


async def test_reasoned_corrections_retain_original_and_removal_is_soft(
    ready: dict[str, Any],
) -> None:
    me = await linked(ready, "employee", ready["employee"])
    admin = ready["admin"]
    row = (await me.post(API + "/own", json=body(description="Private original detail"))).json()
    path = API + f"/{row['id']}"
    assert (
        await admin.post(path + "/correct", json=body(revision=row["revision"], reason=" "))
    ).status_code == 422
    first = await admin.post(
        path + "/correct",
        json=body(
            to_time="15:00",
            description="Private corrected detail",
            revision=row["revision"],
            reason="Reviewed with employee",
        ),
    )
    assert first.status_code == 200, first.text
    assert first.json()["corrected_from"]["description"] == "Private original detail"
    second = await admin.post(
        path + "/correct",
        json=body(to_time="14:00", revision=first.json()["revision"], reason="Second review"),
    )
    assert second.status_code == 200, second.text
    assert second.json()["corrected_from"] == first.json()["corrected_from"]
    hr = await ready["person"]("hr_admin", ready["a"])
    assert (
        await hr.post(
            path + "/remove", json={"revision": second.json()["revision"], "reason": "Duplicate"}
        )
    ).status_code == 403
    foreign = await ready["person"]("company_admin", ready["b"])
    assert (
        await foreign.post(
            path + "/remove", json={"revision": second.json()["revision"], "reason": "Duplicate"}
        )
    ).status_code == 404
    removed = await admin.post(
        path + "/remove", json={"revision": second.json()["revision"], "reason": "Duplicate"}
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["removed_at"] is not None
    assert not removed.json()["can_edit"]
    assert (await me.get(API + "/own?start=2026-01-05&end=2026-01-05")).json()["items"] == []
    assert (await admin.get(API + "?start=2026-01-05&end=2026-01-05&show_removed=true")).json()[
        "total"
    ] == 1
    async with ready["owner"].connect() as c:
        events = (
            await c.execute(
                text(
                    "select before,after,reason from audit_events where company_id=:c and action like 'work_log.%'"
                ),
                {"c": ready["a"]},
            )
        ).all()
    assert len(events) == 4
    assert "Private original detail" not in json.dumps([list(e) for e in events])
    assert "Private corrected detail" not in json.dumps([list(e) for e in events])


@pytest.mark.parametrize(
    "changes",
    [
        {"date": "2026-01-06"},
        {"date": "2024-12-31"},
        {"from_time": "17:00"},
        {"from_time": "09:00:01"},
        {"description": "  "},
        {"responsibility_text": None},
    ],
)
async def test_invalid_entry_rejected(ready: dict[str, Any], changes: dict[str, Any]) -> None:
    me = await linked(ready, "employee", ready["employee"])
    assert (await me.post(API + "/own", json=body(**changes))).status_code == 422


async def test_archived_filter_and_audit_failure_rollback(
    ready: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    me = await linked(ready, "employee", ready["employee"])
    admin = ready["admin"]
    row = (await me.post(API + "/own", json=body())).json()
    async with ready["owner"].begin() as c:
        await c.execute(
            text("update employees set status='archived' where id=:e"), {"e": ready["employee"]}
        )
    assert (await admin.get(API + "?start=2026-01-05&end=2026-01-05")).json()["total"] == 0
    assert (await admin.get(API + "?start=2026-01-05&end=2026-01-05&show_archived=true")).json()[
        "total"
    ] == 1
    assert (await me.post(API + "/own", json=body())).status_code == 403

    async def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("audit failed")

    monkeypatch.setattr(Access, "audit", fail)
    assert (
        await admin.post(
            API + f"/{row['id']}/correct",
            json=body(
                description="Uncommitted correction", revision=row["revision"], reason="Review"
            ),
        )
    ).status_code == 500
    async with ready["owner"].connect() as c:
        current = (
            await c.execute(
                text("select description,corrected_from from work_log_entries where id=:id"),
                {"id": row["id"]},
            )
        ).one()
    assert current.description == body()["description"]
    assert current.corrected_from is None
