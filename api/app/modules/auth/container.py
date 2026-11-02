"""The pieces the auth endpoints share, built once at start-up and kept on ``app.state``."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.modules.auth.notifier import MailNotifier
from app.modules.auth.service import AuthNotifier, AuthService
from app.modules.auth.sessions import SessionStore

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from app.core.config import Settings
    from app.integrations.email import Mailer
    from app.integrations.turnstile import Turnstile


@dataclass(frozen=True)
class AuthContainer:
    settings: Settings
    redis: Redis
    sessions: SessionStore
    auth: AuthService
    mailer: Mailer
    turnstile: Turnstile


def build_container(
    settings: Settings,
    redis: Redis,
    mailer: Mailer,
    turnstile: Turnstile,
    notifier: AuthNotifier | None = None,
) -> AuthContainer:
    sessions = SessionStore(redis)
    # A key for the recovery-code hashes, derived from the session secret so there is one less
    # secret to manage. It is never stored and never leaves this process.
    recovery_key = hmac.new(
        settings.session_secret.get_secret_value().encode(), b"recovery-codes", hashlib.sha256
    ).digest()
    auth = AuthService(
        redis=redis,
        sessions=sessions,
        recovery_key=recovery_key,
        notifier=notifier or MailNotifier(mailer, settings),
    )
    return AuthContainer(
        settings=settings,
        redis=redis,
        sessions=sessions,
        auth=auth,
        mailer=mailer,
        turnstile=turnstile,
    )
