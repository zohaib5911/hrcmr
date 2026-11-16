"""T16.1: the Stripe client. Webhook signatures are checked on the raw body; writes carry an
idempotency key and a retry re-sends the same key."""

from __future__ import annotations

import json
from urllib.parse import parse_qsl

import httpx
import pytest
from pydantic import SecretStr

from app.integrations.stripe import (
    Stripe,
    StripeError,
    StripeSignatureError,
    form_fields,
    sign,
    verify_signature,
)

SECRET = "whsec_test"
NOW = 1_800_000_000
BODY = json.dumps({"id": "evt_1", "type": "invoice.paid"}).encode()


def test_a_valid_recent_signature_gives_the_event() -> None:
    assert verify_signature(BODY, sign(BODY, SECRET, NOW), SECRET, now=NOW + 10)["id"] == "evt_1"


def test_any_v1_signature_may_match_while_a_secret_is_rolled() -> None:
    header = f"t={NOW},v1=deadbeef," + sign(BODY, SECRET, NOW).split(",")[1]
    assert verify_signature(BODY, header, SECRET, now=NOW)["id"] == "evt_1"


@pytest.mark.parametrize(
    ("body", "header", "now"),
    [
        (BODY, None, NOW),  # no header
        (BODY, "v1=abc", NOW),  # no timestamp
        (BODY, sign(BODY, "whsec_other", NOW), NOW),  # another secret
        (BODY.replace(b"evt_1", b"evt_2"), sign(BODY, SECRET, NOW), NOW),  # body changed
        (BODY, sign(BODY, SECRET, NOW), NOW + 301),  # too old: a replay
        (b"[]", sign(b"[]", SECRET, NOW), NOW),  # signed, but not an event
        (BODY, f"t={NOW},v1=\u00e9", NOW),  # not ASCII: refused, not a crash (C6.1.5)
    ],
)
def test_anything_else_is_refused(body: bytes, header: str | None, now: int) -> None:
    with pytest.raises(StripeSignatureError):
        verify_signature(body, header, SECRET, now=now)


def test_nested_form_encoding() -> None:
    assert form_fields(
        {"a": 1, "m": {"k": "v"}, "items": [{"price": "p", "quantity": 1}], "skip": None}
    ) == [("a", "1"), ("m[k]", "v"), ("items[0][price]", "p"), ("items[0][quantity]", "1")]


def _stripe(handler: httpx.MockTransport) -> Stripe:
    return Stripe(
        SecretStr("rk_test_x"),
        SecretStr(SECRET),
        {"annual": "price_a", "ten_year": "price_t"},
        client=httpx.AsyncClient(transport=handler),
    )


async def test_a_failed_write_is_retried_with_the_same_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.integrations.stripe.RETRY_WAIT_SECONDS", 0)
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={"id": "cs_1", "url": "https://checkout.stripe.com/x"})

    stripe = _stripe(httpx.MockTransport(answer))
    session = await stripe.create_checkout_session(
        company_id="c1",
        customer="cus_1",
        plan="ten_year",
        success_url="https://app/ok",
        cancel_url="https://app/no",
        idempotency_key="checkout-c1-1",
    )
    assert session["id"] == "cs_1"
    assert [r.headers["Idempotency-Key"] for r in seen] == ["checkout-c1-1"] * 2
    form = dict(parse_qsl(seen[0].content.decode()))
    assert form["mode"] == "payment"
    assert form["line_items[0][price]"] == "price_t"
    assert form["payment_intent_data[metadata][company_id]"] == "c1"
    assert seen[0].headers["Authorization"] == "Bearer rk_test_x"


async def test_a_refusal_is_not_retried_and_raises() -> None:
    calls = 0

    def answer(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": {"message": "No such price"}})

    stripe = _stripe(httpx.MockTransport(answer))
    with pytest.raises(StripeError):
        await stripe.create_customer(company_id="c1", name="Co", email=None)
    assert calls == 1


async def test_ids_from_events_cannot_change_the_path() -> None:
    stripe = _stripe(httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(StripeError):
        await stripe.retrieve_customer("cus_1/../../v1/refunds")


def test_payments_are_off_without_a_key_or_a_price() -> None:
    assert not Stripe(None, None, {"annual": "p", "ten_year": "q"}).enabled
    assert not Stripe(SecretStr("rk"), None, {"annual": "p", "ten_year": None}).enabled
