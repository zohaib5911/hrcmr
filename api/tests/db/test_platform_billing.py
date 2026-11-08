"""T17.4: platform admins read the subscriptions, the deletion and export queues and the contact
messages; only an owner issues a refund. Stripe is replaced by a fake transport, so nothing reaches
Stripe. A refund is one full refund of the latest payment, sent with the self-serve idempotency key,
so a second request changes nothing. Every change is audited under the platform admin.

The rig gives two companies, "a" and "b", both active. Purchases are seeded straight into the
database, as the webhook would have written them."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text

from app.integrations.stripe import Stripe
from tests.db.test_employee_documents import rig as rig

API = "/api/v1"
PLANS = {"annual": "price_annual", "ten_year": "price_ten_year"}


class FakeStripe:
    """Answers the calls a refund makes, and keeps every request it was sent."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.refuse_refund = False  # the refund call fails with a 400

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/v1/refunds":
            if self.refuse_refund:
                return httpx.Response(400, json={"error": {"message": "refused"}})
            return httpx.Response(
                200, json={"id": "re_1", "object": "refund", "status": "succeeded"}
            )
        if path == "/v1/subscriptions/sub_annual":
            return httpx.Response(200, json={"id": "sub_annual", "latest_invoice": "in_1"})
        if path == "/v1/subscriptions/sub_empty":
            return httpx.Response(200, json={"id": "sub_empty", "latest_invoice": "in_empty"})
        if path == "/v1/invoices/in_1":
            return httpx.Response(200, json={"id": "in_1", "payment_intent": "pi_annual_latest"})
        if path == "/v1/invoices/in_empty":
            return httpx.Response(200, json={"id": "in_empty", "payments": {"data": []}})
        return httpx.Response(404, json={})

    def refunds(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path == "/v1/refunds"]


@pytest.fixture
def fake(rig: dict[str, Any]) -> FakeStripe:
    fake = FakeStripe()
    rig["app"].state.stripe = Stripe(
        SecretStr("rk_test_x"),
        SecretStr("whsec_test"),
        PLANS,
        client=httpx.AsyncClient(transport=httpx.MockTransport(fake)),
    )
    return fake


async def _platform_admin(rig: dict[str, Any], level: str) -> Any:
    """A signed-in company administrator made a platform admin at ``level``, with MFA, and the
    platform cookie started, as the admin pages need (T17.1)."""
    admin = await rig["person"]("company_admin", rig["a"])
    me = uuid.UUID((await admin.get(f"{API}/auth/me")).json()["user"]["id"])
    async with rig["owner"].begin() as c:
        await c.execute(
            text("insert into platform_admins (user_id, level) values (:u, :l)"),
            {"u": me, "l": level},
        )
        await c.execute(text("update users set mfa_enabled=true where id=:u"), {"u": me})
    started = await admin.post(f"{API}/auth/platform-session")
    assert started.status_code == 201, started.text
    return admin


async def _seed_annual(rig: dict[str, Any], company: uuid.UUID, subscription: str) -> uuid.UUID:
    row = uuid.uuid4()
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into subscriptions (id, company_id, plan, status, stripe_subscription_id) "
                "values (:i, :c, 'annual', 'active', :s)"
            ),
            {"i": row, "c": company, "s": subscription},
        )
    return row


async def _seed_ten_year(rig: dict[str, Any], company: uuid.UUID, payment: str) -> uuid.UUID:
    row = uuid.uuid4()
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into subscriptions (id, company_id, plan, status, stripe_payment_intent_id) "
                "values (:i, :c, 'ten_year', 'active', :p)"
            ),
            {"i": row, "c": company, "p": payment},
        )
    return row


async def _refunded_at(rig: dict[str, Any], row: uuid.UUID) -> Any:
    async with rig["owner"].connect() as c:
        return (
            await c.execute(text("select refunded_at from subscriptions where id = :i"), {"i": row})
        ).scalar_one()


async def _audit(rig: dict[str, Any], entity: uuid.UUID) -> list[tuple[str, str | None]]:
    async with rig["owner"].connect() as c:
        rows = await c.execute(
            text(
                "select action, reason from audit_events where entity_id = :e "
                "and action like 'platform.%' order by created_at"
            ),
            {"e": entity},
        )
        return [(str(action), reason) for action, reason in rows.all()]


def _refund_body(row: uuid.UUID, **extra: Any) -> dict[str, Any]:
    return {
        "subscription_id": str(row),
        "reason": "Duplicate charge, ticket 1234",
        "confirm": True,
    } | extra


async def test_only_a_platform_admin_reads_the_subscriptions(rig: dict[str, Any]) -> None:
    company_admin = await rig["person"]("company_admin", rig["a"])
    assert (await company_admin.get(f"{API}/platform/subscriptions")).status_code == 403


async def test_the_subscription_list_shows_every_company_and_filters(rig: dict[str, Any]) -> None:
    await _seed_annual(rig, rig["a"], "sub_annual")
    await _seed_ten_year(rig, rig["b"], "pi_ten")
    admin = await _platform_admin(rig, "support")
    everything = (await admin.get(f"{API}/platform/subscriptions")).json()
    assert everything["total"] == 2
    names = {item["company_name"] for item in everything["items"]}
    assert len(names) == 2
    ten = (await admin.get(f"{API}/platform/subscriptions?plan=ten_year")).json()
    assert [item["plan"] for item in ten["items"]] == ["ten_year"]
    assert ten["items"][0]["stripe_payment_intent_id"] == "pi_ten"
    refunded = (await admin.get(f"{API}/platform/subscriptions?refunded=true")).json()
    assert refunded == {"items": [], "total": 0}


async def test_a_support_admin_cannot_refund_and_nothing_is_sent_to_stripe(
    rig: dict[str, Any], fake: FakeStripe
) -> None:
    row = await _seed_ten_year(rig, rig["a"], "pi_ten")
    admin = await _platform_admin(rig, "support")
    refused = await admin.post(f"{API}/platform/refunds", json=_refund_body(row))
    assert refused.status_code == 403, refused.text
    assert fake.refunds() == []
    assert await _refunded_at(rig, row) is None


async def test_a_refund_needs_the_second_confirmation(
    rig: dict[str, Any], fake: FakeStripe
) -> None:
    row = await _seed_ten_year(rig, rig["a"], "pi_ten")
    owner = await _platform_admin(rig, "owner")
    unconfirmed = await owner.post(f"{API}/platform/refunds", json=_refund_body(row, confirm=False))
    assert unconfirmed.status_code == 422, unconfirmed.text
    assert unconfirmed.json()["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert fake.refunds() == []
    assert await _refunded_at(rig, row) is None


async def test_an_owner_refunds_a_ten_year_payment_once_and_it_is_audited(
    rig: dict[str, Any], fake: FakeStripe
) -> None:
    row = await _seed_ten_year(rig, rig["a"], "pi_ten")
    owner = await _platform_admin(rig, "owner")
    made = await owner.post(f"{API}/platform/refunds", json=_refund_body(row))
    assert made.status_code == 200, made.text
    body = made.json()
    assert body["stripe_refund_id"] == "re_1"
    assert body["subscription"]["refunded_at"] is not None
    assert body["subscription"]["status"] == "refunded"
    [sent] = fake.refunds()
    assert sent.headers["Idempotency-Key"] == "refund-pi_ten"
    assert b"payment_intent=pi_ten" in sent.content
    assert await _refunded_at(rig, row) is not None
    assert await _audit(rig, rig["a"]) == [
        ("platform.refund_issued", "Duplicate charge, ticket 1234")
    ]
    again = await owner.post(f"{API}/platform/refunds", json=_refund_body(row))
    assert again.status_code == 409, again.text
    assert again.json()["error"]["code"] == "ALREADY_REFUNDED"
    assert len(fake.refunds()) == 1


async def test_an_annual_refund_uses_the_latest_payment_behind_the_subscription(
    rig: dict[str, Any], fake: FakeStripe
) -> None:
    row = await _seed_annual(rig, rig["a"], "sub_annual")
    owner = await _platform_admin(rig, "owner")
    made = await owner.post(f"{API}/platform/refunds", json=_refund_body(row))
    assert made.status_code == 200, made.text
    assert made.json()["subscription"]["refunded_at"] is not None
    [sent] = fake.refunds()
    assert sent.headers["Idempotency-Key"] == "refund-pi_annual_latest"
    assert b"payment_intent=pi_annual_latest" in sent.content


async def test_a_purchase_with_no_payment_to_refund_says_so(
    rig: dict[str, Any], fake: FakeStripe
) -> None:
    row = await _seed_annual(rig, rig["a"], "sub_empty")
    owner = await _platform_admin(rig, "owner")
    made = await owner.post(f"{API}/platform/refunds", json=_refund_body(row))
    assert made.status_code == 409, made.text
    assert made.json()["error"]["code"] == "NOTHING_TO_REFUND"
    assert fake.refunds() == []
    assert await _refunded_at(rig, row) is None


async def test_a_refund_stripe_refuses_is_not_recorded(
    rig: dict[str, Any], fake: FakeStripe
) -> None:
    row = await _seed_ten_year(rig, rig["a"], "pi_ten")
    fake.refuse_refund = True
    owner = await _platform_admin(rig, "owner")
    made = await owner.post(f"{API}/platform/refunds", json=_refund_body(row))
    assert made.status_code == 502, made.text
    assert made.json()["error"]["code"] == "PAYMENTS_UNAVAILABLE"
    assert await _refunded_at(rig, row) is None
    assert await _audit(rig, rig["a"]) == []


async def test_payments_not_set_up_refuse_the_refund(rig: dict[str, Any]) -> None:
    row = await _seed_ten_year(rig, rig["a"], "pi_ten")
    rig["app"].state.stripe = Stripe(None, None, {"annual": None, "ten_year": None})
    owner = await _platform_admin(rig, "owner")
    made = await owner.post(f"{API}/platform/refunds", json=_refund_body(row))
    assert made.status_code == 503, made.text
    assert made.json()["error"]["code"] == "PAYMENTS_NOT_SET_UP"
    assert await _refunded_at(rig, row) is None


async def _user_id(admin: Any) -> uuid.UUID:
    return uuid.UUID((await admin.get(f"{API}/auth/me")).json()["user"]["id"])


async def _seed_deletion(
    rig: dict[str, Any], company: uuid.UUID, *, confirmed: bool = False, withdrawn: bool = False
) -> None:
    now = datetime.now(UTC)
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into deletion_requests (id, company_id, confirmed_at, scheduled_for, "
                "withdrawn_at, code_hash) values (:i, :c, :confirmed, :scheduled, :withdrawn, "
                ":hash)"
            ),
            {
                "i": uuid.uuid4(),
                "c": company,
                "confirmed": now if confirmed else None,
                "scheduled": now + timedelta(days=7) if confirmed else None,
                "withdrawn": now if withdrawn else None,
                "hash": "a" * 64,
            },
        )


async def _seed_export(
    rig: dict[str, Any], company: uuid.UUID, requested_by: uuid.UUID, *, status: str
) -> None:
    failed = status == "failed"
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into data_exports (id, company_id, requested_by, status, finished_at, "
                "error_code) values (:i, :c, :u, :s, :f, :e)"
            ),
            {
                "i": uuid.uuid4(),
                "c": company,
                "u": requested_by,
                "s": status,
                "f": datetime.now(UTC) if status != "queued" else None,
                "e": "EXPORT_FAILED" if failed else None,
            },
        )


async def test_only_a_platform_admin_reads_the_queues(rig: dict[str, Any]) -> None:
    company_admin = await rig["person"]("company_admin", rig["a"])
    for path in ("/platform/deletion-requests", "/platform/data-exports"):
        assert (await company_admin.get(f"{API}{path}")).status_code == 403


async def test_the_deletion_queue_shows_each_status_and_never_the_code(rig: dict[str, Any]) -> None:
    await _seed_deletion(rig, rig["a"], confirmed=True)
    await _seed_deletion(rig, rig["b"], withdrawn=True)
    admin = await _platform_admin(rig, "support")
    everything = await admin.get(f"{API}/platform/deletion-requests")
    assert everything.status_code == 200, everything.text
    assert everything.json()["total"] == 2
    assert "code_hash" not in everything.text
    assert "a" * 64 not in everything.text
    statuses = {item["status"] for item in everything.json()["items"]}
    assert statuses == {"scheduled", "withdrawn"}
    scheduled = (await admin.get(f"{API}/platform/deletion-requests?status=scheduled")).json()
    assert [item["company_id"] for item in scheduled["items"]] == [str(rig["a"])]
    assert scheduled["items"][0]["scheduled_for"] is not None


async def test_the_export_queue_shows_each_status(rig: dict[str, Any]) -> None:
    admin = await _platform_admin(rig, "owner")
    user = await _user_id(admin)
    await _seed_export(rig, rig["a"], user, status="queued")
    await _seed_export(rig, rig["b"], user, status="failed")
    everything = (await admin.get(f"{API}/platform/data-exports")).json()
    assert everything["total"] == 2
    failed = (await admin.get(f"{API}/platform/data-exports?status=failed")).json()
    assert [item["error_code"] for item in failed["items"]] == ["EXPORT_FAILED"]
    assert failed["items"][0]["company_id"] == str(rig["b"])
    queued = (await admin.get(f"{API}/platform/data-exports?status=queued")).json()
    assert [item["status"] for item in queued["items"]] == ["queued"]
