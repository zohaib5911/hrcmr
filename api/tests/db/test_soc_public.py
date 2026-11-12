"""T15.8: the free public checker. A visitor who is not signed in gets a title search, a code and the
salary table, each limited per connection, with Turnstile on the salary check. It reads only the
shared reference tables and the published rules, so no company's data is reachable from it."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from typing import Any

import pytest

from app.modules.soc import router as soc_router
from tests.db.support import DatabaseUnderTest, temporary_database
from tests.db.test_careers import anonymous
from tests.db.test_employee_documents import rig as rig
from tests.db.test_soc_match import _fake_embed, _load_sample, _publish_rules

API = "/api/v1"
CHECK = {
    "soc_code": "7111",
    "weekly_hours": "37.5",
    "offered_salary": "30000.00",
    "salary_per": "year",
    "work_nation": "England",
    "cos_assignment_date": "2026-11-01",
    "turnstile_token": "test-token",
}
SALARY_TABLE_FIELDS = {
    "soc_code",
    "title",
    "rules_version_name",
    "rules_effective_from",
    "eligibility",
    "going_rate",
    "options",
    "verdict",
    "dependants_allowed",
    "notes",
}


@pytest.fixture(scope="module")
def database(stack: None) -> Iterator[DatabaseUnderTest]:
    with temporary_database() as db:
        asyncio.run(_load_sample(db.owner_url))
        yield db


@pytest.fixture(autouse=True)
async def ready(
    rig: dict[str, Any], database: DatabaseUnderTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Match the sample's vectors without downloading weights or starting ONNX worker threads.
    # Guard the factory too: losing this injection must fail instead of hanging on model setup.
    def unexpected_model_load() -> None:
        pytest.fail("SOC database tests must use the deterministic sample embedder")

    monkeypatch.setattr(soc_router, "fastembed_embedder", unexpected_model_load)
    rig["app"].state.soc_embedder = _fake_embed
    await _publish_rules(database.owner_url)


async def _accept(token: str | None, remote_ip: str | None = None) -> bool:
    return True


async def test_the_search_and_a_code_return_only_the_reference_fields(rig: dict[str, Any]) -> None:
    public = anonymous(rig)
    found = await public.get(f"{API}/public/soc/search", params={"q": "Adviser, sales"})
    assert found.status_code == 200, found.text
    assert found.json()["results"][0] == {"code": "7111", "title": "Sales and retail assistants"}
    code = await public.get(f"{API}/public/soc/7111")
    assert code.status_code == 200, code.text
    assert set(code.json()) == {"code", "title", "description", "tasks", "typical_titles"}
    await public.aclose()


async def test_the_salary_check_needs_turnstile_and_returns_only_the_table(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    public = anonymous(rig)

    async def refusing(token: str | None, remote_ip: str | None = None) -> bool:
        return False

    with monkeypatch.context() as patch:
        patch.setattr(rig["app"].state.auth.turnstile, "verify", refusing)
        refused = await public.post(f"{API}/public/soc/salary-check", json=CHECK)
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "TURNSTILE_FAILED"

    with monkeypatch.context() as patch:
        patch.setattr(rig["app"].state.auth.turnstile, "verify", _accept)
        made = await public.post(f"{API}/public/soc/salary-check", json=CHECK)
    assert made.status_code == 200, made.text
    body = made.json()
    assert set(body) == SALARY_TABLE_FIELDS
    assert body["soc_code"] == "7111"
    await public.aclose()


async def test_repeated_salary_checks_from_one_connection_are_limited(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    public = anonymous(rig)
    with monkeypatch.context() as patch:
        patch.setattr(rig["app"].state.auth.turnstile, "verify", _accept)
        for _ in range(10):
            made = await public.post(f"{API}/public/soc/salary-check", json=CHECK)
            assert made.status_code == 200, made.text
        limited = await public.post(f"{API}/public/soc/salary-check", json=CHECK)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    await public.aclose()


async def test_nothing_from_a_company_is_reachable_without_signing_in(rig: dict[str, Any]) -> None:
    public = anonymous(rig)
    for path in ("/soc/checks", "/soc/search?q=adviser", "/platform/rules"):
        response = await public.get(f"{API}{path}")
        assert response.status_code == 401, path
        assert "company" not in json.dumps(response.json()).lower(), path
    await public.aclose()
