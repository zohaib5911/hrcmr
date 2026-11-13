"""Verify the final SDK envelope, not just a standalone scrubber."""

from __future__ import annotations

import json
from typing import Any

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from app.core.telemetry import before_send, configure_telemetry
from tests.support import build_settings


@pytest.fixture(autouse=True)
def _client() -> Any:
    original = sentry_sdk.get_global_scope().client
    yield
    sentry_sdk.get_global_scope().set_client(original)


class Capture(Transport):
    def __init__(self, options: dict[str, Any]) -> None:
        super().__init__(options)
        self.events: list[dict[str, Any]] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        for item in envelope.items:
            if item.headers.get("type") == "event":
                self.events.append(json.loads(item.get_bytes()))


def test_sdk_scrubs_exception_request_breadcrumbs_locals_and_free_text() -> None:
    client = sentry_sdk.Client(
        dsn="https://public@example.test/1",
        transport=Capture,
        default_integrations=False,
        before_send=before_send,
        include_local_variables=True,
    )
    with sentry_sdk.isolation_scope() as scope:
        scope.set_client(client)
        with sentry_sdk.new_scope() as scope:
            scope.set_user({"email": "PRIVATE-USER"})
            scope.set_extra("context", {"passport": "PRIVATE-EXTRA"})
            scope.add_event_processor(
                lambda event, hint: {
                    **event,
                    "request": {
                        "data": "PRIVATE-BODY",
                        "headers": {"Authorization": "PRIVATE-AUTH"},
                    },
                    "breadcrumbs": {"values": [{"message": "PRIVATE-BREADCRUMB"}]},
                }
            )
            try:
                raise ValueError("PRIVATE-MESSAGE AB123456C")
            except ValueError:
                sentry_sdk.capture_exception()
        transport = client.transport
        assert isinstance(transport, Capture)
        assert len(transport.events) == 1
        event = transport.events[0]
        assert "PRIVATE" not in json.dumps(event)
        assert "AB123456C" not in json.dumps(event)
        assert event["exception"]["values"][0]["type"] == "ValueError"
        assert event["exception"]["values"][0]["stacktrace"]["frames"]
        assert set(event) <= {"event_id", "timestamp", "platform", "level", "exception"}


def test_configured_sdk_has_no_pii_capture_or_automatic_integrations() -> None:
    with sentry_sdk.isolation_scope():
        configure_telemetry(build_settings(sentry_dsn_api="https://public@example.test/1"))
        client = sentry_sdk.get_client()
        assert client.options["data_collection"]["user_info"] is False
        assert client.options["data_collection"]["http_bodies"] == []
        assert client.options["include_local_variables"] is False
        assert client.options["max_request_body_size"] == "never"
        assert client.options["traces_sample_rate"] == 0
        assert client.options["max_breadcrumbs"] == 0
        assert client.options["before_send"] is before_send
        assert not client.integrations
        client.close()
