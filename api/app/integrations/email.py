"""The e-mail interface the rest of the API uses (plan.md T2.8 builds the real sender).

Code that needs to send an e-mail calls ``mailer.send_template``. It names a template and the
values to fill in, never ready-made text, so the wording lives in one place. Links in the data are
built by the caller from ``WEB_ORIGIN``; they carry one-time tokens, so nothing may log ``data``.
"""

from __future__ import annotations

from typing import Protocol

from app.core.logging import get_logger

logger = get_logger("app.email")


class Mailer(Protocol):
    async def send_template(self, *, to: str, template: str, data: dict[str, str]) -> None: ...


class LoggingMailer:
    """Sends nothing. Records that a message of this kind was asked for (never to whom, or what it
    held), so a developer can see the flow ran. Replaced by the real sender in T2.8."""

    async def send_template(self, *, to: str, template: str, data: dict[str, str]) -> None:
        logger.info("email_not_sent", template=template)
