"""T10.3 schema: immutable sent versions and completed receipts, retained assignment identity."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db.ids import uuid7
from app.db.session import TenantSession
from app.modules.files.models import File
from app.modules.identity.models import Membership
from app.modules.policies.models import PolicyAcceptance, PolicyDocument
from tests.db.test_employee_documents import _employee
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig


@pytest.fixture
async def policy(rig: dict[str, Any]) -> dict[str, Any]:
    await rig["person"]("company_admin", rig["a"])
    employee = await _employee(rig, rig["a"], "POL-001")
    async with TenantSession(rig["app"].state.engine, company_id=rig["a"]) as db:
        actor = (
            await db.execute(select(Membership.user_id).where(Membership.role == "company_admin"))
        ).scalar_one()
        file = File(
            company_id=rig["a"],
            storage_key=f"policy-test/{uuid.uuid4()}",
            original_name="policy.pdf",
            mime="application/pdf",
            size=1,
            sha256="0" * 64,
            scan_status="clean",
        )
        db.add(file)
        await db.flush()
        ident = uuid7()
        document = PolicyDocument(
            id=ident,
            group_id=ident,
            company_id=rig["a"],
            title="Policy evidence",
            category="company_policy",
            file_id=file.id,
        )
        db.add(document)
        await db.commit()
        document.status, document.sent_at, document.sent_by = "sent", datetime.now(UTC), actor
        await db.commit()
        acceptance = PolicyAcceptance(
            company_id=rig["a"],
            policy_document_id=document.id,
            employee_id=employee,
            due_on=date(2026, 11, 20),
        )
        db.add(acceptance)
        await db.commit()
        rig.update(
            {
                "policy_id": ident,
                "acceptance_id": acceptance.id,
                "actor": actor,
                "employee": employee,
            }
        )
    return rig


async def test_sent_versions_allow_archive_but_never_overwrite_evidence(
    policy: dict[str, Any],
) -> None:
    for statement in (
        "update policy_documents set title='Changed' where id=:i",
        "update policy_documents set status='draft' where id=:i",
        "delete from policy_documents where id=:i",
    ):
        with pytest.raises(IntegrityError):
            async with policy["owner"].begin() as db:
                await db.execute(text(statement), {"i": policy["policy_id"]})
    async with policy["owner"].begin() as db:
        await db.execute(
            text("update policy_documents set status='archived', archived_at=now() where id=:i"),
            {"i": policy["policy_id"]},
        )
    with pytest.raises(IntegrityError):
        async with policy["owner"].begin() as db:
            await db.execute(
                text("update policy_documents set title='Archived rewrite' where id=:i"),
                {"i": policy["policy_id"]},
            )


async def test_completed_receipts_and_original_assignment_are_frozen(
    policy: dict[str, Any],
) -> None:
    with pytest.raises(IntegrityError):
        async with policy["owner"].begin() as db:
            await db.execute(
                text("update policy_acceptances set due_on=due_on+1 where id=:i"),
                {"i": policy["acceptance_id"]},
            )
    async with TenantSession(policy["app"].state.engine, company_id=policy["a"]) as db:
        row = (
            await db.execute(
                select(PolicyAcceptance).where(PolicyAcceptance.id == policy["acceptance_id"])
            )
        ).scalar_one()
        row.status, row.accepted_at, row.accepted_by = (
            "accepted",
            datetime.now(UTC),
            policy["actor"],
        )
        row.ip, row.user_agent = "127.0.0.1", "Policy schema test"
        await db.commit()
    for statement in (
        "update policy_acceptances set ip='192.0.2.1' where id=:i",
        "delete from policy_acceptances where id=:i",
    ):
        with pytest.raises(IntegrityError):
            async with policy["owner"].begin() as db:
                await db.execute(text(statement), {"i": policy["acceptance_id"]})


async def test_tenant_file_employee_and_confirmation_mode_are_enforced(
    policy: dict[str, Any],
) -> None:
    foreign = await _employee(policy, policy["b"], "FOREIGN-POL")
    async with TenantSession(policy["app"].state.engine, company_id=policy["a"]) as db:
        db.add(
            PolicyAcceptance(
                company_id=policy["a"],
                policy_document_id=policy["policy_id"],
                employee_id=foreign,
                due_on=date(2026, 11, 20),
            )
        )
        with pytest.raises(IntegrityError):
            await db.commit()
    async with TenantSession(policy["app"].state.engine, company_id=policy["a"]) as db:
        receipt = (
            await db.execute(
                select(PolicyAcceptance).where(PolicyAcceptance.id == policy["acceptance_id"])
            )
        ).scalar_one()
        receipt.status, receipt.accepted_at, receipt.accepted_by = (
            "signed",
            datetime.now(UTC),
            policy["actor"],
        )
        receipt.typed_signature = "Example signer"
        with pytest.raises(IntegrityError):
            await db.commit()
    async with TenantSession(policy["app"].state.engine, company_id=policy["b"]) as db:
        file = File(
            company_id=policy["b"],
            storage_key=f"policy-test/{uuid.uuid4()}",
            original_name="foreign.pdf",
            mime="application/pdf",
            size=1,
            sha256="0" * 64,
            scan_status="clean",
        )
        db.add(file)
        await db.commit()
        foreign_file = file.id
    async with TenantSession(policy["app"].state.engine, company_id=policy["a"]) as db:
        ident = uuid7()
        db.add(
            PolicyDocument(
                id=ident,
                group_id=ident,
                company_id=policy["a"],
                title="Foreign file",
                category="other",
                file_id=foreign_file,
            )
        )
        with pytest.raises(IntegrityError):
            await db.commit()
