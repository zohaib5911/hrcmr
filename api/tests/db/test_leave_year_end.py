"""T8.5 reviewed carry-over, atomic close, scopes and replay/closed-year safety."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.db.test_compliance_hub import rig as rig
from tests.db.test_leave_requests import BASE, payload
from tests.db.test_leave_requests import ready as ready
from tests.db.test_leave_settings import seeded as seeded
from tests.db.test_reminders import _keys as _keys

YEAR = {"from_year": "2026-01-01"}


@pytest.fixture(autouse=True)
def ended(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.modules.leave.year_end_router._today", lambda _: date(2027, 1, 2))


async def preview(ready: dict[str, Any], **extra: Any) -> dict[str, Any]:
    response = await ready["admin"].post(BASE + "/year-end/preview", json={**YEAR, **extra})
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


async def commit(ready: dict[str, Any], reviewed: dict[str, Any], **extra: Any) -> Any:
    return await ready["admin"].post(
        BASE + "/year-end/commit",
        json={**YEAR, "preview_token": reviewed["preview_token"], **extra},
    )


async def test_preview_readonly_commit_carry_expiry_retry_and_closed_year(
    ready: dict[str, Any],
) -> None:
    reviewed = await preview(ready)
    annual = [r for r in reviewed["rows"] if r["leave_type_id"] == ready["annual"]]
    assert len(annual) == 2
    assert {(r["remaining"], r["carry"], r["expire"]) for r in annual} == {
        ("26.00", "5.00", "21.00")
    }
    assert reviewed["blockers"] == []
    async with ready["owner"].connect() as c:
        assert (await c.execute(text("select count(*) from leave_ledger"))).scalar_one() == 0
    response = await commit(ready, reviewed)
    assert response.status_code == 200, response.text
    assert response.json()["committed_run_id"]
    retry = await commit(ready, reviewed)
    assert retry.status_code == 200, retry.text
    assert retry.json() == response.json()
    async with ready["owner"].connect() as c:
        assert (
            await c.execute(
                text("select sum(days) from leave_ledger where leave_year_start='2026-01-01'")
            )
        ).scalar_one() == 0
        assert (
            await c.execute(
                text("select sum(days) from leave_ledger where entry_type='carry_over'")
            )
        ).scalar_one() == 10
        assert (await c.execute(text("select count(*) from leave_year_end_runs"))).scalar_one() == 1
        assert (
            await c.execute(
                text(
                    "select count(*) from audit_events where action='leave.year_end_committed' and company_id=:c"
                ),
                {"c": ready["a"]},
            )
        ).scalar_one() == 1
    closed = await ready["admin"].get(
        f"/api/v1/employees/{ready['employee']}/leave-balances?on=2026-01-05"
    )
    assert (
        next(r for r in closed.json()["items"] if r["leave_type_id"] == ready["annual"])[
            "available"
        ]
        == "0.00"
    )
    blocked = await ready["admin"].post(BASE + "/requests", json=payload(ready))
    assert blocked.status_code == 409, blocked.text
    blocked = await ready["admin"].post(
        f"/api/v1/employees/{ready['employee']}/leave-balances/grant",
        json={
            "leave_type_id": ready["annual"],
            "on": "2026-01-05",
            "days": "1",
            "reason": "Late correction",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert blocked.status_code == 409, blocked.text
    historical = await preview(ready)
    assert historical["committed_run_id"] == response.json()["committed_run_id"]
    with pytest.raises(DBAPIError, match="immutable"):
        async with ready["owner"].begin() as c:
            await c.execute(text("update leave_year_end_runs set to_year='2028-01-01'"))


async def test_stale_preview_reasoned_overrides_and_foreign_inputs(ready: dict[str, Any]) -> None:
    reviewed = await preview(ready)
    body = {
        "leave_type_id": ready["annual"],
        "on": "2026-01-05",
        "days": "1",
        "reason": "Reviewed",
        "idempotency_key": str(uuid.uuid4()),
    }
    changed = await ready["admin"].post(
        f"/api/v1/employees/{ready['employee']}/leave-balances/grant", json=body
    )
    assert changed.status_code == 200, changed.text
    assert (await commit(ready, reviewed)).status_code == 409
    override = {
        "employee_id": str(ready["employee"]),
        "leave_type_id": ready["annual"],
        "days": "8",
        "reason": "Reviewed family leave carry-over",
    }
    reviewed = await preview(ready, overrides=[override])
    row = next(
        r
        for r in reviewed["rows"]
        if r["employee_id"] == str(ready["employee"]) and r["leave_type_id"] == ready["annual"]
    )
    assert row["carry"] == "8"
    assert row["override_reason"] == override["reason"]
    response = await commit(ready, reviewed, overrides=[override])
    assert response.status_code == 200, response.text
    assert (await commit(ready, reviewed, overrides=[])).status_code == 409
    # A different tenant never sees the committed run or the other company's records.
    foreign = await ready["person"]("company_admin", ready["b"])
    response = await foreign.post(
        BASE + "/year-end/preview", json={**YEAR, "overrides": [override]}
    )
    assert response.status_code == 422, response.text
    assert "Amina" not in response.text


async def test_invalid_override_and_pending_or_future_year_blockers(
    ready: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    override = {
        "employee_id": str(ready["employee"]),
        "leave_type_id": ready["annual"],
        "days": "99",
        "reason": "Reviewed",
    }
    for overrides in (
        [override],
        [{**override, "days": "1", "reason": " "}],
        [{**override, "days": "1"}] * 2,
    ):
        response = await ready["admin"].post(
            BASE + "/year-end/preview", json={**YEAR, "overrides": overrides}
        )
        assert response.status_code == 422, response.text
    response = await ready["admin"].post(
        BASE + "/year-end/preview", json={"from_year": "2026-02-01"}
    )
    assert response.status_code == 422
    made = await ready["admin"].post(BASE + "/requests", json=payload(ready))
    assert made.status_code == 201
    reviewed = await preview(ready)
    assert any("pending" in b for b in reviewed["blockers"])
    assert (await commit(ready, reviewed)).status_code == 409
    monkeypatch.setattr("app.modules.leave.year_end_router._today", lambda _: date(2026, 11, 3))
    reviewed = await preview(ready)
    assert any("not ended" in b for b in reviewed["blockers"])


async def test_audit_failure_rolls_back_and_concurrent_commit_retries(
    ready: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewed = await preview(ready)

    async def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Audit unavailable")

    with monkeypatch.context() as m:
        m.setattr("app.modules.rbac.deps.record_audit", broken)
        assert (await commit(ready, reviewed)).status_code == 500
    async with ready["owner"].connect() as c:
        assert (await c.execute(text("select count(*) from leave_year_end_runs"))).scalar_one() == 0
        assert (await c.execute(text("select count(*) from leave_ledger"))).scalar_one() == 0
    responses = await asyncio.gather(commit(ready, reviewed), commit(ready, reviewed))
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json()["committed_run_id"] == responses[1].json()["committed_run_id"]
