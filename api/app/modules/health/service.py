from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Literal

from app.core.logging import get_logger

Probe = Callable[[], Awaitable[None]]
CheckResult = Literal["ok", "fail"]

PROBE_TIMEOUT_SECONDS = 2.0
logger = get_logger("app.health")


async def _run_one(name: str, probe: Probe, seconds: float) -> CheckResult:
    try:
        async with asyncio.timeout(seconds):
            await probe()
    except Exception as exc:
        # Log the class only: driver messages can name hosts, and the response must not.
        logger.warning("readiness_check_failed", check=name, error_type=type(exc).__name__)
        return "fail"
    return "ok"


async def run_probes(
    probes: Mapping[str, Probe], seconds: float = PROBE_TIMEOUT_SECONDS
) -> dict[str, CheckResult]:
    """Run every probe at once, each with its own time limit."""
    names = list(probes)
    results = await asyncio.gather(*(_run_one(n, probes[n], seconds) for n in names))
    return dict(zip(names, results, strict=True))
