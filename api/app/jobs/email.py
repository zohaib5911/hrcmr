"""Background jobs for e-mail. The worker (T2.9) registers these and supplies ``ctx["email"]``."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from arq import Retry, func

from app.jobs.queue import ArqQueue
from app.modules.email.outbox import MAX_ATTEMPTS

if TYPE_CHECKING:
    from arq.worker import Function

    from app.modules.email.outbox import EmailDelivery


async def deliver_email(ctx: dict[str, Any], outbox_id: str) -> str:
    """Send one message from the outbox. A temporary failure asks the worker to try again later."""
    delivery: EmailDelivery = ctx["email"]
    outcome = await delivery.deliver(uuid.UUID(outbox_id))
    if outcome.retry_in is not None:
        raise Retry(defer=outcome.retry_in)
    return outcome.status


async def sweep_email_outbox(ctx: dict[str, Any]) -> int:
    """Pick up messages that are waiting but have no job (the API restarted, Redis lost one)."""
    delivery: EmailDelivery = ctx["email"]
    return await delivery.sweep(ArqQueue(ctx["redis"]))


# Our own retry schedule decides when to try again, so the worker allows one more run than that.
EMAIL_FUNCTIONS: list[Function] = [
    func(deliver_email, max_tries=MAX_ATTEMPTS + 1),
    func(sweep_email_outbox, max_tries=1),
]
