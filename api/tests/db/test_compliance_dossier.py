"""Official link seeds, mandatory platform MFA, global audit isolation and original PDF."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pypdf import PdfReader
from sqlalchemy import insert, text
from sqlalchemy.exc import DBAPIError

from app.db.session import GlobalSession
from app.modules.compliance.dossier_models import DossierLink
from tests.db.test_compliance_hub import rig as rig

API = "/api/v1"


async def test_official_dossier_checklist_and_platform_edits_require_mfa(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    response = await admin.get(API + "/compliance/dossier")
    assert response.status_code == 200, response.text
    links = response.json()["links"]
    assert len(links) == 8
    assert {link["section"] for link in links} == {"licence", "rtw", "sms"}
    assert all(link["url"].startswith("https://www.gov.uk/") for link in links)
    assert all(link["checked_on"] == "2026-11-03" for link in links)
    pdf = await admin.get(API + response.json()["checklist_url"])
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF-")
    content = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Original working checklist" in content
    assert "Before work starts" in content
    assert "Follow up" in content
    assert "https://www.gov.uk/" in content
    assert "no-store" in pdf.headers["cache-control"]
    payload = {key: value for key, value in links[0].items() if key != "id"}
    for role in ("company_admin", "hr_admin", "read_only_auditor", "employee"):
        client = await rig["person"](role, rig["a"])
        assert (await client.get(API + "/admin/dossier-links")).status_code == 403
        assert (
            await client.put(API + "/admin/dossier-links/" + links[0]["id"], json=payload)
        ).status_code == 403
    platform_id = next(
        u["user_id"] for u in (await admin.get(API + "/users")).json()["users"] if u["is_you"]
    )
    async with rig["owner"].begin() as c:
        await c.execute(
            text("insert into platform_admins (user_id,level) values (:u,'support')"),
            {"u": platform_id},
        )
    # The platform session (T17.1) is what refuses an admin with no authenticator set up.
    enrol = await admin.post(API + "/auth/platform-session")
    assert enrol.status_code == 403
    assert enrol.json()["error"]["code"] == "MFA_ENROLMENT_REQUIRED"
    # Without a platform session the signed-in tenant session is refused on the admin page.
    assert (await admin.get(API + "/admin/dossier-links")).status_code == 403
    async with rig["owner"].begin() as c:
        await c.execute(text("update users set mfa_enabled=true where id=:u"), {"u": platform_id})
    # This fixture's signed session already passed MFA; setting the enrolled flag makes the
    # otherwise unchanged session satisfy the mandatory platform policy.
    started = await admin.post(API + "/auth/platform-session")
    assert started.status_code == 201, started.text
    assert (await admin.get(API + "/admin/dossier-links")).status_code == 200
    for url in (
        "javascript:alert(1)",
        "https://www.gov.uk.evil.test/path",
        "https://www.gov.uk@evil.test/path",
        "http://www.gov.uk/path",
        "https://www.gov.uk:443/path",
    ):
        invalid = await admin.put(
            API + "/admin/dossier-links/" + links[0]["id"], json={**payload, "url": url}
        )
        assert invalid.status_code == 422
    future = await admin.put(
        API + "/admin/dossier-links/" + links[0]["id"],
        json={**payload, "checked_on": str(datetime.now(UTC).date() + timedelta(days=1))},
    )
    assert future.status_code == 422
    hidden = await admin.put(
        API + "/admin/dossier-links/" + links[0]["id"],
        json={**payload, "title": "Licence application guidance", "active": False},
    )
    assert hidden.status_code == 200, hidden.text
    other = await rig["person"]("hr_admin", rig["b"])
    assert len((await other.get(API + "/compliance/dossier")).json()["links"]) == 7
    added = await admin.post(
        API + "/admin/dossier-links", json={**payload, "title": "More official guidance"}
    )
    assert added.status_code == 201, added.text
    assert len((await other.get(API + "/compliance/dossier")).json()["links"]) == 8
    assert (
        await admin.put(API + "/admin/dossier-links/" + str(uuid.uuid4()), json=payload)
    ).status_code == 404
    async with rig["owner"].connect() as c:
        records = (
            await c.execute(
                text(
                    "select company_id, actor_type, actor_user_id from audit_events where action like 'platform.dossier_link_%'"
                )
            )
        ).all()
        assert len(records) == 2
        assert all(
            row[0] is None and row[1] == "platform_admin" and str(row[2]) == platform_id
            for row in records
        )
    assert "platform.dossier_link_" not in (await other.get(API + "/compliance/activity")).text
    own = await rig["person"]("employee", rig["a"])
    assert (await own.get(API + "/compliance/dossier")).status_code == 403
    assert (await own.get(API + "/compliance/rtw-checklist.pdf")).status_code == 403
    # Even a missing application-level permission check cannot make a tenant write global links.
    async with GlobalSession(rig["app"].state.engine) as db:
        with pytest.raises(DBAPIError):
            await db.execute(insert(DossierLink).values(**payload))
        await db.rollback()
