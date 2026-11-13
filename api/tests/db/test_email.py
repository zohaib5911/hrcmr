"""T2.8: every template renders and takes only what it declares; a message is saved encrypted before
it is sent, wiped once it is sent or given up on, retried when the service is down; and all of them
really reach a mail server (Mailpit)."""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from arq import Retry
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.integrations.email import Message, SmtpTransport, TransportError
from app.jobs.email import deliver_email
from app.modules.email.outbox import BACKOFF, MAX_ATTEMPTS, EmailDelivery, OutboxMailer
from app.modules.email.templates import TEMPLATES, TemplateError, render
from seed.email_samples import SAMPLES, send_samples
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import build_settings

MAILPIT_API = os.environ.get("TEST_MAILPIT_API", "http://localhost:8025")
SMTP_HOST = os.environ.get("TEST_SMTP_HOST", "localhost")
SMTP_PORT = int(os.environ.get("TEST_SMTP_PORT", "1025"))
SETTINGS = build_settings(brand_name="Acme HR", support_email="help@example.com")


@pytest.fixture(autouse=True)
def _keys() -> Any:
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    yield
    set_keyring(None)


# --- the templates (no database) --------------------------------------------------------------------


def test_every_template_has_a_sample_and_renders_in_html_and_text() -> None:
    assert set(SAMPLES) == set(TEMPLATES)
    for name, data in SAMPLES.items():
        rendered = render(name, data, SETTINGS)
        for part in (rendered.subject, rendered.html, rendered.plain):
            assert not re.search(r"\{[a-z_]+\}", part), name  # no placeholder left unfilled
        assert f'src="{SETTINGS.web_origin}/brand/logo-email.png"' in rendered.html
        assert 'width="269" height="64" alt="Acme HR"' in rendered.html
        assert "logo-email.png" not in rendered.plain
        assert "Acme HR" in rendered.html
        assert "Acme HR" in rendered.plain
        for field, value in data.items():
            if field.endswith("link"):
                assert value in rendered.html, name
                assert value in rendered.plain, name
        assert "help@example.com" in rendered.html


def test_values_are_escaped_in_html_and_a_template_takes_only_what_it_declares() -> None:
    data = {**SAMPLES["verify_email"], "first_name": "<script>alert(1)</script>"}
    rendered = render("verify_email", data, SETTINGS)
    assert "<script>alert(1)</script>" not in rendered.html
    assert "&lt;script&gt;" in rendered.html
    assert "<script>alert(1)</script>" in rendered.plain

    with pytest.raises(TemplateError, match="not accepted"):
        render("verify_email", {**SAMPLES["verify_email"], "ni_number": "AB123456C"}, SETTINGS)
    with pytest.raises(TemplateError, match="missing"):
        render("verify_email", {"first_name": "Amira"}, SETTINGS)
    with pytest.raises(TemplateError, match="single line"):
        render("verify_email", {**SAMPLES["verify_email"], "first_name": "A\nBcc: x"}, SETTINGS)
    with pytest.raises(TemplateError, match="web address"):
        render("verify_email", {**SAMPLES["verify_email"], "link": "javascript:alert(1)"}, SETTINGS)
    with pytest.raises(TemplateError, match="no e-mail template"):
        render("nope", {}, SETTINGS)


# --- the outbox -----------------------------------------------------------------------------------------


class FakeTransport:
    def __init__(self, *failures: TransportError) -> None:
        self.failures = list(failures)
        self.sent: list[Message] = []

    async def send(self, message: Message) -> str | None:
        if self.failures:
            raise self.failures.pop(0)
        self.sent.append(message)
        return "provider-1"


class FakeQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[str, ...], str]] = []
        self.broken = False

    async def enqueue(self, function: str, *args: str, job_id: str) -> None:
        if self.broken:
            raise ConnectionError("redis is down")
        self.jobs.append((function, args, job_id))


@pytest.fixture
async def engine(database: DatabaseUnderTest) -> AsyncIterator[AsyncEngine]:
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.begin() as c:
        await c.execute(text("truncate reminders, email_outbox"))
    await owner.dispose()
    engine = engine_for(database.app_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


async def _row(database: DatabaseUnderTest, outbox_id: uuid.UUID) -> Any:
    owner = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with owner.connect() as c:
            result = await c.execute(
                text("select * from email_outbox where id = :i"), {"i": outbox_id}
            )
            return result.mappings().one()
    finally:
        await owner.dispose()


async def test_a_message_is_saved_encrypted_then_sent_and_wiped(
    database: DatabaseUnderTest, engine: AsyncEngine
) -> None:
    queue, transport = FakeQueue(), FakeTransport()
    mailer = OutboxMailer(engine, queue)
    link = f"http://localhost:3000/verify-email?token={uuid.uuid4().hex}"
    await mailer.send_template(
        to="amira@example.com", template="verify_email", data={"first_name": "Amira", "link": link}
    )
    ((function, (outbox_id,), job_id),) = queue.jobs
    assert function == "deliver_email"
    assert job_id == f"email-{outbox_id}-0"

    waiting = await _row(database, uuid.UUID(outbox_id))
    assert waiting["status"] == "pending"
    assert link not in waiting["payload"]  # the one-time link is not readable in the table
    assert "Amira" not in waiting["payload"]

    delivery = EmailDelivery(engine, transport, SETTINGS)
    assert (await delivery.deliver(uuid.UUID(outbox_id))).status == "sent"
    (message,) = transport.sent
    assert message.to == "amira@example.com"
    assert message.subject == "Confirm your email address"
    assert link in message.html
    assert message.idempotency_key == f"outbox-{outbox_id}"
    assert message.sender.startswith("Acme HR <")

    done = await _row(database, uuid.UUID(outbox_id))
    assert (done["status"], done["payload"], done["provider_id"]) == ("sent", None, "provider-1")
    # Asking again finds nothing waiting, so it cannot be sent twice.
    assert (await delivery.deliver(uuid.UUID(outbox_id))).status == "skipped"
    assert len(transport.sent) == 1


async def test_a_queue_that_is_down_does_not_fail_the_request_and_the_sweep_finds_it(
    database: DatabaseUnderTest, engine: AsyncEngine
) -> None:
    queue = FakeQueue()
    queue.broken = True
    await OutboxMailer(engine, queue).send_template(
        to="amira@example.com", template="password_changed", data={"first_name": "Amira"}
    )
    queue.broken = False
    delivery = EmailDelivery(engine, FakeTransport(), SETTINGS)
    assert await delivery.sweep(queue) == 1
    ((_, (outbox_id,), job_id),) = queue.jobs
    assert job_id == f"email-{outbox_id}-0"
    await delivery.deliver(uuid.UUID(outbox_id))
    assert await delivery.sweep(queue) == 0  # sent: nothing left to pick up


async def test_a_service_that_is_down_is_retried_later_and_given_up_on_after_five_tries(
    database: DatabaseUnderTest, engine: AsyncEngine
) -> None:
    transport = FakeTransport(*[TransportError("down", retry=True)] * MAX_ATTEMPTS)
    delivery = EmailDelivery(engine, transport, SETTINGS)
    row = await OutboxMailer(engine).save(
        to="amira@example.com", template="password_changed", data={"first_name": "Amira"}
    )
    start = datetime.now(UTC)
    for attempt in range(1, MAX_ATTEMPTS):
        outcome = await delivery.deliver(row.id, now=start)
        assert (outcome.status, outcome.retry_in) == ("retry", BACKOFF[min(attempt, 4) - 1])
        stored = await _row(database, row.id)
        assert stored["attempts"] == attempt
        assert stored["status"] == "pending"
        assert stored["next_attempt_at"] >= start + BACKOFF[min(attempt, 4) - 1] - timedelta(
            seconds=1
        )
        assert stored["payload"] is not None
    assert (await delivery.deliver(row.id, now=start)).status == "failed"
    final = await _row(database, row.id)
    assert (final["status"], final["payload"], final["attempts"]) == ("failed", None, MAX_ATTEMPTS)
    assert final["last_error"] == "down"


async def test_a_message_the_service_refuses_is_not_retried_and_the_job_asks_to_retry_a_blip(
    database: DatabaseUnderTest, engine: AsyncEngine
) -> None:
    refused = EmailDelivery(
        engine, FakeTransport(TransportError("bad address", retry=False)), SETTINGS
    )
    mailer = OutboxMailer(engine)
    row = await mailer.save(
        to="x@example.com", template="password_changed", data={"first_name": "X"}
    )
    assert (await refused.deliver(row.id)).status == "failed"
    assert (await _row(database, row.id))["payload"] is None

    row = await mailer.save(
        to="x@example.com", template="password_changed", data={"first_name": "X"}
    )
    blip = EmailDelivery(engine, FakeTransport(TransportError("blip", retry=True)), SETTINGS)
    with pytest.raises(Retry):
        await deliver_email({"email": blip}, str(row.id))
    assert await deliver_email({"email": blip}, str(row.id)) == "sent"


# --- a real mail server ------------------------------------------------------------------------------------


async def test_every_template_reaches_mailpit(engine: AsyncEngine) -> None:
    async with httpx.AsyncClient(base_url=MAILPIT_API) as mailpit:
        await mailpit.delete("/api/v1/messages")
        settings = build_settings(brand_name="Acme HR", support_email="help@example.com")
        sent = await send_samples(engine, SmtpTransport(SMTP_HOST, SMTP_PORT), settings)
        assert sent == len(TEMPLATES)
        listing = (await mailpit.get("/api/v1/messages", params={"limit": 50})).json()
        assert listing["total"] == len(TEMPLATES)
        subjects = {m["Subject"] for m in listing["messages"]}
        assert "Confirm your email address" in subjects
        assert "Your leave request was approved" in subjects
        first = (await mailpit.get(f"/api/v1/message/{listing['messages'][0]['ID']}")).json()
        assert first["HTML"]
        assert first["Text"]
        assert first["To"][0]["Address"] == "amira@example.com"
