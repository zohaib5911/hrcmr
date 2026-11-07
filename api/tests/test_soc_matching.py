"""T15.4, no database: title folding, rank fusion, the strict reply from Claude, the confidence flag,
and the search order that is kept when the AI is off. The AI and the database are covered in
tests/db/test_soc_match.py."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.soc.ranking import LOW_CONFIDENCE, NOT_AI_RANKED, is_low, parse_ranking, rank
from app.modules.soc.retrieval import CANDIDATES, Candidate, fuse, normalise_title

GOOD_REPLY = (
    '{"ranking": [{"code": "7111", "confidence": 82, "matched_duties": ["sell goods"], '
    '"reason": "fits"}, {"code": "5111", "confidence": 20, "reason": "farming"}]}'
)


def candidate(code: str, title: str = "A group") -> Candidate:
    return Candidate(
        code=code,
        title=title,
        description="Describes the group.",
        tasks=("Serves customers.",),
        typical_titles=(),
        matched_title=title,
    )


def test_titles_are_folded_for_comparison() -> None:
    assert normalise_title("  Nurse,   Registered ") == "nurse registered"
    # Full-width letters have one normal form, so this is "nurse" (named to keep the source ASCII).
    full_width_nurse = "\N{FULLWIDTH LATIN CAPITAL LETTER N}urse"
    assert normalise_title(full_width_nurse) == "nurse"
    assert normalise_title("!!!") == ""


def test_a_code_that_several_searches_agree_on_comes_first() -> None:
    lexical = [("2111", "chemist"), ("5111", "farmer")]
    by_vector = [("5111", "agriculturist"), ("9111", "farm worker")]
    fused = fuse([lexical, by_vector])
    assert [code for code, _ in fused] == ["5111", "2111", "9111"]
    # The title kept is the one from the first search that found the code.
    assert dict(fused)["5111"] == "farmer"


def test_a_code_is_listed_once_and_the_limit_holds() -> None:
    leg = [(f"{n:04d}", "title") for n in range(1000, 1025)]
    fused = fuse([leg, leg])
    assert len(fused) == CANDIDATES
    assert len({code for code, _ in fused}) == CANDIDATES


def test_a_repeat_inside_one_search_counts_once_and_does_not_move_the_rank() -> None:
    fused = fuse([[("1111", "a"), ("1111", "a again"), ("2222", "b")]])
    assert fused == [("1111", "a"), ("2222", "b")]


def test_ties_break_on_the_code_so_the_order_is_stable() -> None:
    fused = fuse([[("3000", "x")], [("2000", "y")]])
    assert fused == [("2000", "y"), ("3000", "x")]


def test_a_valid_reply_keeps_claudes_order() -> None:
    items = parse_ranking(GOOD_REPLY, {"7111", "5111", "2111"})
    assert items is not None
    assert [item.code for item in items] == ["7111", "5111"]
    assert items[0].confidence == 82
    assert items[1].matched_duties == []


def test_a_fenced_reply_is_accepted() -> None:
    items = parse_ranking(f"```json\n{GOOD_REPLY}\n```", {"7111", "5111"})
    assert items is not None
    assert items[0].code == "7111"


@pytest.mark.parametrize(
    "reply",
    [
        "not json at all",
        '{"ranking": []}',
        '{"rank": [{"code": "7111", "confidence": 50}]}',
        '{"ranking": [{"code": "9999", "confidence": 50}]}',  # not one of the candidates
        '{"ranking": [{"code": "7111", "confidence": 50}, {"code": "7111", "confidence": 40}]}',
        '{"ranking": [{"code": "7111", "confidence": 101}]}',  # confidence is 0 to 100
        '{"ranking": [{"code": "7111"}]}',  # confidence is required
    ],
)
def test_anything_else_is_not_trusted(reply: str) -> None:
    assert parse_ranking(reply, {"7111", "5111"}) is None


def test_confidence_under_sixty_is_flagged() -> None:
    assert LOW_CONFIDENCE == 60
    assert is_low(59) is True
    assert is_low(60) is False
    assert is_low(None) is False


async def test_without_ai_the_search_order_is_kept_and_flagged() -> None:
    request: Any = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(anthropic=None)))
    outcome = await rank(
        request,
        None,
        job_title="Adviser, sales",
        job_description="",
        candidates=[candidate("7111"), candidate("5111")],
    )
    assert outcome.ai_ranked is False
    assert outcome.notice == NOT_AI_RANKED
    assert outcome.low_confidence is False
    assert [item.candidate.code for item in outcome.items] == ["7111", "5111"]
    assert all(item.confidence is None and item.reason is None for item in outcome.items)


async def test_no_candidates_means_nothing_to_rank() -> None:
    request: Any = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(anthropic=None)))
    outcome = await rank(request, None, job_title="zzz", job_description="", candidates=[])
    assert outcome.items == []
    assert outcome.ai_ranked is False
