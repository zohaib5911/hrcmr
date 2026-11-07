"""T11.4 stage rules, checked for every pair of the eight stages (no database needed)."""

from __future__ import annotations

import itertools

import pytest

from app.core.errors import AppError
from app.modules.recruitment.applications import LABELS, STAGES, check_move, stage_error

ENDING = {"rejected", "withdrawn"}
ORDER = ["applied", "shortlisted", "interview", "offer_letter", "offer_accepted", "hired"]


def expected(current: str, target: str) -> str | None:
    """The rule written out separately from the implementation, for every pair."""
    if current in ENDING:
        return f"This application is {LABELS[current].lower()}. It cannot change."
    if current == "hired":
        return "This candidate is already an employee. The application cannot change."
    if target == "hired":
        return "Use Convert to employee to hire this candidate."
    if target == current or target in ENDING:
        return None
    if ORDER.index(target) <= ORDER.index(current):
        return None
    if ORDER.index(target) == ORDER.index(current) + 1:
        return None
    nxt = ORDER[ORDER.index(current) + 1]
    return f"The next step from {LABELS[current]} is {LABELS[nxt]}"


@pytest.mark.parametrize(("current", "target"), list(itertools.product(STAGES, STAGES)))
def test_every_pair_of_stages(current: str, target: str) -> None:
    assert stage_error(current, target) == expected(current, target)


def test_a_skipped_step_gives_the_exact_message() -> None:
    with pytest.raises(AppError) as refused:
        check_move("applied", "offer_letter")
    assert refused.value.message == "The next step from Job Applied is Shortlisted"
    assert refused.value.status_code == 422
