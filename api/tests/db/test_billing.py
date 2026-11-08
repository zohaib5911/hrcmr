"""T16.1: Stripe Checkout and the webhook, with Stripe replaced by a fake transport.

The webhook checks Stripe's signature on the raw body, applies each event id once (a replay changes
nothing), starts the annual plan from the live subscription and the 10-year plan from the payment,
and ends a refunded 10-year plan. Only a role with billing.manage may start Checkout.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import column, table, text, update

from app.integrations.stripe import Stripe, sign
from tests.db.test_careers import anonymous
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig

API = "/api/v1"
WEBHOOK_SECRET = "whsec_test"
START = 1_793_000_000  # 2026-10-26
END = START + 365 * 86400


class FakeStripe:
    """Answers the calls the app makes, and keeps every request it was sent."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.subscription: dict[str, Any] = {
            "id": "sub_1",
            "object": "subscription",
            "status": "active",
            "customer": "cus_1",
            "start_date": START,
            "cancel_at": None,
            "cancel_at_period_end": False,
            "items": {"data": [{"current_period_start": START, "current_period_end": END}]},
        }
        self.customer_company = ""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/v1/customers":
            return httpx.Response(200, json={"id": "cus_1"})
        if path == "/v1/checkout/sessions":
            return httpx.Response(200, json={"id": "cs_1", "url": "https://checkout.stripe.com/c"})
        if path == "/v1/billing_portal/sessions":
            return httpx.Response(200, json={"url": "https://billing.stripe.com/p"})
        if path == "/v1/subscriptions/sub_1":
            return httpx.Response(200, json=self.subscription)
        if path == "/v1/customers/cus_1":
            return httpx.Response(200, json={"id": "cus_1", "metadata": self.customer_company})
        return httpx.Response(404, json={})


@pytest.fixture(autouse=True)
async def free(rig: dict[str, Any]) -> None:
    """Both companies start on the free plan, as a new sign-up does."""
    async with rig["owner"].begin() as c:
        await c.execute(text("update companies set plan = 'free', subscription_status = null"))


@pytest.fixture
def fake(rig: dict[str, Any]) -> FakeStripe:
    fake = FakeStripe()
    rig["app"].state.stripe = Stripe(
        SecretStr("rk_test_x"),
        SecretStr(WEBHOOK_SECRET),
        {"annual": "price_annual", "ten_year": "price_ten_year"},
        client=httpx.AsyncClient(transport=httpx.MockTransport(fake)),
    )
    return fake


def _event(event_id: str, kind: str, obj: dict[str, Any]) -> dict[str, Any]:
    return {"id": event_id, "type": kind, "created": START, "data": {"object": obj}}


async def _deliver(
    rig: dict[str, Any], event: dict[str, Any], secret: str = WEBHOOK_SECRET
) -> httpx.Response:
    body = json.dumps(event).encode()
    stripe = anonymous(rig)
    stripe.cookies.clear()  # Stripe has no browser: no cookie and no CSRF header
    del stripe.headers["X-CSRF-Token"]
    async with stripe:
        return await stripe.post(
            f"{API}/webhooks/stripe",
            content=body,
            headers={
                "Stripe-Signature": sign(body, secret, int(time.time())),
                "Content-Type": "application/json",
            },
        )


async def _company(rig: dict[str, Any]) -> dict[str, Any]:
    async with rig["owner"].connect() as c:
        row = (
            await c.execute(
                text(
                    "select plan, subscription_status, subscription_started_at, "
                    "subscription_ends_at, cooling_off_ends_at, stripe_customer_id, "
                    "stripe_subscription_id from companies where id = :c"
                ),
                {"c": rig["a"]},
            )
        ).one()
    return dict(row._mapping)


async def _count(rig: dict[str, Any], sql: str) -> int:
    async with rig["owner"].connect() as c:
        return int((await c.execute(text(sql), {"c": rig["a"]})).scalar_one())


async def _clear_events(rig: dict[str, Any]) -> None:
    async with rig["owner"].begin() as c:
        await c.execute(text("truncate stripe_events"))


async def test_checkout_makes_one_customer_and_a_session_for_the_plan(
    rig: dict[str, Any], fake: FakeStripe
) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    refused = await hr.post(f"{API}/billing/checkout-session", json={"plan": "annual"})
    assert refused.status_code == 403

    admin = await rig["person"]("company_admin", rig["a"])
    made = await admin.post(f"{API}/billing/checkout-session", json={"plan": "annual"})
    assert made.status_code == 200, made.text
    assert made.json() == {"url": "https://checkout.stripe.com/c"}
    customer, session = fake.requests
    assert customer.headers["Idempotency-Key"] == f"customer-{rig['a']}"
    form = dict(parse_qsl(session.content.decode()))
    assert form["mode"] == "subscription"
    assert form["line_items[0][price]"] == "price_annual"
    assert form["client_reference_id"] == str(rig["a"])
    assert form["subscription_data[metadata][company_id]"] == str(rig["a"])
    assert form["success_url"] == "http://localhost:3000/company/billing?checkout=success"
    assert session.headers["Idempotency-Key"].startswith(f"checkout-{rig['a']}-")
    assert (await _company(rig))["stripe_customer_id"] == "cus_1"

    again = await admin.post(f"{API}/billing/checkout-session", json={"plan": "ten_year"})
    assert again.status_code == 200
    assert [r.url.path for r in fake.requests[2:]] == ["/v1/checkout/sessions"]  # same customer
    assert (
        await _count(
            rig,
            "select count(*) from audit_events where company_id = :c "
            "and action = 'billing.checkout_started'",
        )
        == 2
    )
    portal = await admin.post(f"{API}/billing/portal-session")
    assert portal.json() == {"url": "https://billing.stripe.com/p"}


async def test_payments_not_set_up_say_so(rig: dict[str, Any]) -> None:
    rig["app"].state.stripe = Stripe(None, None, {"annual": None, "ten_year": None})
    admin = await rig["person"]("company_admin", rig["a"])
    response = await admin.post(f"{API}/billing/checkout-session", json={"plan": "annual"})
    assert response.status_code == 503
    assert (await admin.get(f"{API}/billing/subscription")).json()["payments_enabled"] is False
    assert (await _deliver(rig, _event("evt_x", "invoice.paid", {}))).status_code == 503


async def test_a_bad_signature_changes_nothing(rig: dict[str, Any], fake: FakeStripe) -> None:
    await _clear_events(rig)
    event = _event(
        "evt_forged",
        "checkout.session.completed",
        {
            "object": "checkout.session",
            "mode": "payment",
            "payment_status": "paid",
            "payment_intent": "pi_1",
            "client_reference_id": str(rig["a"]),
            "metadata": {"company_id": str(rig["a"]), "plan": "ten_year"},
        },
    )
    response = await _deliver(rig, event, secret="whsec_attacker")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"
    assert (await _company(rig))["plan"] == "free"
    assert await _count(rig, "select count(*) from stripe_events") == 0


async def test_the_annual_plan_starts_from_the_live_subscription_and_a_replay_does_nothing(
    rig: dict[str, Any], fake: FakeStripe
) -> None:
    await _clear_events(rig)
    completed = _event(
        "evt_annual",
        "checkout.session.completed",
        {
            "object": "checkout.session",
            "mode": "subscription",
            "payment_status": "paid",
            "subscription": "sub_1",
            "customer": "cus_1",
            "client_reference_id": str(rig["a"]),
            "metadata": {"company_id": str(rig["a"]), "plan": "annual"},
        },
    )
    assert (await _deliver(rig, completed)).status_code == 200
    company = await _company(rig)
    started = datetime.fromtimestamp(START, UTC)
    assert company["plan"] == "annual"
    assert company["subscription_status"] == "active"
    assert company["subscription_started_at"] == started
    assert company["subscription_ends_at"] == datetime.fromtimestamp(END, UTC)
    assert company["cooling_off_ends_at"] == started + timedelta(days=14)
    assert company["stripe_subscription_id"] == "sub_1"
    audit = "select count(*) from audit_events where company_id = :c and action like 'billing.%'"
    events = await _count(rig, audit)

    replay = await _deliver(rig, completed)
    assert replay.status_code == 200
    assert await _count(rig, audit) == events
    assert await _count(rig, "select count(*) from stripe_events") == 1
    assert await _count(rig, "select count(*) from subscriptions where company_id = :c") == 1

    # A failed renewal: the invoice names no company, so the customer's metadata is asked.
    fake.customer_company = ""
    fake.subscription["status"] = "past_due"
    failed = _event(
        "evt_failed",
        "invoice.payment_failed",
        {"object": "invoice", "customer": "cus_1", "subscription": "sub_1", "metadata": {}},
    )
    fake.customer_company = {"company_id": str(rig["a"])}  # type: ignore[assignment]
    assert (await _deliver(rig, failed)).status_code == 200
    assert (await _company(rig))["subscription_status"] == "past_due"

    fake.subscription |= {"status": "canceled", "ended_at": END}
    deleted = _event(
        "evt_deleted",
        "customer.subscription.deleted",
        {
            "id": "sub_1",
            "object": "subscription",
            "customer": "cus_1",
            "metadata": {"company_id": str(rig["a"])},
        },
    )
    assert (await _deliver(rig, deleted)).status_code == 200
    company = await _company(rig)
    assert (company["plan"], company["subscription_status"]) == ("free", "canceled")


async def test_the_ten_year_plan_starts_from_the_payment_and_ends_on_a_full_refund(
    rig: dict[str, Any], fake: FakeStripe
) -> None:
    await _clear_events(rig)
    paid = _event(
        "evt_ten",
        "checkout.session.completed",
        {
            "object": "checkout.session",
            "mode": "payment",
            "payment_status": "paid",
            "payment_intent": "pi_1",
            "customer": "cus_1",
            "client_reference_id": str(rig["a"]),
            "metadata": {"company_id": str(rig["a"]), "plan": "ten_year"},
        },
    )
    assert (await _deliver(rig, paid)).status_code == 200
    company = await _company(rig)
    started = datetime.fromtimestamp(START, UTC)
    assert company["plan"] == "ten_year"
    assert company["subscription_ends_at"] == started.replace(year=started.year + 10)
    assert company["cooling_off_ends_at"] == started + timedelta(days=14)

    admin = await rig["person"]("company_admin", rig["a"])
    shown = (await admin.get(f"{API}/billing/subscription")).json()
    assert (shown["plan"], shown["payments_enabled"], shown["has_billing_account"]) == (
        "ten_year",
        True,
        True,
    )
    refused = await admin.post(f"{API}/billing/checkout-session", json={"plan": "annual"})
    assert refused.status_code == 409

    partial = _event(
        "evt_partial",
        "charge.refunded",
        {
            "object": "charge",
            "refunded": False,
            "payment_intent": "pi_1",
            "customer": "cus_1",
            "metadata": {"company_id": str(rig["a"])},
        },
    )
    assert (await _deliver(rig, partial)).status_code == 200
    assert (await _company(rig))["plan"] == "ten_year"
    refund = _event(
        "evt_refund",
        "charge.refunded",
        {
            "object": "charge",
            "refunded": True,
            "payment_intent": "pi_1",
            "customer": "cus_1",
            "metadata": {"company_id": str(rig["a"])},
        },
    )
    assert (await _deliver(rig, refund)).status_code == 200
    company = await _company(rig)
    assert (company["plan"], company["subscription_status"]) == ("free", "refunded")
    # Company b was never touched.
    async with rig["owner"].connect() as c:
        other = (
            await c.execute(text("select plan from companies where id = :b"), {"b": rig["b"]})
        ).scalar_one()
    assert other == "free"


async def test_an_event_for_another_customer_is_ignored(
    rig: dict[str, Any], fake: FakeStripe
) -> None:
    await _clear_events(rig)
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update companies set stripe_customer_id = 'cus_mine' where id = :c"),
            {"c": rig["a"]},
        )
    stray = _event(
        "evt_stray",
        "checkout.session.completed",
        {
            "object": "checkout.session",
            "mode": "payment",
            "payment_status": "paid",
            "payment_intent": "pi_9",
            "customer": "cus_someone_else",
            "metadata": {"company_id": str(rig["a"]), "plan": "ten_year"},
        },
    )
    assert (await _deliver(rig, stray)).status_code == 200
    assert (await _company(rig))["plan"] == "free"


async def _set_plan(rig: dict[str, Any], **values: Any) -> None:
    companies = table("companies", column("id"), *(column(name) for name in values))
    async with rig["owner"].begin() as c:
        await c.execute(update(companies).where(companies.c.id == rig["a"]).values(**values))


async def test_a_free_or_lapsed_company_is_read_only_but_can_pay_and_keep_its_profile(
    rig: dict[str, Any], fake: FakeStripe
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    assert (await admin.get(f"{API}/company")).status_code == 200
    refused = await admin.post(f"{API}/departments", json={"name": "Sales"})
    assert refused.status_code == 402
    assert refused.json()["error"]["code"] == "PLAN_REQUIRED"
    # Billing, the company profile and reads made by POST are not gated.
    assert (await admin.patch(f"{API}/company", json={"trading_name": "Co"})).status_code == 200
    assert (await admin.post(f"{API}/notifications/read-all")).status_code != 402
    assert (
        await admin.post(f"{API}/billing/checkout-session", json={"plan": "annual"})
    ).status_code == 200

    now = datetime.now(UTC)
    await _set_plan(rig, plan="annual", subscription_status="active")
    assert (await admin.post(f"{API}/departments", json={"name": "Sales"})).status_code == 201
    # A failed renewal keeps working through the grace period, then is read-only.
    await _set_plan(
        rig, subscription_status="past_due", payment_grace_ends_at=now + timedelta(days=1)
    )
    assert (await admin.post(f"{API}/departments", json={"name": "Ops"})).status_code == 201
    await _set_plan(rig, payment_grace_ends_at=now - timedelta(minutes=1))
    assert (await admin.post(f"{API}/departments", json={"name": "HR"})).status_code == 402
    await _set_plan(rig, subscription_status="canceled", plan="free")
    assert (await admin.post(f"{API}/departments", json={"name": "HR"})).status_code == 402
    # A 10-year plan works until its end date.
    await _set_plan(
        rig,
        plan="ten_year",
        subscription_status="active",
        subscription_ends_at=now + timedelta(days=1),
    )
    assert (await admin.post(f"{API}/departments", json={"name": "HR"})).status_code == 201
    await _set_plan(rig, subscription_ends_at=now - timedelta(days=1))
    assert (await admin.post(f"{API}/departments", json={"name": "IT"})).status_code == 402


async def test_a_failed_renewal_starts_seven_days_of_grace_once_and_tells_the_admins(
    rig: dict[str, Any], fake: FakeStripe
) -> None:
    await _clear_events(rig)
    admin = await rig["person"]("company_admin", rig["a"])
    await rig["person"]("hr_admin", rig["a"])  # not told: billing is the company admin's
    await rig["person"]("company_admin", rig["b"])  # another company's admin: not told
    await _set_plan(rig, stripe_customer_id="cus_1")
    metadata = {"company_id": str(rig["a"])}
    fake.subscription["status"] = "past_due"

    def failed(event_id: str) -> dict[str, Any]:
        return _event(
            event_id,
            "invoice.payment_failed",
            {
                "object": "invoice",
                "customer": "cus_1",
                "subscription": "sub_1",
                "subscription_details": {"metadata": metadata},
            },
        )

    assert (await _deliver(rig, failed("evt_fail_1"))).status_code == 200
    company = await _company(rig)
    assert company["subscription_status"] == "past_due"
    async with rig["owner"].connect() as c:
        grace = (
            await c.execute(
                text("select payment_grace_ends_at from companies where id = :c"), {"c": rig["a"]}
            )
        ).scalar_one()
    assert grace == datetime.fromtimestamp(START, UTC) + timedelta(days=7)
    mail = "select count(*) from email_outbox where template = 'payment_failed'"
    notices = "select count(*) from notifications where company_id = :c and kind = 'billing.payment_failed'"
    assert (await _count(rig, mail), await _count(rig, notices)) == (1, 1)

    # Stripe's next retry fails too: the date stays, and nobody is mailed again.
    assert (await _deliver(rig, failed("evt_fail_2"))).status_code == 200
    assert (await _count(rig, mail), await _count(rig, notices)) == (1, 1)

    # The card is fixed: the grace period is over and writes need nothing more.
    fake.subscription["status"] = "active"
    paid = _event(
        "evt_paid",
        "invoice.paid",
        {
            "object": "invoice",
            "customer": "cus_1",
            "subscription": "sub_1",
            "subscription_details": {"metadata": metadata},
        },
    )
    assert (await _deliver(rig, paid)).status_code == 200
    async with rig["owner"].connect() as c:
        grace = (
            await c.execute(
                text("select payment_grace_ends_at from companies where id = :c"), {"c": rig["a"]}
            )
        ).scalar_one()
    assert grace is None
    assert (await admin.post(f"{API}/departments", json={"name": "Sales"})).status_code == 201
