from __future__ import annotations

import json
import logging
from typing import Any

import pytest
import structlog

from app.core.logging import configure_logging, get_logger, redact_sensitive_keys, scrub_text
from tests.support import build_settings


def lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    out = capsys.readouterr().out
    return [json.loads(line) for line in out.splitlines()]  # every line must be valid JSON


@pytest.fixture(autouse=True)
def _logging(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    structlog.contextvars.clear_contextvars()
    capsys.readouterr()


def test_each_line_is_one_json_object_with_standard_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    get_logger("test").info("something_happened", count=3)
    (record,) = lines(capsys)
    assert record["event"] == "something_happened"
    assert record["count"] == 3
    assert record["level"] == "info"
    assert record["logger"] == "test"
    assert record["timestamp"].endswith("Z")


def test_request_id_context_is_added(capsys: pytest.CaptureFixture[str]) -> None:
    structlog.contextvars.bind_contextvars(request_id="req-12345678")
    get_logger("test").info("hello")
    (record,) = lines(capsys)
    assert record["request_id"] == "req-12345678"


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "new_password",
        "Authorization",
        "authorization_header",
        "session_token",
        "csrf_token",
        "client_secret",
        "Cookie",
        "set-cookie",
        "ni_number",
        "passport_number",
        "sort_code",
        "account_number",
        "share_code",
        "cos_number",
        "salary",
        "annual_salary",
        "bank_details",
        "bank",
    ],
)
def test_sensitive_keys_are_dropped(key: str, capsys: pytest.CaptureFixture[str]) -> None:
    get_logger("test").info("event", **{key: "VALUE-THAT-MUST-NOT-APPEAR", "safe": "kept"})
    (record,) = lines(capsys)
    assert key not in record
    assert record["safe"] == "kept"
    assert "VALUE-THAT-MUST-NOT-APPEAR" not in json.dumps(record)


def test_sensitive_keys_are_dropped_at_any_depth(capsys: pytest.CaptureFixture[str]) -> None:
    get_logger("test").info(
        "event",
        user={"name": "Sam", "ni_number": "AB123456C", "bank": {"sort_code": "00-00-00"}},
        rows=[{"token": "t", "keep": 1}, ({"salary": 1, "keep": 2},)],
    )
    (record,) = lines(capsys)
    assert record["user"] == {"name": "Sam"}
    assert record["rows"] == [{"keep": 1}, [{"keep": 2}]]


def test_redaction_processor_ignores_case() -> None:
    result = redact_sensitive_keys(None, "info", {"PASSWORD": "x", "Ok": 1})
    assert result == {"Ok": 1}


def test_passwords_in_urls_are_masked_in_messages_and_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    get_logger("test").info(
        "cannot reach postgresql+asyncpg://app_user:hunter2@db.internal:5432/app",
        target="redis://:s3cr3t@cache:6379/0",
    )
    (record,) = lines(capsys)
    text = json.dumps(record)
    assert "hunter2" not in text
    assert "s3cr3t" not in text
    assert "postgresql+asyncpg://app_user:***@db.internal:5432/app" in record["event"]
    assert record["target"] == "redis://:***@cache:6379/0"


def test_passwords_in_tracebacks_are_masked(capsys: pytest.CaptureFixture[str]) -> None:
    log = get_logger("test")
    try:
        raise ConnectionError("connect failed for postgresql://owner:PASSWORD-IN-TRACEBACK@db/app")
    except ConnectionError:
        log.exception("db_error")
    (record,) = lines(capsys)
    assert "PASSWORD-IN-TRACEBACK" not in json.dumps(record)
    assert "owner:***@db/app" in record["exception"]


def test_third_party_stdlib_logs_go_through_the_same_pipeline(
    capsys: pytest.CaptureFixture[str],
) -> None:
    logging.getLogger("sqlalchemy.engine").warning(
        "pool connect %s", "postgresql://u:LIBRARY-LEAK@h/db"
    )
    (record,) = lines(capsys)
    assert record["event"] == "pool connect postgresql://u:***@h/db"
    assert record["level"] == "warning"
    assert "LIBRARY-LEAK" not in json.dumps(record)


def test_logging_the_settings_object_shows_no_secret(capsys: pytest.CaptureFixture[str]) -> None:
    # Built at run time: a literal `session_secret="..."` would (rightly) trip gitleaks.
    sentinels = {
        name: f"SENTINEL-{name}-9f3c1a7e" for name in ("session_secret", "anthropic_api_key")
    }
    settings = build_settings(**sentinels)
    get_logger("test").info("config_loaded", settings=settings)
    out = capsys.readouterr().out
    assert "SENTINEL" not in out
    assert "config_loaded" in out


def test_scrub_text_leaves_ordinary_text_alone() -> None:
    assert scrub_text("https://example.com/path?a=1") == "https://example.com/path?a=1"
    assert scrub_text("user:name@example.com") == "user:name@example.com"


def test_uvicorn_access_log_is_silenced() -> None:
    access = logging.getLogger("uvicorn.access")
    assert access.propagate is False
    # pytest attaches its own capture handlers to non-propagating loggers; ignore those.
    ours = [h for h in access.handlers if not type(h).__module__.startswith("_pytest")]
    assert ours == []


def test_http_client_libraries_do_not_log_urls_at_info(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """httpx logs every request URL at INFO, and a URL can carry a token in its query string."""
    logging.getLogger("httpx").info(
        'HTTP Request: GET https://example.test/x?token=URL-TOKEN "200"'
    )
    logging.getLogger("httpcore.http11").debug("send_request_headers")
    assert capsys.readouterr().out == ""
    logging.getLogger("httpx").warning("slow response")
    (record,) = lines(capsys)
    assert record["event"] == "slow response"
