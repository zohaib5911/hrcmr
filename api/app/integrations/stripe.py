"""Stripe: customers, Checkout, the Billing Portal and webhook signatures (plan.md 8.16, T16.1).

Every Stripe call in the app goes through this module, from the server only, with a restricted key
(deployment-requirements.txt 5.4). It speaks Stripe's form-encoded REST API over httpx, as the other
integrations do, so tests replace the transport and nothing reaches Stripe.

Writes carry an ``Idempotency-Key``. A network error, a 429 or a 5xx is retried with the SAME key,
so Stripe performs the write at most once however many times we send it.

With no key (local development, tests) payments are off and the billing endpoints say so. Deployed
environments cannot start without the keys (``stripe_*`` are in the required list in
``app/core/config.py``).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx

from app.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic import SecretStr

    from app.core.config import Settings

logger = get_logger("app.stripe")

BASE_URL = "https://api.stripe.com"
TIMEOUT_SECONDS = 15.0
ATTEMPTS = 3
RETRY_WAIT_SECONDS = 0.5  # times the attempt number
SIGNATURE_TOLERANCE_SECONDS = 300  # Stripe's own default: older signed payloads are replays
PLANS = ("annual", "ten_year")
_OBJECT_ID = re.compile(r"[A-Za-z0-9_]{1,255}")


class StripeError(Exception):
    """Stripe could not be reached, or refused the request. The message is safe to log."""


class StripeSignatureError(Exception):
    """A webhook body that Stripe did not sign with our endpoint secret, or signed too long ago."""


def form_fields(data: Mapping[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    """Stripe's nested form encoding: ``{"metadata": {"a": 1}}`` becomes ``metadata[a]=1``."""
    fields: list[tuple[str, str]] = []
    for key, value in data.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if value is None:
            continue
        if isinstance(value, dict):
            fields.extend(form_fields(value, name))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    fields.extend(form_fields(item, f"{name}[{index}]"))
                else:
                    fields.append((f"{name}[{index}]", str(item)))
        elif isinstance(value, bool):
            fields.append((name, "true" if value else "false"))
        else:
            fields.append((name, str(value)))
    return fields


def sign(payload: bytes, secret: str, timestamp: int) -> str:
    """The ``Stripe-Signature`` header Stripe would send for ``payload`` (used by tests)."""
    digest = hmac.new(
        secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_signature(
    payload: bytes,
    header: str | None,
    secret: str,
    *,
    now: float | None = None,
    tolerance: int = SIGNATURE_TOLERANCE_SECONDS,
) -> dict[str, Any]:
    """The event in ``payload`` if ``header`` is Stripe's valid, recent signature of it.

    Checked against the raw bytes, before any parsing. Any ``v1`` value may match (Stripe sends
    one per active secret while a secret is being rolled)."""
    if not header:
        raise StripeSignatureError("no signature")
    timestamp: int | None = None
    signatures: list[str] = []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t" and value.isdigit():
            timestamp = int(value)
        elif key == "v1" and value:
            signatures.append(value)
    if timestamp is None or not signatures:
        raise StripeSignatureError("malformed signature")
    expected = sign(payload, secret, timestamp).rsplit("=", 1)[1]
    if not any(hmac.compare_digest(expected, given) for given in signatures):
        raise StripeSignatureError("signature does not match")
    if abs((now if now is not None else time.time()) - timestamp) > tolerance:
        raise StripeSignatureError("signature is too old")
    try:
        event = json.loads(payload)
    except ValueError as exc:
        raise StripeSignatureError("body is not JSON") from exc
    if not isinstance(event, dict) or not isinstance(event.get("id"), str):
        raise StripeSignatureError("body is not an event")
    return event


class Stripe:
    def __init__(
        self,
        secret_key: SecretStr | None,
        webhook_secret: SecretStr | None,
        prices: Mapping[str, str | None],
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._key = secret_key
        self._webhook_secret = webhook_secret
        self._prices = dict(prices)
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> Stripe:
        return cls(
            settings.stripe_secret_key,
            settings.stripe_webhook_secret,
            {"annual": settings.stripe_price_annual, "ten_year": settings.stripe_price_ten_year},
        )

    @property
    def enabled(self) -> bool:
        """Checkout can be offered: a key and a price for every plan."""
        return self._key is not None and all(self._prices.get(plan) for plan in PLANS)

    @property
    def webhooks_enabled(self) -> bool:
        return self._key is not None and self._webhook_secret is not None

    def price_for(self, plan: str) -> str:
        price = self._prices.get(plan)
        if not price:
            raise StripeError(f"no price is set for the {plan} plan")
        return price

    def construct_event(self, payload: bytes, header: str | None) -> dict[str, Any]:
        if self._webhook_secret is None:
            raise StripeSignatureError("webhooks are not set up")
        return verify_signature(payload, header, self._webhook_secret.get_secret_value())

    # --- Calls -----------------------------------------------------------------------------------

    async def create_customer(
        self, *, company_id: str, name: str, email: str | None
    ) -> dict[str, Any]:
        # One key per company: two clicks on "Upgrade" at once still make a single customer.
        return await self._post(
            "/v1/customers",
            {"name": name, "email": email, "metadata": {"company_id": company_id}},
            idempotency_key=f"customer-{company_id}",
        )

    async def create_checkout_session(
        self,
        *,
        company_id: str,
        customer: str,
        plan: str,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Annual is a subscription; 10-year is a one-off payment. Both carry the company id and the
        plan in metadata, so every later event names the company it belongs to."""
        tags = {"company_id": company_id, "plan": plan}
        data: dict[str, Any] = {
            "customer": customer,
            "client_reference_id": company_id,
            "line_items": [{"price": self.price_for(plan), "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": tags,
        }
        if plan == "annual":
            data |= {"mode": "subscription", "subscription_data": {"metadata": tags}}
        else:
            data |= {"mode": "payment", "payment_intent_data": {"metadata": tags}}
        return await self._post("/v1/checkout/sessions", data, idempotency_key=idempotency_key)

    async def create_portal_session(
        self, *, customer: str, return_url: str, idempotency_key: str
    ) -> dict[str, Any]:
        return await self._post(
            "/v1/billing_portal/sessions",
            {"customer": customer, "return_url": return_url},
            idempotency_key=idempotency_key,
        )

    async def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]:
        return await self._get("/v1/subscriptions", subscription_id)

    async def retrieve_customer(self, customer_id: str) -> dict[str, Any]:
        return await self._get("/v1/customers", customer_id)

    # --- Transport -------------------------------------------------------------------------------

    async def _post(
        self, path: str, data: Mapping[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        return await self._send("POST", path, form_fields(data), idempotency_key)

    async def _get(self, collection: str, object_id: str) -> dict[str, Any]:
        # Ids come from signed events; still, only a plain id may become part of the path.
        if not _OBJECT_ID.fullmatch(object_id):
            raise StripeError("unexpected Stripe id")
        return await self._send("GET", f"{collection}/{object_id}", None, None)

    async def _send(
        self,
        method: str,
        path: str,
        fields: list[tuple[str, str]] | None,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        if self._key is None:
            raise StripeError("payments are not set up")
        headers = {"Authorization": f"Bearer {self._key.get_secret_value()}"}
        body = None
        if fields is not None:
            # Encoded by hand: a list of pairs keeps Stripe's repeated and nested keys in order.
            body = urlencode(fields).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        client = self._client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
        try:
            for attempt in range(1, ATTEMPTS + 1):
                try:
                    response = await client.request(
                        method,
                        BASE_URL + path,
                        content=body,
                        headers=headers,
                        timeout=TIMEOUT_SECONDS,
                    )
                except httpx.TransportError as exc:
                    if attempt == ATTEMPTS:
                        raise StripeError(f"Stripe could not be reached ({path})") from exc
                else:
                    if response.status_code < 400:
                        answer: dict[str, Any] = response.json()
                        return answer
                    retry = response.status_code == 429 or response.status_code >= 500
                    if not retry or attempt == ATTEMPTS:
                        logger.warning("stripe_refused", path=path, status=response.status_code)
                        raise StripeError(f"Stripe refused the request ({response.status_code})")
                await asyncio.sleep(RETRY_WAIT_SECONDS * attempt)
        finally:
            if self._client is None:
                await client.aclose()
        raise StripeError("unreachable")  # pragma: no cover
