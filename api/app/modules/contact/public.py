"""The public contact form (plan 8.20, T18.1). No login.

A message is stored for platform admins to read (T17.4). Every POST checks a rate limit and
Turnstile.
The reply carries nothing but ``received``; the address is kept only as a hash of the connection.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr, StringConstraints

from app.core.errors import AppError
from app.core.rate_limit import RateLimiter, hashed
from app.core.schemas import RequestModel
from app.db.ids import uuid7
from app.db.session import GlobalDb  # noqa: TC001  (FastAPI reads the dependency at runtime)
from app.modules.auth.deps import client_ip
from app.modules.contact.models import ContactMessage

router = APIRouter(prefix="/public", tags=["contact"])

CONTACT_PER_CONNECTION = ("public.contact", 5, 3600)  # messages, per hour, per connection

Topic = Literal[
    "sponsor_compliance",
    "simple_hr",
    "pricing_billing",
    "setup_help",
    "partnership",
    "other",
    "data_protection",
]


class ContactFormIn(RequestModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    company: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
        | None
    ) = None
    email: EmailStr
    topic: Topic
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    turnstile_token: Annotated[str, StringConstraints(min_length=1, max_length=2048)]


class ContactFormOut(BaseModel):
    received: bool


@router.post("/contact", response_model=ContactFormOut, status_code=201)
async def send_message(body: ContactFormIn, db: GlobalDb, request: Request) -> ContactFormOut:
    ip = client_ip(request)
    auth = request.app.state.auth
    name, limit, window = CONTACT_PER_CONNECTION
    result = await RateLimiter(auth.redis).hit(
        name, ip or "unknown", limit=limit, window_seconds=window
    )
    if not result.allowed:
        raise AppError(
            "RATE_LIMITED",
            "Too many messages from this connection. Try again later.",
            status_code=429,
        )
    if not await auth.turnstile.verify(body.turnstile_token, ip):
        raise AppError(
            "TURNSTILE_FAILED",
            "We could not confirm you are a person. Try again.",
            status_code=400,
            field="turnstile_token",
        )
    db.add(
        ContactMessage(
            id=uuid7(),
            name=body.name,
            company=body.company,
            email=str(body.email).strip().lower(),
            topic=body.topic,
            message=body.message,
            ip_hash=hashed(ip) if ip else None,
        )
    )
    await db.commit()
    return ContactFormOut(received=True)
