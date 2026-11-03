"""Cross-company exports must be indistinguishable from missing records."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import text

from tests.db.test_sponsor_documents import _employee
from tests.db.test_sponsor_documents import _keys as _keys
from tests.db.test_sponsor_documents import rig as rig

API = "/api/v1"


@pytest.mark.parametrize("role", ["company_admin", "hr_admin"])
async def test_foreign_employee_exports_are_404_without_rendering_or_audit(
    rig: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    from app.modules.compliance import sponsor_pdf
    from app.modules.employees import record_pdf

    def unexpected_render(html: str) -> bytes:
        pytest.fail("A foreign or missing employee must never reach PDF rendering")

    monkeypatch.setattr(record_pdf, "render_pdf", unexpected_render)
    monkeypatch.setattr(sponsor_pdf, "render_pdf", unexpected_render)
    foreign = await _employee(rig, rig["b"], "PRIVATE-FOREIGN")
    client = await rig["person"](role, rig["a"])
    for suffix in ("record.pdf", "sponsor-record.pdf"):
        responses = []
        for ident in (foreign, uuid.uuid4()):
            response = await client.get(f"{API}/employees/{ident}/{suffix}")
            assert response.status_code == 404
            assert response.headers["content-type"] == "application/json"
            body = response.json()
            body["error"].pop("request_id")
            responses.append(body)
            assert "PRIVATE-FOREIGN" not in response.text
        assert responses[0] == responses[1]
    async with rig["owner"].connect() as connection:
        assert (
            await connection.execute(
                text(
                    "select count(*) from audit_events where company_id in (:a,:b) "
                    "and action in ('employee.record_exported','employee.sponsor_record_exported')"
                ),
                {"a": rig["a"], "b": rig["b"]},
            )
        ).scalar_one() == 0


async def test_dossier_is_shared_guidance_and_checklist_audit_stays_in_callers_company(
    rig: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.compliance import dossier_router

    await _employee(rig, rig["b"], "PRIVATE-FOREIGN")
    a = await rig["person"]("company_admin", rig["a"])
    b = await rig["person"]("company_admin", rig["b"])
    guidance = await a.get(API + "/compliance/dossier")
    assert guidance.status_code == 200
    assert guidance.json() == (await b.get(API + "/compliance/dossier")).json()
    spoofed = await a.get(API + "/compliance/dossier", params={"company_id": str(rig["b"])})
    assert spoofed.json() == guidance.json()
    assert "PRIVATE-FOREIGN" not in guidance.text
    # This PDF is a global original checklist, with a tenant-scoped download audit.
    rendered: list[str] = []

    def render(html: str) -> bytes:
        rendered.append(html)
        return b"%PDF-checklist"

    monkeypatch.setattr(dossier_router, "render_pdf", render)
    result = await a.get(
        API + "/compliance/rtw-checklist.pdf", params={"company_id": str(rig["b"])}
    )
    assert result.status_code == 200
    assert "PRIVATE-FOREIGN" not in rendered[0]
    async with rig["owner"].connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        "select company_id from audit_events where company_id in (:a,:b) "
                        "and action='compliance.checklist_downloaded'"
                    ),
                    {"a": rig["a"], "b": rig["b"]},
                )
            )
            .scalars()
            .all()
        )
    assert rows == [rig["a"]]
