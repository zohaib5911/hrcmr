from pathlib import Path

import httpx
import pytest

from app.modules.register.ingest import allowed, discover, download, normalise, parse

FIXTURES = Path(__file__).parent / "fixtures" / "register"


def test_discovery_and_parse() -> None:
    assert discover((FIXTURES / "publication.html").read_text()).endswith("/register.csv")
    rows = parse((FIXTURES / "first.csv").read_bytes())
    assert len(rows) == 3
    assert normalise("  EXAMPLE   Care, Ltd. ") == "example care ltd"


@pytest.mark.parametrize(
    "url",
    [
        "http://www.gov.uk/a.csv",
        "https://evil.gov.uk/a.csv",
        "https://www.gov.uk.evil.test/a.csv",
        "https://user@www.gov.uk/a.csv",
        "https://assets.publishing.service.gov.uk:444/a.csv",
    ],
)
def test_reject_source(url: str) -> None:
    with pytest.raises(ValueError, match="allowlisted"):
        allowed(url)


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"wrong,headers\na,b",
        b"Organisation Name,Town/City,County,Type & Rating,Route\n",
        b"Organisation Name,Town/City,County,Type & Rating,Route\na,b,c",
    ],
)
def test_invalid_csv(content: bytes) -> None:
    with pytest.raises(ValueError, match=r"columns|Empty|Malformed"):
        parse(content)


async def test_redirect_is_checked_before_request() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://evil.test/register.csv"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="allowlisted"):
            await download(client, "https://www.gov.uk/fixture", 100)
    assert len(requests) == 1


async def test_response_size_limit() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"too big"))
    ) as client:
        with pytest.raises(ValueError, match="too large"):
            await download(client, "https://www.gov.uk/fixture", 2)


@pytest.mark.parametrize(
    ("stamp", "expected"),
    [
        ("2026-07-13T08:00:00+00:00", "outside_schedule"),
        ("2026-07-13T09:00:00+00:00", "no_owner_engine"),
        ("2026-11-12T10:00:00+00:00", "no_owner_engine"),
        ("2026-11-14T10:00:00+00:00", "outside_schedule"),
        ("2026-07-13T15:00:00+00:00", "no_owner_engine"),
    ],
)
async def test_uk_schedule(stamp: str, expected: str) -> None:
    from datetime import datetime

    from app.jobs.register import register_ingest

    assert await register_ingest({"now": datetime.fromisoformat(stamp)}) == expected
