"""Fixed-window rate limits in Redis (plan.md 4.2).

Keys are hashed, so no e-mail address or IP address sits in Redis in the clear. If Redis cannot be
reached the call raises, and the request fails: letting people through unchecked when the limiter is
down would turn an outage into a way around the limits.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int  # seconds until the window resets


def hashed(*parts: str) -> str:
    return hashlib.sha256("\x00".join(parts).lower().encode("utf-8")).hexdigest()[:32]


class RateLimiter:
    def __init__(self, redis: Redis, *, prefix: str = "rl") -> None:
        self._redis = redis
        self._prefix = prefix

    async def hit(
        self, name: str, subject: str, *, limit: int, window_seconds: int
    ) -> RateLimitResult:
        """Count one attempt by ``subject`` (an IP, an e-mail) against the ``name`` limit."""
        key = f"{self._prefix}:{name}:{hashed(subject)}"
        # Create the key with its expiry first, so a crash between the two calls can never leave a
        # counter that never resets.
        await self._redis.set(key, 0, ex=window_seconds, nx=True)
        count = int(await self._redis.incr(key))
        ttl = await self._redis.ttl(key)
        retry_after = ttl if ttl > 0 else window_seconds
        return RateLimitResult(count <= limit, max(limit - count, 0), retry_after)

    async def reset(self, name: str, subject: str) -> None:
        await self._redis.delete(f"{self._prefix}:{name}:{hashed(subject)}")


# The limits from plan.md 4.2, named so a router asks for one by name.
LOGIN_PER_IP = ("login-ip", 5, 60)
LOGIN_PER_ACCOUNT = ("login-account", 10, 3600)
PASSWORD_RESET_PER_EMAIL = ("reset-email", 3, 3600)
SIGNUP_PER_IP = ("signup-ip", 5, 3600)
PUBLIC_PER_IP = ("public-ip", 60, 60)
AI_PER_USER = ("ai-user", 30, 3600)
