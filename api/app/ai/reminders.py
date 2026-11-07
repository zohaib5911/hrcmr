"""AI wording for a reminder message (T14.5, plan 8.12): the text the employee reads, never a name.

Claude sees only the document type (for example "Visa") and the threshold in days. It never sees
the employee's name, a date, a reference number or the reminder history. The answer is a draft:
HR reads and edits it in the review drawer before anything is sent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ai.redaction import find_restricted
from app.ai.service import ai_ready, generate
from app.core.errors import AppError

if TYPE_CHECKING:
    from fastapi import Request

    from app.modules.rbac.deps import Access

REMINDER_TASK = (
    "Task: write the message HR sends to one employee to say that a document on their record needs "
    "review. The data gives the document type and the number of days within which it expires. "
    "Write two or three short sentences in plain British English, warm and professional. Say that "
    "the document needs review, that they should check their record and speak with HR about the "
    "evidence or next steps. Do not name the employee, do not give any date, and do not mention "
    "any other document or personal detail. Return the message text only."
)
MAX_MESSAGE_LENGTH = 2000  # the same limit as the reminder message field


async def reminder_wording(
    request: Request, access: Access, *, document: str, threshold_days: int
) -> str | None:
    """Claude's suggested message, or None when AI is off, unavailable, failed or unsafe."""
    if not await ai_ready(request, access):
        return None
    try:
        reply = await generate(
            request,
            access,
            feature="reminder",
            task=REMINDER_TASK,
            instruction="Write the reminder message described in the data.",
            data={"document": document, "days_to_expiry_within": threshold_days},
            max_tokens=300,
        )
    except AppError:
        return None
    reply = reply.strip()
    if not reply or len(reply) > MAX_MESSAGE_LENGTH or find_restricted(reply):
        return None
    return reply
