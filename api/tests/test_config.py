from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import AppEnv, Settings
from tests.support import build_settings

# Every field that is a secret, with a unique sentinel so any leak is easy to spot.
SECRET_FIELDS = [
    "database_url",
    "database_url_owner",
    "database_app_user_password",
    "redis_url",
    "session_secret",
    "field_encryption_keys",
    "blind_index_key",
    "r2_access_key_id",
    "r2_secret_access_key",
    "r2_backup_access_key_id",
    "r2_backup_secret_access_key",
    "resend_api_key",
    "anthropic_api_key",
    "stripe_secret_key",
    "stripe_webhook_secret",
    "turnstile_secret_key",
    "companies_house_api_key",
    "sentry_dsn_api",
]
# Fields whose names look secret but are public by design (deployment-requirements.txt, [PUBLIC]).
PUBLIC_DESPITE_NAME = {"backup_age_public_key", "session_cookie_name"}
SECRET_LOOKING = re.compile(r"secret|password|key|token|dsn|^database_url|^redis_url")

DEPLOYED_EXTRAS: dict[str, Any] = {
    "database_url_owner": "postgresql+asyncpg://owner@db/app",
    "r2_account_id": "acct",
    "r2_endpoint": "https://acct.eu.r2.cloudflarestorage.com",
    "r2_access_key_id": "r2-id",
    "r2_secret_access_key": "r2-secret",
    "r2_bucket_files": "files",
    "resend_api_key": "resend",
    "email_from": "Brand <no-reply@example.com>",
    "email_reply_to": "support@example.com",
    "support_email": "support@example.com",
    "anthropic_api_key": "anthropic",
    "stripe_secret_key": "stripe",
    "stripe_webhook_secret": "webhook",
    "stripe_price_annual": "price_annual",
    "stripe_price_ten_year": "price_ten",
    "turnstile_secret_key": "turnstile",
}


def sentinel_settings() -> tuple[Settings, dict[str, str]]:
    sentinels = {name: f"SENTINEL-{name}-9f3c1a7e" for name in SECRET_FIELDS}
    return build_settings(**sentinels), sentinels


def test_every_secret_looking_field_is_a_secretstr() -> None:
    """Guards future additions: a new `*_key` or `*_secret` setting must not be a plain str."""
    plain: list[str] = []
    for name, field in Settings.model_fields.items():
        if name in PUBLIC_DESPITE_NAME or not SECRET_LOOKING.search(name):
            continue
        annotation = field.annotation
        candidates = {annotation, *get_args(annotation)}
        if SecretStr not in candidates:
            plain.append(name)
    assert plain == []


def test_secret_field_list_is_complete() -> None:
    declared = {
        name
        for name, field in Settings.model_fields.items()
        if SecretStr in {field.annotation, *get_args(field.annotation)}
    }
    assert declared == set(SECRET_FIELDS)


def test_repr_str_and_dumps_never_show_secret_values() -> None:
    settings, sentinels = sentinel_settings()
    rendered = [
        repr(settings),
        str(settings),
        settings.model_dump_json(),
        json.dumps(settings.model_dump(mode="json")),
        repr(settings.model_dump()),
        f"{settings!r} {settings!s} {settings}",
    ]
    for text in rendered:
        for name, sentinel in sentinels.items():
            assert sentinel not in text, f"{name} leaked"
    assert "**********" in repr(settings)


def test_secret_value_is_available_only_through_get_secret_value() -> None:
    settings, sentinels = sentinel_settings()
    assert settings.session_secret.get_secret_value() == sentinels["session_secret"]


def test_validation_errors_do_not_echo_secret_values() -> None:
    sentinels = {name: f"SENTINEL-{name}-9f3c1a7e" for name in SECRET_FIELDS}
    with pytest.raises(ValidationError) as caught:
        build_settings(tz="Not/AZone", web_origin="ftp://nope", **sentinels)
    message = str(caught.value)
    assert "tz" in message
    assert not any(sentinel in message for sentinel in sentinels.values())


def test_required_values_are_enforced() -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None)
    missing = {err["loc"][0] for err in caught.value.errors()}
    assert missing == {
        "app_env",
        "domain",
        "web_origin",
        "admin_origin",
        "api_origin",
        "database_url",
        "redis_url",
        "session_secret",
        "field_encryption_keys",
        "blind_index_key",
    }


def test_reads_the_environment_and_treats_empty_values_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = build_settings()
    for name in ("domain", "web_origin", "admin_origin", "api_origin"):
        monkeypatch.setenv(name.upper(), str(getattr(base, name)))
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    for name in ("session_secret", "field_encryption_keys", "blind_index_key"):
        monkeypatch.setenv(name.upper(), getattr(base, name).get_secret_value())
    # As copied straight from .env.example: "NAME=" with nothing after it.
    monkeypatch.setenv("CLAMAV_PORT", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    settings = Settings(_env_file=None)

    assert settings.app_env is AppEnv.LOCAL
    assert settings.clamav_port == 3310
    assert settings.anthropic_api_key is None


def test_env_file_is_read_and_real_environment_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = build_settings()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_ENV=local",
                "DOMAIN=from-file",
                f"WEB_ORIGIN={base.web_origin}",
                f"ADMIN_ORIGIN={base.admin_origin}",
                f"API_ORIGIN={base.api_origin}",
                "DATABASE_URL=postgresql+asyncpg://u@h/db",
                "REDIS_URL=redis://h:6379/0",
                f"SESSION_SECRET={base.session_secret.get_secret_value()}",
                f"FIELD_ENCRYPTION_KEYS={base.field_encryption_keys.get_secret_value()}",
                f"BLIND_INDEX_KEY={base.blind_index_key.get_secret_value()}",
            ]
        )
    )
    assert Settings(_env_file=env_file).domain == "from-file"
    monkeypatch.setenv("DOMAIN", "from-environment")
    assert Settings(_env_file=env_file).domain == "from-environment"


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("https://Example.com", "https://example.com"),
        ("https://example.com/", "https://example.com"),
        ("http://localhost:3000/", "http://localhost:3000"),
        ("https://admin.staging.example.com", "https://admin.staging.example.com"),
    ],
)
def test_origins_are_normalised(given: str, expected: str) -> None:
    assert build_settings(web_origin=given).web_origin == expected


@pytest.mark.parametrize(
    "bad",
    [
        "example.com",
        "ftp://example.com",
        "https://example.com/app",
        "https://example.com?x=1",
        "https://user:pw@example.com",
    ],
)
def test_bad_origins_are_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        build_settings(web_origin=bad)


def test_admin_ip_allowlist_is_comma_separated() -> None:
    assert build_settings(admin_ip_allowlist="203.0.113.7, 10.0.0.0/8 ,").admin_ip_allowlist == [
        "203.0.113.7",
        "10.0.0.0/8",
    ]
    assert build_settings().admin_ip_allowlist == []


def test_timezone_must_be_valid() -> None:
    assert build_settings().tz == "Europe/London"
    with pytest.raises(ValidationError):
        build_settings(tz="Mars/Olympus")


def test_defaults_match_the_plan() -> None:
    settings = build_settings()
    assert settings.anthropic_model_main == "claude-sonnet-5-5"
    assert settings.anthropic_model_fast == "claude-haiku-5-5"
    assert settings.session_cookie_name == "brand_session"
    assert settings.field_encryption_active_kid == "k1"
    assert settings.hibp_enabled is True
    assert settings.ai_features_enabled is True


@pytest.mark.parametrize("env", ["staging", "production"])
def test_deployed_environments_fail_closed_naming_variables_not_values(env: str) -> None:
    sentinel = "SENTINEL-deployed-9f3c1a7e"
    with pytest.raises(ValidationError) as caught:
        build_settings(app_env=env, session_secret=sentinel)
    message = str(caught.value)
    for variable in (
        "DATABASE_URL_OWNER",
        "STRIPE_SECRET_KEY",
        "RESEND_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        assert variable in message
    assert sentinel not in message


@pytest.mark.parametrize("env", ["staging", "production"])
def test_deployed_environments_start_when_everything_is_present(env: str) -> None:
    assert build_settings(app_env=env, **DEPLOYED_EXTRAS).app_env.is_deployed


def test_one_missing_deployed_variable_is_named() -> None:
    extras = {**DEPLOYED_EXTRAS, "stripe_webhook_secret": None}
    with pytest.raises(ValidationError, match="STRIPE_WEBHOOK_SECRET"):
        build_settings(app_env="production", **extras)


def test_local_and_test_do_not_need_third_party_accounts() -> None:
    for env in ("local", "test"):
        settings = build_settings(app_env=env)
        assert not settings.app_env.is_deployed
        assert settings.docs_enabled is True


def test_docs_are_off_when_deployed() -> None:
    assert build_settings(app_env="production", **DEPLOYED_EXTRAS).docs_enabled is False
    assert build_settings(app_env="staging", **DEPLOYED_EXTRAS).docs_enabled is False


def test_settings_are_immutable() -> None:
    settings = build_settings()
    with pytest.raises(ValidationError):
        settings.domain = "other"  # type: ignore[misc]  # frozen on purpose
