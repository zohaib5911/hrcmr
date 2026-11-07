"""T15.4: the SOC search and match API over the reference tables, with Claude on and off (plan 8.17).

The embedder and Claude are fakes, so nothing downloads and nothing leaves the test. The SOC sample
and the saved GOV.UK rules pages are loaded into a fresh database and the rules are published, so
the engine has real rows to check against.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

from app.ai.redaction import find_restricted
from app.modules.soc import router as soc_router
from app.modules.soc.importer import load_soc_source
from app.modules.soc.source import load_source
from app.modules.soc_rules.importer import import_rules_source, publish_rules_version
from app.modules.soc_rules.loader import NoRulesVersionError
from app.modules.soc_rules.source import PAGE_KINDS, RulesSource, load_rules_source
from tests.db.api_support import fake_claude
from tests.db.support import DatabaseUnderTest, engine_for, temporary_database
from tests.db.test_employee_documents import rig as rig

API = "/api/v1/soc"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "soc"
RULES = Path(__file__).resolve().parents[3] / "data" / "raw" / "rules"
SAMPLE_INDEX = "soc2020-coding-index-sample.xlsx"
SAMPLE_GROUPS = "soc2020-unit-groups-sample.xlsx"


def _fake_embed(texts: Sequence[str]) -> list[list[float]]:
    # Never a zero vector (cosine distance needs a length); deterministic for a given text.
    return [[1.0 + float((len(text) + dim) % 7) for dim in range(384)] for text in texts]


def _rules_source() -> RulesSource:
    return load_rules_source(
        {
            kind: (
                RULES / f"appendix-{kind}-2026-10-29.html",
                RULES / f"appendix-{kind}-2026-10-29.json",
            )
            for kind in PAGE_KINDS
        }
    )


async def _load_sample(url: str) -> None:
    """The SOC reference tables. The rig's user clean-up does not touch them."""
    source = load_source(FIXTURES / SAMPLE_INDEX, FIXTURES / SAMPLE_GROUPS)
    engine = engine_for(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with AsyncSession(engine) as db:
            await load_soc_source(db, source, _fake_embed)
            await db.commit()
    finally:
        await engine.dispose()


async def _publish_rules(url: str) -> None:
    engine = engine_for(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with AsyncSession(engine) as db:
            result = await import_rules_source(db, _rules_source())
            assert result.version_id is not None
            await publish_rules_version(db, result.version_id)
            await db.commit()
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def database(stack: None) -> Iterator[DatabaseUnderTest]:
    """A fresh database with the SOC sample loaded, for this module only."""
    with temporary_database() as db:
        asyncio.run(_load_sample(db.owner_url))
        yield db


@pytest.fixture(autouse=True)
async def ready(rig: dict[str, Any], database: DatabaseUnderTest) -> None:
    """The fake embedder, and the published rules. The rig's clean-up truncates the rules (their
    rows refer to users), so they are published again after it for every test."""
    rig["app"].state.soc_embedder = _fake_embed
    await _publish_rules(database.owner_url)


def _match_body(
    title: str = "Adviser, sales",
    description: str = "Serve customers on the shop floor.",
) -> dict[str, Any]:
    return {
        "job_title": title,
        "job_description": description,
        "check": {
            "weekly_hours": "37.5",
            "offered_salary": "30000.00",
            "salary_per": "year",
            "work_nation": "England",
            "cos_assignment_date": "2026-11-01",
            "applicant": {"situation": "outside_uk"},
        },
    }


def _code(response: Any) -> str:
    return str(response.json()["error"]["code"])


async def test_search_puts_the_exact_title_first_and_returns_at_most_ten(
    rig: dict[str, Any],
) -> None:
    user = await rig["person"]("recruiter", rig["a"])
    found = await user.get(API + "/search", params={"q": "Adviser, sales"})
    assert found.status_code == 200, found.text
    results = found.json()["results"]
    assert results[0] == {
        "code": "7111",
        "title": "Sales and retail assistants",
        "matched_title": "Adviser, sales",
    }
    codes = [hit["code"] for hit in results]
    assert len(results) <= 10
    assert len(codes) == len(set(codes))


async def test_a_title_under_two_letters_finds_nothing(rig: dict[str, Any]) -> None:
    user = await rig["person"]("recruiter", rig["a"])
    found = await user.get(API + "/search", params={"q": "a"})
    assert found.status_code == 200
    assert found.json() == {"results": []}


async def test_the_search_is_refused_with_503_when_the_model_cannot_run(
    rig: dict[str, Any],
) -> None:
    def broken(texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("the weights are missing")

    rig["app"].state.soc_embedder = broken
    user = await rig["person"]("recruiter", rig["a"])
    found = await user.get(API + "/search", params={"q": "Adviser, sales"})
    assert found.status_code == 503
    assert _code(found) == "SOC_SEARCH_UNAVAILABLE"


async def test_the_read_only_auditor_can_search_but_not_match(rig: dict[str, Any]) -> None:
    auditor = await rig["person"]("read_only_auditor", rig["a"])
    found = await auditor.get(API + "/search", params={"q": "Adviser, sales"})
    assert found.status_code == 200
    refused = await auditor.post(API + "/match", json=_match_body())
    assert refused.status_code == 403


async def test_without_ai_the_search_order_is_kept_and_the_top_codes_are_checked(
    rig: dict[str, Any],
) -> None:
    user = await rig["person"]("recruiter", rig["a"])
    made = await user.post(API + "/match", json=_match_body())
    assert made.status_code == 200, made.text
    body = made.json()
    assert body["ai_ranked"] is False
    assert "Not AI-ranked" in body["notice"]
    assert body["confidence"] is None
    assert body["low_confidence"] is False
    assert body["candidates"][0]["code"] == "7111"
    assert all(c["confidence"] is None and c["reason"] is None for c in body["candidates"])
    assert [c["rank"] for c in body["candidates"]] == list(range(1, len(body["candidates"]) + 1))
    # The rules engine runs on the top three codes, in the same order.
    assert len(body["checks"]) == 3
    assert [check["soc_code"] for check in body["checks"]] == [
        c["code"] for c in body["candidates"][:3]
    ]
    assert all(check["rules_version_id"] for check in body["checks"])


@pytest.mark.parametrize(("confidence", "flagged"), [(45, True), (85, False)])
async def test_claudes_ranking_is_used_and_low_confidence_is_flagged(
    rig: dict[str, Any], confidence: int, flagged: bool
) -> None:
    sent = fake_claude(
        rig["app"],
        reply=json.dumps(
            {
                "ranking": [
                    {
                        "code": "5111",
                        "confidence": confidence,
                        "matched_duties": ["serve customers"],
                        "reason": "Farming, not retail.",
                    },
                    {"code": "7111", "confidence": 10, "matched_duties": [], "reason": "Lower."},
                ]
            }
        ),
    )
    user = await rig["person"]("recruiter", rig["a"])
    made = await user.post(API + "/match", json=_match_body())
    assert made.status_code == 200, made.text
    body = made.json()
    assert body["ai_ranked"] is True
    assert body["notice"] is None
    assert [c["code"] for c in body["candidates"]] == ["5111", "7111"]
    assert body["candidates"][0]["confidence"] == confidence
    assert body["candidates"][0]["matched_duties"] == ["serve customers"]
    assert body["confidence"] == confidence
    assert body["low_confidence"] is flagged
    assert body["checks"][0]["soc_code"] == "5111"
    # Only the job text and the candidates' official text are sent, with no personal data.
    assert len(sent) == 1
    assert find_restricted(sent[0]) == []
    assert "Adviser, sales" in sent[0]


async def test_an_ai_error_falls_back_to_the_search_order(rig: dict[str, Any]) -> None:
    fake_claude(rig["app"], status=500)
    user = await rig["person"]("recruiter", rig["a"])
    made = await user.post(API + "/match", json=_match_body())
    assert made.status_code == 200, made.text
    body = made.json()
    assert body["ai_ranked"] is False
    assert "Not AI-ranked" in body["notice"]
    assert body["candidates"][0]["code"] == "7111"


@pytest.mark.parametrize(
    "reply",
    ["Sorry, I cannot rank these.", '{"ranking": [{"code": "9999", "confidence": 90}]}'],
)
async def test_an_unreadable_or_unknown_reply_falls_back(rig: dict[str, Any], reply: str) -> None:
    fake_claude(rig["app"], reply=reply)
    user = await rig["person"]("recruiter", rig["a"])
    made = await user.post(API + "/match", json=_match_body())
    assert made.status_code == 200, made.text
    body = made.json()
    assert body["ai_ranked"] is False
    assert "could not be read" in body["notice"]
    assert body["candidates"][0]["code"] == "7111"


async def test_an_email_in_the_job_is_redacted_before_it_is_sent(rig: dict[str, Any]) -> None:
    reply = {
        "ranking": [{"code": "7111", "confidence": 90, "matched_duties": [], "reason": "Fits."}]
    }
    sent = fake_claude(rig["app"], reply=json.dumps(reply))
    user = await rig["person"]("recruiter", rig["a"])
    made = await user.post(
        API + "/match", json=_match_body(description="Email hr@example.com to apply.")
    )
    assert made.status_code == 200, made.text
    assert made.json()["ai_ranked"] is True
    assert len(sent) == 1
    assert "hr@example.com" not in sent[0]
    assert find_restricted(sent[0]) == []


async def test_a_job_title_with_no_letters_or_numbers_is_refused(rig: dict[str, Any]) -> None:
    user = await rig["person"]("recruiter", rig["a"])
    refused = await user.post(API + "/match", json=_match_body(title="!!"))
    assert refused.status_code == 422
    assert _code(refused) == "INVALID_JOB_TITLE"


async def test_no_published_rules_is_a_clear_409(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unpublished(db: Any, version_id: Any = None) -> None:
        raise NoRulesVersionError("no version")

    monkeypatch.setattr(soc_router, "load_rules_data", unpublished)
    user = await rig["person"]("recruiter", rig["a"])
    refused = await user.post(API + "/match", json=_match_body())
    assert refused.status_code == 409
    assert _code(refused) == "RULES_NOT_PUBLISHED"
