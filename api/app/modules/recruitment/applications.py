"""Application stages: the forward-one-step rule and backward moves (plan 8.11).

Pure rules, with no database access, so every pair of stages can be tested directly.
"""

from __future__ import annotations

from typing import Final

from app.core.errors import AppError

STAGE_ORDER: Final[tuple[str, ...]] = (
    "applied",
    "shortlisted",
    "interview",
    "offer_letter",
    "offer_accepted",
    "hired",
)
ENDING: Final[frozenset[str]] = frozenset({"rejected", "withdrawn"})
STAGES: Final[tuple[str, ...]] = (*STAGE_ORDER, "rejected", "withdrawn")
LABELS: Final[dict[str, str]] = {
    "applied": "Job Applied",
    "shortlisted": "Shortlisted",
    "interview": "Interview",
    "offer_letter": "Offer Letter",
    "offer_accepted": "Offer Accepted",
    "hired": "Hired",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}


def stage_error(current: str, target: str) -> str | None:
    """Why a move from ``current`` to ``target`` is refused, or None when it is allowed.

    Forward moves go one step at a time. Backward moves are allowed. Rejected and withdrawn end an
    application, so nothing moves out of them. Moving to the stage it is already at is a no-op.
    """
    if current in ENDING:
        return f"This application is {LABELS[current].lower()}. It cannot change."
    if target == current or target in ENDING:
        return None
    current_at = STAGE_ORDER.index(current)
    target_at = STAGE_ORDER.index(target)
    if target_at <= current_at:
        return None
    if target_at == current_at + 1:
        return None
    next_step = STAGE_ORDER[current_at + 1]
    return f"The next step from {LABELS[current]} is {LABELS[next_step]}"


def check_move(current: str, target: str) -> None:
    message = stage_error(current, target)
    if message is not None:
        raise AppError("APPLICATION_STAGE_MOVE", message, status_code=422, field="stage")
