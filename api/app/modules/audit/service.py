"""Writing to the audit trail (plan.md 4.5).

``record`` adds an event to the SAME database transaction as the change it describes, so the two
succeed or fail together: there is never a change without its event, or an event for a change that
was rolled back. Sensitive values are masked before they are stored, so the trail itself never
becomes a place where secrets or personal identifiers pile up.
"""

from __future__ import annotations

import re
import uuid  # noqa: TC003
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from fastapi.encoders import jsonable_encoder

from app.modules.audit.models import AuditEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

MASKED = "[masked]"

# A field is masked if its lower-cased name is one of these, or matches one of the patterns. The
# patterns catch the next field someone adds (``backup_secret``) without anyone listing it.
_SENSITIVE_NAMES = frozenset(
    {
        "ni_number",
        "national_insurance_number",
        "passport_number",
        "sort_code",
        "account_number",
        "bank_account_number",
        "iban",
        "visa_reference",
        "evisa_reference",
        "share_code",
        "cos_number",
        "date_of_birth",
        "salary",
        "recovery_codes",
    }
)
_SENSITIVE_FRAGMENTS = re.compile(r"password|passwd|secret|token|api_key|private_key|_hash$|^hash$")

ACTOR_TYPES = ("user", "platform_admin", "system")


def is_sensitive(field: str) -> bool:
    name = field.lower()
    return name in _SENSITIVE_NAMES or bool(_SENSITIVE_FRAGMENTS.search(name))


def mask(value: Any) -> Any:
    """A copy of ``value`` safe to store: JSON-friendly, with every sensitive field hidden."""
    # Money and other decimals become text, never floats, so nothing is rounded in the record.
    encoded = jsonable_encoder(value, custom_encoder={Decimal: str})
    return _mask(encoded)


def _mask(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: MASKED if is_sensitive(str(key)) and item is not None else _mask(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_mask(item) for item in value]
    return value


def changed_fields(before: dict[str, Any] | None, after: dict[str, Any] | None) -> list[str]:
    """The names of fields that differ, compared on the real values (before masking)."""
    before, after = before or {}, after or {}
    return sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))


@dataclass(frozen=True)
class AuditContext:
    """Who did it, and from where. Built once per request."""

    company_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    actor_type: str = "user"
    ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    impersonation_session_id: uuid.UUID | None = None


async def record(
    db: AsyncSession,
    context: AuditContext,
    action: str,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
    summary: str | None = None,
) -> AuditEvent:
    """Add an event to ``db``'s current transaction. Nothing is committed here."""
    if context.actor_type not in ACTOR_TYPES:
        raise ValueError(f"unknown actor type {context.actor_type!r}")
    if summary is None:
        names = changed_fields(before, after)
        summary = f"Changed: {', '.join(names)}" if names and before is not None else None
    event = AuditEvent(
        company_id=context.company_id,
        actor_user_id=context.actor_user_id,
        actor_type=context.actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        before=None if before is None else mask(before),
        after=None if after is None else mask(after),
        reason=reason,
        ip=context.ip,
        user_agent=(context.user_agent or "")[:400] or None,
        request_id=context.request_id,
        impersonation_session_id=context.impersonation_session_id,
    )
    db.add(event)
    await db.flush()
    return event
