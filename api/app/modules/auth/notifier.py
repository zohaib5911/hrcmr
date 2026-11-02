"""E-mails about what happened to an account: it was locked, or signed in to from a new device."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from app.core.config import Settings
    from app.integrations.email import Mailer

logger = get_logger("app.auth.notifier")


def describe_device(user_agent: str | None) -> str:
    """Words such as "Firefox on Linux"; the browser's raw text never goes into an e-mail."""
    agent = user_agent or ""
    browser = next(
        (
            name
            for marker, name in (
                ("Edg/", "Edge"),
                ("OPR/", "Opera"),
                ("Firefox/", "Firefox"),
                ("Chrome/", "Chrome"),
                ("Safari/", "Safari"),
            )
            if marker in agent
        ),
        None,
    )
    system = next(
        (
            name
            for marker, name in (
                ("Windows", "Windows"),
                ("Android", "Android"),
                ("iPhone", "iOS"),
                ("iPad", "iPadOS"),
                ("Mac OS X", "macOS"),
                ("Linux", "Linux"),
            )
            if marker in agent
        ),
        None,
    )
    if browser and system:
        return f"{browser} on {system}"
    return browser or system or "a device we do not recognise"


def describe_wait(seconds: int) -> str:
    if seconds < 3600:
        minutes = max(round(seconds / 60), 1)
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = round(seconds / 3600)
    return f"{hours} hour{'s' if hours != 1 else ''}"


class MailNotifier:
    def __init__(self, mailer: Mailer, settings: Settings) -> None:
        self._mailer = mailer
        self._web = str(settings.web_origin)

    async def account_locked(
        self, user_id: uuid.UUID, email: str, first_name: str, retry_after: int
    ) -> None:
        await self._send(
            email,
            "account_locked",
            {
                "first_name": first_name,
                "minutes": describe_wait(retry_after),
                "link": f"{self._web}/forgot-password",
            },
        )

    async def new_device_login(
        self,
        user_id: uuid.UUID,
        email: str,
        first_name: str,
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        await self._send(
            email,
            "login_alert",
            {
                "first_name": first_name,
                "when": datetime.now(UTC).strftime("%-d %B %Y at %H:%M UTC"),
                "device": describe_device(user_agent),
                "link": f"{self._web}/forgot-password",
            },
        )

    async def _send(self, to: str, template: str, data: dict[str, str]) -> None:
        try:
            await self._mailer.send_template(to=to, template=template, data=data)
        except Exception:
            # A notice that cannot be sent must not fail the sign-in it is about.
            logger.warning("auth_notice_failed", template=template)
