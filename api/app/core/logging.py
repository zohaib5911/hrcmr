"""Structured JSON logging with redaction (plan.md sections 4.1 and 4.6).

Every log line is one JSON object on stdout carrying the request id. Two processors run on
EVERY record, including records from third-party libraries (uvicorn, gunicorn, SQLAlchemy):

* ``redact_sensitive_keys`` drops any key whose name matches the plan's sensitive list.
* ``scrub_url_credentials`` masks the password in anything shaped like ``scheme://user:pass@host``,
  because driver and ORM error messages can contain connection strings.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import TYPE_CHECKING, Any

import structlog

from app.ai.redaction import PATTERNS, is_restricted_key

if TYPE_CHECKING:
    from structlog.typing import EventDict, Processor, WrappedLogger

# plan.md 4.6: password|token|secret|authorization|cookie|ni_number|passport|sort_code|
# account_number|share_code|cos_number|salary|bank
SENSITIVE_KEY = re.compile(
    r"password|token|secret|authorization|cookie|ni_number|passport|sort_code"
    r"|account_number|share_code|cos_number|salary|bank",
    re.IGNORECASE,
)
_URL_CREDENTIALS = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*://)(?P<user>[^\s:/@]*):(?P<password>[^\s@/]+)@"
)
MASK = "***"


def _sensitive(key: str) -> bool:
    return (
        bool(SENSITIVE_KEY.search(key))
        or is_restricted_key(key)
        or key.lower()
        in {
            "body",
            "request_body",
            "payload",
            "prompt",
            "answer",
            "cv",
        }
    )


def _drop_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _drop_sensitive(v) for k, v in value.items() if not _sensitive(str(k))}
    if isinstance(value, list | tuple):
        return [_drop_sensitive(item) for item in value]
    return value


def redact_sensitive_keys(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    """Remove sensitive keys at any depth."""
    return {k: _drop_sensitive(v) for k, v in event_dict.items() if not _sensitive(k)}


def scrub_text(text: str) -> str:
    text = _URL_CREDENTIALS.sub(rf"\g<scheme>\g<user>:{MASK}@", text)
    text = re.sub(
        r"(?i)((?:password|token|secret|authorization|cookie)[\w-]*[=:\s]+)[^\s&;,]+",
        rf"\1{MASK}",
        text,
    )
    for kind in ("ni_number", "salary", "passport", "share_code"):
        text = PATTERNS[kind].sub(MASK, text)
    return text


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_scrub(item) for item in value]
    return value


def scrub_url_credentials(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    """Mask passwords inside URLs in every string value (including formatted tracebacks)."""
    return {k: _scrub(v) for k, v in event_dict.items()}


class _StdoutHandler(logging.Handler):
    """Write each record to whatever ``sys.stdout`` is at emit time.

    A plain ``StreamHandler(sys.stdout)`` keeps the stream object it saw at configuration time,
    which goes stale when a process manager or test runner swaps ``sys.stdout`` afterwards.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stdout.write(self.format(record) + "\n")
            sys.stdout.flush()
        except Exception:
            self.handleError(record)


def configure_logging(level: str = "INFO") -> None:
    """Route structlog and the standard library through one JSON pipeline. Safe to call twice."""
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_sensitive_keys,
        scrub_url_credentials,
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = _StdoutHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    # Libraries log through the root handler. uvicorn's own access log is replaced by the
    # request middleware's line, which never includes the query string (it can hold tokens).
    for name in ("uvicorn", "uvicorn.error", "gunicorn.error"):
        lib = logging.getLogger(name)
        lib.handlers.clear()
        lib.propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
    # HTTP client libraries log each request URL at INFO, and a URL can carry a token.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
