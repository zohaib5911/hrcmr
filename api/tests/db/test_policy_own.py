"""T10.3: owned acceptance/signing, encrypted immutable receipts and authorized file viewing."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import text

from app.modules.rbac.deps import Access
from tests.db.test_employee_documents import _employee
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig
from tests.db.test_policies import document, send

API = "/api/v1/policies"


async def linked(rig: dict[str, Any], employee: uuid.UUID) -> httpx.AsyncClient:
    client: httpx.AsyncClient = await rig["person"]("employee", rig["a"])
    async with rig["owner"].begin() as db:
        await db.execute(
            text(
                "update memberships set employee_id=:e where id=(select id from memberships where company_id=:c and role='employee' and employee_id is null order by id desc limit 1)"
            ),
            {"e": employee, "c": rig["a"]},
        )
    return client


async def setup(
    rig: dict[str, Any], *, sign: bool = False
) -> tuple[httpx.AsyncClient, httpx.AsyncClient, dict[str, Any], uuid.UUID]:
    admin = await rig["person"]("company_admin", rig["a"])
    employee = await _employee(rig, rig["a"], "OWN-POL")
    member = await linked(rig, employee)
    row = await document(
        admin,
        audience_type="named",
        audience_ids=[str(employee)],
        confirmation_mode="sign" if sign else "accept",
    )
    sent = await send(admin, row)
    assert sent.status_code == 200, sent.text
    return admin, member, row, employee


async def test_own_acceptance_receipt_viewer_and_historical_archive(rig: dict[str, Any]) -> None:
    admin, member, row, employee = await setup(rig)
    own = (await member.get(API + "/own")).json()
    assert own["total"] == 1
    assert own["items"][0]["id"] == row["id"]
    assert (await member.get(API + "/own/summary")).json() == {
        "pending": 1,
        "overdue": 0,
        "completed": 0,
    }
    view = await member.get(API + f"/own/{row['id']}/view")
    assert view.status_code == 200, view.text
    assert view.headers["content-type"] == "application/pdf"
    assert view.content.startswith(b"%PDF-")  # streamed in pieces, and whole (C6.1.11)
    assert int(view.headers["content-length"]) == len(view.content)
    assert view.headers["content-disposition"].startswith("inline;")
    assert view.headers["cache-control"] == "private, no-store"
    assert view.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors" in view.headers["content-security-policy"]
    assert (await member.get(API + f"/own/{row['id']}/download")).json()["expires_in"] == 60
    assert (await member.get(API + f"/{row['id']}/receipt")).status_code == 404
    assert (
        await member.post(API + f"/{row['id']}/accept", json={"confirmed": False})
    ).status_code == 422
    assert (
        await member.post(
            API + f"/{row['id']}/accept", json={"confirmed": True, "typed_signature": "Wrong mode"}
        )
    ).status_code == 422
    assert (
        await member.post(API + f"/{row['id']}/accept", json={"confirmed": True, "ip": "192.0.2.1"})
    ).status_code == 422
    accepted = await member.post(
        API + f"/{row['id']}/accept",
        json={"confirmed": True},
        headers={"User-Agent": "Policy API receipt test"},
    )
    assert accepted.status_code == 200, accepted.text
    receipt = accepted.json()
    assert receipt["employee_id"] == str(employee)
    assert receipt["version"] == 1
    assert receipt["typed_signature"] is None
    assert receipt["ip"]
    assert receipt["user_agent"] == "Policy API receipt test"
    assert (
        await member.post(API + f"/{row['id']}/accept", json={"confirmed": True})
    ).json() == receipt
    assert (await member.get(API + f"/{row['id']}/receipt")).json() == receipt
    assert (await member.get(API + "/own/summary")).json() == {
        "pending": 0,
        "overdue": 0,
        "completed": 1,
    }
    assert (
        await admin.get(API + f"/{row['id']}/acceptances/{receipt['id']}/receipt")
    ).json() == receipt
    assert (await admin.delete(API + f"/{row['id']}")).status_code == 204
    assert (await member.get(API + "/own")).json()["items"][0]["archived"]
    assert (await member.get(API + f"/own/{row['id']}/view")).status_code == 200
    assert (await member.get(f"/api/v1/files/{row['file_id']}/download")).status_code == 200
    async with rig["owner"].connect() as db:
        assert (
            await db.execute(
                text(
                    "select count(*) from audit_events where company_id=:c and action='policy.accepted'"
                ),
                {"c": rig["a"]},
            )
        ).scalar_one() == 1


async def test_signing_keeps_original_encrypted_name_and_rejects_replacement(
    rig: dict[str, Any],
) -> None:
    _, member, row, _ = await setup(rig, sign=True)
    assert (
        await member.post(API + f"/{row['id']}/accept", json={"confirmed": True})
    ).status_code == 422
    for name in ("", "   "):
        assert (
            await member.post(
                API + f"/{row['id']}/accept", json={"confirmed": True, "typed_signature": name}
            )
        ).status_code == 422
    body = {"confirmed": True, "typed_signature": "Amira Hassan"}
    signed = await member.post(API + f"/{row['id']}/accept", json=body)
    assert signed.status_code == 200, signed.text
    receipt = signed.json()
    assert receipt["typed_signature"] == "Amira Hassan"
    assert (await member.post(API + f"/{row['id']}/accept", json=body)).json() == receipt
    changed = await member.post(
        API + f"/{row['id']}/accept", json={**body, "typed_signature": "Different name"}
    )
    assert changed.status_code == 409
    async with rig["owner"].connect() as db:
        stored = (
            await db.execute(
                text("select typed_signature from policy_acceptances where id=:i"),
                {"i": receipt["id"]},
            )
        ).scalar_one()
        assert stored != "Amira Hassan"
        events = (
            (
                await db.execute(
                    text(
                        "select after from audit_events where company_id=:c and action='policy.signed'"
                    ),
                    {"c": rig["a"]},
                )
            )
            .scalars()
            .all()
        )
    assert len(events) == 1
    assert "Amira Hassan" not in json.dumps(events)


async def test_unassigned_foreign_relinked_and_pending_archived_documents_are_unreachable(
    rig: dict[str, Any],
) -> None:
    admin, member, row, _ = await setup(rig)
    another = await _employee(rig, rig["a"], "OTHER-OWN")
    other = await linked(rig, another)
    assert (await other.get(API + "/own")).json()["items"] == []
    for suffix in (f"/own/{row['id']}/view", f"/own/{row['id']}/download", f"/{row['id']}/receipt"):
        assert (await other.get(API + suffix)).status_code == 404
    assert (
        await other.post(API + f"/{row['id']}/accept", json={"confirmed": True})
    ).status_code == 404
    foreign = await rig["person"]("employee", rig["b"])
    assert (await foreign.get(API + f"/own/{row['id']}/view")).status_code == 404
    assert (await member.get(API + f"/{row['id']}")).status_code == 403
    assert (await admin.delete(API + f"/{row['id']}")).status_code == 204
    assert (await member.get(API + "/own")).json()["items"] == []
    assert (await member.get(API + f"/own/{row['id']}/view")).status_code == 404
    assert (
        await member.post(API + f"/{row['id']}/accept", json={"confirmed": True})
    ).status_code == 409
    assert (await member.get(f"/api/v1/files/{row['file_id']}/download")).status_code == 404


async def test_confirmation_requires_available_scan_and_audit_is_atomic(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, member, row, _ = await setup(rig, sign=True)
    async with rig["owner"].begin() as db:
        await db.execute(
            text("update files set scan_status='pending' where id=:i"), {"i": row["file_id"]}
        )
    assert (await member.get(API + f"/own/{row['id']}/view")).status_code == 404
    body = {"confirmed": True, "typed_signature": "Amira Hassan"}
    assert (await member.post(API + f"/{row['id']}/accept", json=body)).status_code == 404
    async with rig["owner"].begin() as db:
        await db.execute(
            text("update files set scan_status='clean' where id=:i"), {"i": row["file_id"]}
        )
    original = Access.audit

    async def fail(self: Access, action: str, **kwargs: Any) -> None:
        if action == "policy.signed":
            await self.db.flush()
            raise RuntimeError("audit unavailable")
        await original(self, action, **kwargs)

    monkeypatch.setattr(Access, "audit", fail)
    assert (await member.post(API + f"/{row['id']}/accept", json=body)).status_code == 500
    assert (await member.get(API + "/own/summary")).json()["pending"] == 1
    async with rig["owner"].connect() as db:
        receipt = (
            await db.execute(
                text(
                    "select accepted_at, typed_signature from policy_acceptances where policy_document_id=:i"
                ),
                {"i": row["id"]},
            )
        ).one()
    assert receipt.accepted_at is None
    assert receipt.typed_signature is None
