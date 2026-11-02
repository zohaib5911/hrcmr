"""One example of every e-mail, for looking at in Mailpit (``python -m app.cli email-samples``).

Development only: this file lives in ``seed/``, which the production image does not contain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.email.outbox import EmailDelivery, OutboxMailer

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.core.config import Settings
    from app.integrations.email import Transport

SAMPLE_BASE = "http://localhost:3000"

SAMPLES: dict[str, dict[str, str]] = {
    "verify_email": {"first_name": "Amira", "link": f"{SAMPLE_BASE}/verify-email?token=example"},
    "reset_password": {
        "first_name": "Amira",
        "link": f"{SAMPLE_BASE}/reset-password?token=example",
    },
    "password_changed": {"first_name": "Amira"},
    "account_exists": {
        "first_name": "Amira",
        "sign_in_link": f"{SAMPLE_BASE}/login",
        "reset_link": f"{SAMPLE_BASE}/forgot-password",
    },
    "invite": {
        "first_name": "Tom",
        "inviter_name": "Amira Hassan",
        "company_name": "Harbourside Care Ltd",
        "role_label": "HR Admin",
        "link": f"{SAMPLE_BASE}/accept-invite?token=example",
    },
    "login_alert": {
        "first_name": "Amira",
        "when": "2 November 2026 at 09:42 UTC",
        "device": "Firefox on Linux",
        "link": f"{SAMPLE_BASE}/forgot-password",
    },
    "account_locked": {
        "first_name": "Amira",
        "minutes": "15 minutes",
        "link": f"{SAMPLE_BASE}/forgot-password",
    },
    "notifications_digest": {
        "first_name": "Amira",
        "count": "4 notifications",
        "link": f"{SAMPLE_BASE}/notifications",
    },
    "reminder_nudge": {
        "first_name": "Tom",
        "sender_name": "Amira Hassan",
        "link": f"{SAMPLE_BASE}/my-documents",
    },
    "leave_decision": {
        "first_name": "Tom",
        "decision": "approved",
        "dates": "14 to 18 December 2026",
        "link": f"{SAMPLE_BASE}/leave",
    },
    "policy_request": {
        "first_name": "Tom",
        "policy_title": "Data protection policy",
        "link": f"{SAMPLE_BASE}/policies",
    },
    "deletion_code": {"first_name": "Amira", "code": "482 915", "minutes": "15"},
}


async def send_samples(
    engine: AsyncEngine, transport: Transport, settings: Settings, *, to: str = "amira@example.com"
) -> int:
    """Send each sample through the outbox and the real transport; returns how many were sent."""
    mailer, delivery = OutboxMailer(engine), EmailDelivery(engine, transport, settings)
    sent = 0
    for name, data in SAMPLES.items():
        row = await mailer.save(to=to, template=name, data=data)
        sent += (await delivery.deliver(row.id)).status == "sent"
    return sent
