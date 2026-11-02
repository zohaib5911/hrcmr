"""The lockout and new-device e-mails (T2.3): what is sent, to whom, and that a failure is harmless."""

from __future__ import annotations

import uuid

from app.modules.auth.notifier import MailNotifier, describe_device, describe_wait
from app.modules.email.templates import render
from tests.support import build_settings

SETTINGS = build_settings()


class Recorder:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[tuple[str, str, dict[str, str]]] = []
        self.fail = fail

    async def send_template(self, *, to: str, template: str, data: dict[str, str]) -> None:
        if self.fail:
            raise RuntimeError("mail service down")
        self.sent.append((to, template, data))


async def test_a_lockout_sends_the_lockout_email_that_renders() -> None:
    mail = Recorder()
    await MailNotifier(mail, SETTINGS).account_locked(uuid.uuid4(), "a@example.com", "Amira", 900)
    [(to, template, data)] = mail.sent
    assert (to, template, data["minutes"]) == ("a@example.com", "account_locked", "15 minutes")
    assert data["link"].endswith("/forgot-password")
    render(template, data, SETTINGS)


async def test_a_new_device_sends_the_alert_with_a_readable_device_and_no_address() -> None:
    mail = Recorder()
    agent = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
    await MailNotifier(mail, SETTINGS).new_device_login(
        uuid.uuid4(), "a@example.com", "Amira", "203.0.113.9", agent
    )
    [(_, template, data)] = mail.sent
    assert template == "login_alert"
    assert data["device"] == "Firefox on Linux"
    assert "203.0.113.9" not in "".join(data.values())
    render(template, data, SETTINGS)


async def test_a_mail_failure_never_breaks_the_sign_in() -> None:
    notifier = MailNotifier(Recorder(fail=True), SETTINGS)
    await notifier.account_locked(uuid.uuid4(), "a@example.com", "Amira", 60)
    await notifier.new_device_login(uuid.uuid4(), "a@example.com", "Amira", None, None)


def test_descriptions() -> None:
    assert describe_device(None) == "a device we do not recognise"
    assert describe_wait(60) == "1 minute"
    assert describe_wait(7200) == "2 hours"
