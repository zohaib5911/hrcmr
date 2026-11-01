"""Gunicorn settings (plan.md T0.4).

Railway provides PORT. Tune the worker count with WEB_CONCURRENCY. Start with:
    gunicorn -c gunicorn.conf.py "app.main:create_app()"
"""

from __future__ import annotations

import multiprocessing
import os
from pathlib import Path
from typing import Any

from gunicorn.glogging import Logger as GunicornLogger
from uvicorn_worker import UvicornWorker

from app.core.logging import configure_logging


class JsonLogger(GunicornLogger):  # type: ignore[misc]  # gunicorn ships no type stubs
    """Gunicorn replaces the root log handler while it sets itself up. Put ours back afterwards, so
    the master process's own messages are JSON and pass through the redaction processors too."""

    def setup(self, cfg: Any) -> None:
        super().setup(cfg)
        configure_logging()


class ApiWorker(UvicornWorker):  # type: ignore[misc]  # uvicorn_worker ships no type stubs
    """Uvicorn worker that does not advertise the server software in a ``Server`` header."""

    CONFIG_KWARGS: dict[str, Any] = {"loop": "auto", "http": "auto", "server_header": False}


bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
worker_class = ApiWorker
workers = int(os.environ.get("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 4)))
timeout = 30
graceful_timeout = 30
keepalive = 5
# Recycle workers now and then to bound any slow memory growth.
max_requests = 2000
max_requests_jitter = 200
# Heartbeat files in memory: avoids stalls on container filesystems.
worker_tmp_dir = "/dev/shm" if Path("/dev/shm").is_dir() else None  # noqa: S108

# The request middleware writes one JSON access line per request, without the query string.
accesslog = None
errorlog = "-"
loglevel = "info"
logger_class = JsonLogger
