"""Sending e-mail (plan.md T2.8).

Code that needs to send an e-mail calls ``mailer.send_template``. It names a template and the
values to fill in, never ready-made text, so the wording lives in one place. Links in the data are
built by the caller from ``WEB_ORIGIN``; they carry one-time tokens, so nothing may log ``data``.

Behind that call is an outbox (``app.modules.email``): the message is saved, then a background job
hands it to a *transport*, which is the only code here that talks to a mail service. In deployment
that is Resend; on a developer's machine it is Mailpit (SMTP), which catches everything.
"""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from typing import TYPE_CHECKING, Protocol

import aiosmtplib
import httpx

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.config import Settings

logger = get_logger("app.email")

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 15.0


class Mailer(Protocol):
    async def send_template(self, *, to: str, template: str, data: dict[str, str]) -> None: ...


class LoggingMailer:
    """Sends nothing. Records that a message of this kind was asked for (never to whom, or what it
    held), so a developer can see the flow ran. Used when no mail service is configured."""

    async def send_template(self, *, to: str, template: str, data: dict[str, str]) -> None:
        logger.info("email_not_sent", template=template)


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    html: str
    plain: str  # the plain-text version
    sender: str
    reply_to: str | None = None
    # Sending the same key twice must not send two e-mails (Resend honours it for 24 hours).
    idempotency_key: str | None = None


class TransportError(Exception):
    """The mail service did not take the message. ``retry`` says whether trying again can help.

    The text never includes the address, the body or the service's reply, only a short reason."""

    def __init__(self, reason: str, *, retry: bool) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retry = retry


class Transport(Protocol):
    async def send(self, message: Message) -> str | None:
        """Hand the message over. Returns the service's id for it, if it gives one."""
        ...


class ResendTransport:
    def __init__(self, api_key: str, *, client: httpx.AsyncClient | None = None) -> None:
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client

    async def send(self, message: Message) -> str | None:
        body: dict[str, object] = {
            "from": message.sender,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
            "text": message.plain,
        }
        if message.reply_to:
            body["reply_to"] = message.reply_to
        headers = dict(self._headers)
        if message.idempotency_key:
            headers["Idempotency-Key"] = message.idempotency_key
        try:
            if self._client is not None:
                response = await self._client.post(RESEND_URL, json=body, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                    response = await client.post(RESEND_URL, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise TransportError("The mail service could not be reached.", retry=True) from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise TransportError(f"The mail service answered {response.status_code}.", retry=True)
        if response.status_code >= 400:
            # A rejected address, domain or key: asking again would be refused the same way.
            raise TransportError(
                f"The mail service refused it ({response.status_code}).", retry=False
            )
        sent_id = response.json().get("id")
        return str(sent_id) if sent_id else None


class SmtpTransport:
    """Plain SMTP without login or encryption: for Mailpit on a developer's own machine."""

    def __init__(self, host: str, port: int) -> None:
        self._host, self._port = host, port

    async def send(self, message: Message) -> str | None:
        mail = EmailMessage()
        mail["From"], mail["To"], mail["Subject"] = message.sender, message.to, message.subject
        if message.reply_to:
            mail["Reply-To"] = message.reply_to
        mail.set_content(message.plain)
        mail.add_alternative(message.html, subtype="html")
        try:
            await aiosmtplib.send(
                mail, hostname=self._host, port=self._port, timeout=TIMEOUT_SECONDS
            )
        except aiosmtplib.SMTPResponseException as exc:
            raise TransportError(
                f"The mail server answered {exc.code}.", retry=not 500 <= exc.code < 600
            ) from exc
        except (aiosmtplib.SMTPException, OSError) as exc:
            raise TransportError("The mail server could not be reached.", retry=True) from exc
        return None


def transport_from_settings(settings: Settings) -> Transport | None:
    """Resend when it has a key, else Mailpit when an SMTP host is set, else nothing (not sent)."""
    if settings.resend_api_key is not None:
        return ResendTransport(settings.resend_api_key.get_secret_value())
    if settings.smtp_host:
        return SmtpTransport(settings.smtp_host, settings.smtp_port)
    return None
