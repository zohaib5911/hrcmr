"""Saving e-mails, handing them to the mail service, and trying again when it is down (T2.8).

    caller -> OutboxMailer.send_template -> row in email_outbox -> job -> transport (Resend/Mailpit)

Delivery is at-least-once with one safety net on each side: the row is locked while it is sent (so
two workers never send the same message), and Resend is given an idempotency key (so a retry after
a lost reply does not send twice).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from sqlalchemy import select

from app.core.crypto import DecryptionError, decrypt, encrypt
from app.core.logging import get_logger
from app.db.session import GlobalSession
from app.integrations.email import Message, TransportError
from app.modules.email.models import EmailOutbox
from app.modules.email.templates import TemplateError, check, render

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.core.config import Settings
    from app.integrations.email import Transport

logger = get_logger("app.email")

PAYLOAD_CONTEXT = "email_outbox.payload"
MAX_ATTEMPTS = 5
# The wait after the 1st, 2nd, 3rd... failed attempt; the last value repeats.
BACKOFF = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30), timedelta(hours=2))
SWEEP_LIMIT = 200


class JobQueue(Protocol):
    async def enqueue(self, function: str, *args: str, job_id: str) -> None: ...


@dataclass(frozen=True)
class Outcome:
    status: str  # "sent", "retry", "failed" or "skipped" (nothing waiting under that id)
    retry_in: timedelta | None = None


def sender_of(settings: Settings) -> str:
    address = settings.email_from or f"no-reply@{settings.domain}"
    return address if "<" in address else f"{settings.brand_name} <{address}>"


class OutboxMailer:
    """The ``Mailer`` the API uses: save the message, then ask the worker to send it."""

    def __init__(self, engine: AsyncEngine, queue: JobQueue | None = None) -> None:
        self._engine = engine
        self._queue = queue

    async def save(self, *, to: str, template: str, data: dict[str, str]) -> EmailOutbox:
        check(template, data)  # a wrong call fails here, in the code that made it
        row = EmailOutbox(
            to_address=to,
            template=template,
            payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
        )
        async with GlobalSession(self._engine) as db:
            db.add(row)
            await db.commit()
        logger.info("email_queued", template=template)
        return row

    async def send_template(self, *, to: str, template: str, data: dict[str, str]) -> None:
        row = await self.save(to=to, template=template, data=data)
        if self._queue is not None:
            try:
                await self._queue.enqueue("deliver_email", str(row.id), job_id=f"email-{row.id}-0")
            except Exception as exc:  # the sweep picks the row up; the caller's request goes on
                logger.warning("email_enqueue_failed", kind=type(exc).__name__)


class EmailDelivery:
    def __init__(self, engine: AsyncEngine, transport: Transport, settings: Settings) -> None:
        self._engine = engine
        self._transport = transport
        self._settings = settings

    async def deliver(self, outbox_id: uuid.UUID, *, now: datetime | None = None) -> Outcome:
        """Send one waiting message. Never raises for a message that cannot be sent: it records
        why, and says whether to try again."""
        moment = now or datetime.now(UTC)
        async with GlobalSession(self._engine) as db:
            row = (
                await db.execute(
                    select(EmailOutbox)
                    .where(EmailOutbox.id == outbox_id, EmailOutbox.status == "pending")
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if row is None:
                return Outcome("skipped")
            try:
                message = self._message(row)
            except (DecryptionError, TemplateError, ValueError, TypeError):
                self._give_up(row, "The message could not be built.")
                await db.commit()
                logger.warning("email_failed", template=row.template, reason="unbuildable")
                return Outcome("failed")
            row.attempts += 1
            try:
                row.provider_id = await self._transport.send(message)
            except TransportError as exc:
                row.last_error = exc.reason[:200]
                if not exc.retry or row.attempts >= MAX_ATTEMPTS:
                    self._give_up(row, exc.reason)
                    await db.commit()
                    logger.warning("email_failed", template=row.template, attempts=row.attempts)
                    return Outcome("failed")
                wait = BACKOFF[min(row.attempts, len(BACKOFF)) - 1]
                row.next_attempt_at = moment + wait
                await db.commit()
                logger.info("email_will_retry", template=row.template, attempts=row.attempts)
                return Outcome("retry", wait)
            row.status, row.sent_at, row.payload, row.last_error = "sent", moment, None, None
            await db.commit()
            logger.info("email_sent", template=row.template, attempts=row.attempts)
            return Outcome("sent")

    def _message(self, row: EmailOutbox) -> Message:
        if row.payload is None:
            raise ValueError("no payload")
        data = json.loads(decrypt(row.payload, context=PAYLOAD_CONTEXT))
        rendered = render(row.template, data, self._settings)
        return Message(
            to=row.to_address,
            subject=rendered.subject,
            html=rendered.html,
            plain=rendered.plain,
            sender=sender_of(self._settings),
            reply_to=self._settings.email_reply_to or self._settings.support_email,
            idempotency_key=f"outbox-{row.id}",
        )

    @staticmethod
    def _give_up(row: EmailOutbox, reason: str) -> None:
        row.status, row.payload, row.last_error = "failed", None, reason[:200]

    async def sweep(self, queue: JobQueue, *, now: datetime | None = None) -> int:
        """Ask for every waiting message that is due again (a restart or a lost job left it)."""
        moment = now or datetime.now(UTC)
        async with GlobalSession(self._engine) as db:
            waiting = (
                await db.execute(
                    select(EmailOutbox.id, EmailOutbox.attempts)
                    .where(EmailOutbox.status == "pending", EmailOutbox.next_attempt_at <= moment)
                    .order_by(EmailOutbox.next_attempt_at)
                    .limit(SWEEP_LIMIT)
                )
            ).all()
        for outbox_id, attempts in waiting:
            await queue.enqueue(
                "deliver_email", str(outbox_id), job_id=f"email-{outbox_id}-{attempts}"
            )
        return len(waiting)
