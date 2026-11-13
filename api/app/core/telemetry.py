"""Sentry receives diagnostic structure only; arbitrary text is never trustworthy."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import sentry_sdk

if TYPE_CHECKING:
    from sentry_sdk.types import Event, Hint

    from app.core.config import Settings

_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z0-9_.<>-]{0,159}\Z")


def before_send(event: Event, hint: Hint) -> Event:
    """Allowlist instead of chasing PII in request, extras, breadcrumbs and locals.

    Exception messages, source context and filenames can contain employee data too.
    Never use the hint: it contains the original unsanitised exception/request.
    """
    clean: dict[str, Any] = {
        key: event[key] for key in ("event_id", "timestamp", "platform", "level") if key in event
    }
    values = []
    for error in (event.get("exception") or {}).get("values", []):
        kind = error.get("type", "Error")
        frames = []
        for frame in (error.get("stacktrace") or {}).get("frames", []):
            safe = {
                key: value
                for key in ("module", "function")
                if isinstance(value := frame.get(key), str) and _SYMBOL.fullmatch(value)
            }
            if isinstance(frame.get("lineno"), int):
                safe["lineno"] = frame["lineno"]
            frames.append(safe)
        values.append(
            {
                "type": kind if isinstance(kind, str) and _SYMBOL.fullmatch(kind) else "Error",
                "value": "[redacted]",
                "stacktrace": {"frames": frames},
            }
        )
    if values:
        clean["exception"] = {"values": values}
    else:
        clean["message"] = "[redacted]"
    return clean  # type: ignore[return-value]


def configure_telemetry(settings: Settings) -> None:
    if not settings.sentry_dsn_api:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn_api.get_secret_value(),
        # Current SDK replaces send_default_pii=False with category controls.
        data_collection={
            "user_info": False,
            "cookies": {"mode": "off"},
            "url_query_params": {"mode": "off"},
            "http_bodies": [],
            "stack_frame_variables": False,
            "frame_context_lines": 0,
            "database_query_data": False,
            "queues": False,
        },
        include_local_variables=False,
        max_request_body_size="never",
        default_integrations=False,
        auto_enabling_integrations=False,
        traces_sample_rate=0,
        max_breadcrumbs=0,
        before_send=before_send,
    )
