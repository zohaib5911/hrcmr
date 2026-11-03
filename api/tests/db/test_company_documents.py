"""T10.1: scanned company files, review boundaries, scoped CRUD and retained audit history."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text

from app.integrations.clamav import ScanResult
from app.modules.rbac.deps import Access
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig
from tests.db.test_files import PDF

API = "/api/v1/documents"


async def upload(client: httpx.AsyncClient, **changes: str) -> httpx.Response:
    return await client.post(
        API,
        files={"file": ("handbook.pdf", PDF, "application/pdf")},
        data={"title": "Staff handbook", "category": "policy_handbook", **changes},
    )


async def test_scanned_crud_review_filters_archived_download_and_audit(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    today = date.fromisoformat((await admin.get(API)).json()["today"])
    made = await upload(
        admin, title="  Handbook 100%  ", next_review_date=str(today + timedelta(days=30))
    )
    assert made.status_code == 201, made.text
    row = made.json()
    assert row["title"] == "Handbook 100%"
    assert row["review_status"] == "review_due"
    assert row["scan_status"] == "clean"
    assert (await admin.get(API, params={"search": "%", "category": "insurance"})).json()[
        "total"
    ] == 0
    assert (await admin.get(API, params={"search": "%", "review_due": True})).json()["total"] == 1
    assert (await admin.get(API + f"/{row['id']}")).json()["file_name"] == "handbook.pdf"
    link = await admin.get(API + f"/{row['id']}/download")
    assert link.status_code == 200, link.text
    assert link.json()["expires_in"] == 60
    assert "X-Amz-Expires=60" in link.json()["url"]
    edited = await admin.patch(
        API + f"/{row['id']}",
        json={"title": "Reviewed handbook", "category": "training", "next_review_date": None},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["review_status"] == "no_review_date"
    assert (await admin.get(API, params={"review_due": True})).json()["total"] == 0
    assert (await admin.delete(API + f"/{row['id']}")).status_code == 204
    assert (await admin.delete(API + f"/{row['id']}")).status_code == 204
    assert (await admin.get(API)).json()["items"] == []
    archived = (await admin.get(API, params={"show_archived": True})).json()
    assert archived["total"] == 1
    assert archived["items"][0]["archived_at"]
    assert (await admin.get(API + f"/{row['id']}/download")).status_code == 200
    assert (
        await admin.patch(API + f"/{row['id']}", json={"title": "No", "category": "other"})
    ).status_code == 409
    async with rig["owner"].connect() as c:
        actions = list(
            (
                await c.execute(
                    text("select action from audit_events where company_id=:c"), {"c": rig["a"]}
                )
            ).scalars()
        )
        assert actions.count("company_document.archived") == 1
        assert {
            "company_document.added",
            "company_document.updated",
            "file.uploaded",
            "file.downloaded",
        } <= set(actions)


async def test_review_day_boundaries_and_pagination(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("hr_admin", rig["a"])
    today = date.fromisoformat((await admin.get(API)).json()["today"])
    for days, expected in [(-1, "overdue"), (0, "review_due"), (30, "review_due"), (31, "current")]:
        result = await upload(admin, next_review_date=str(today + timedelta(days=days)))
        assert result.status_code == 201, result.text
        assert result.json()["review_status"] == expected
    assert (await admin.get(API, params={"review_due": True})).json()["total"] == 3
    first = (await admin.get(API, params={"limit": 2})).json()
    second = (await admin.get(API, params={"limit": 2, "offset": 2})).json()
    assert first["total"] == second["total"] == 4
    assert not {r["id"] for r in first["items"]} & {r["id"] for r in second["items"]}


async def test_full_scope_permissions_and_tenant_isolation(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    made = (await upload(hr)).json()
    foreign = await rig["person"]("company_admin", rig["b"])
    assert (await foreign.get(API)).json()["items"] == []
    for suffix in ("", "/download"):
        assert (await foreign.get(API + f"/{made['id']}" + suffix)).status_code == 404
    assert (
        await foreign.patch(API + f"/{made['id']}", json={"title": "Other", "category": "other"})
    ).status_code == 404
    assert (await foreign.delete(API + f"/{made['id']}")).status_code == 404
    for role in ("employee", "people_manager", "recruiter", "read_only_auditor"):
        client = await rig["person"](role, rig["a"])
        assert (await client.get(API)).status_code == 403
        assert (await client.get(API + f"/{made['id']}/download")).status_code == 403
        assert (await upload(client)).status_code == 403
        assert (
            await client.patch(API + f"/{made['id']}", json={"title": "Other", "category": "other"})
        ).status_code == 403
        assert (await client.delete(API + f"/{made['id']}")).status_code == 403
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "update memberships set role='employee' where user_id=(select uploaded_by from files where id=:f) and company_id=:c"
            ),
            {"f": made["file_id"], "c": rig["a"]},
        )
    assert (await hr.get(f"/api/v1/files/{made['file_id']}")).status_code == 404
    assert (await hr.get(f"/api/v1/files/{made['file_id']}/download")).status_code == 404


async def test_invalid_metadata_scan_gating_and_file_types(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    for changes in ({"title": " "}, {"category": "invalid"}, {"next_review_date": "2026-02-30"}):
        assert (await upload(admin, **changes)).status_code == 422
    for name, payload, expected in [
        ("bad.pdf", b"MZ-invalid", 415),
        ("sheet.csv", b"a,b\n1,2\n", 415),
        ("mismatch.doc", b"not a Word file", 415),
    ]:
        refused = await admin.post(
            API, files={"file": (name, payload)}, data={"title": "Example", "category": "other"}
        )
        assert refused.status_code == expected, refused.text
    for verdict, expected in [(ScanResult("infected", "test"), 422), (ScanResult("error"), 503)]:

        async def blocked(*args: Any, result: ScanResult = verdict, **kwargs: Any) -> ScanResult:
            return result

        with monkeypatch.context() as patch:
            patch.setattr(rig["app"].state.files.scanner, "scan", blocked)
            assert (await upload(admin)).status_code == expected
    row = (await upload(admin)).json()
    assert (
        await admin.patch(API + f"/{row['id']}", json={"title": " ", "category": "other"})
    ).status_code == 422
    assert (
        await admin.patch(
            API + f"/{row['id']}", json={"title": "Valid", "category": "other", "unexpected": True}
        )
    ).status_code == 422
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update files set scan_status='pending' where id=:f"), {"f": row["file_id"]}
        )
    assert (await admin.get(API + f"/{row['id']}/download")).status_code == 404
    assert (await admin.get(f"/api/v1/files/{row['file_id']}/download")).status_code == 404
    assert (await admin.get(API)).json()["items"][0]["scan_status"] == "pending"


async def test_upload_edit_archive_roll_back_when_audit_fails(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    original = Access.audit

    async def fail(self: Access, action: str, **kwargs: Any) -> None:
        if action.startswith("company_document."):
            raise RuntimeError("audit failed")
        await original(self, action, **kwargs)

    row = (await upload(admin)).json()
    monkeypatch.setattr(Access, "audit", fail)
    assert (await upload(admin)).status_code == 500
    assert (
        await admin.patch(API + f"/{row['id']}", json={"title": "Changed", "category": "other"})
    ).status_code == 500
    assert (await admin.delete(API + f"/{row['id']}")).status_code == 500
    rows = (await admin.get(API)).json()["items"]
    assert len(rows) == 1
    assert rows[0]["title"] == row["title"]
    async with rig["owner"].connect() as c:
        assert (
            await c.execute(text("select count(*) from files where company_id=:c"), {"c": rig["a"]})
        ).scalar_one() == 1
