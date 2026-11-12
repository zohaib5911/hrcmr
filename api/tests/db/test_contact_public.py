"""T18.1: the public contact form. A visitor who is not signed in can leave one message; Turnstile
and a per-connection limit guard it, and the reply says only that it was received."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

from tests.db.test_careers import anonymous
from tests.db.test_employee_documents import rig as rig

API = "/api/v1"
MESSAGE = {
    "name": "Sam Jones",
    "company": "Jones Cafe Ltd",
    "email": "Sam@Example.com",
    "topic": "pricing_billing",
    "message": "Do you offer a discount for a team of five?",
    "turnstile_token": "test-token",
}


async def _accept(token: str | None, remote_ip: str | None = None) -> bool:
    return True


async def _refuse(token: str | None, remote_ip: str | None = None) -> bool:
    return False


async def test_a_message_is_stored_and_the_reply_says_only_received(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    public = anonymous(rig)
    monkeypatch.setattr(rig["app"].state.auth.turnstile, "verify", _accept)
    sent = await public.post(f"{API}/public/contact", json=MESSAGE)
    assert sent.status_code == 201, sent.text
    assert sent.json() == {"received": True}
    async with rig["owner"].connect() as connection:
        row = (
            await connection.execute(
                text("select email, topic, ip_hash from contact_messages where name = 'Sam Jones'")
            )
        ).one()
    assert row.email == "sam@example.com"
    assert row.topic == "pricing_billing"
    assert row.ip_hash is None or "127.0.0.1" not in row.ip_hash
    await public.aclose()


async def test_turnstile_and_a_known_topic_are_required(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    public = anonymous(rig)
    with monkeypatch.context() as patch:
        patch.setattr(rig["app"].state.auth.turnstile, "verify", _refuse)
        refused = await public.post(f"{API}/public/contact", json=MESSAGE)
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "TURNSTILE_FAILED"
    with monkeypatch.context() as patch:
        patch.setattr(rig["app"].state.auth.turnstile, "verify", _accept)
        bad_topic = await public.post(f"{API}/public/contact", json={**MESSAGE, "topic": "spam"})
    assert bad_topic.status_code == 422
    await public.aclose()


async def test_repeated_messages_from_one_connection_are_limited(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    public = anonymous(rig)
    monkeypatch.setattr(rig["app"].state.auth.turnstile, "verify", _accept)
    for _ in range(5):
        assert (await public.post(f"{API}/public/contact", json=MESSAGE)).status_code == 201
    limited = await public.post(f"{API}/public/contact", json=MESSAGE)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    await public.aclose()
