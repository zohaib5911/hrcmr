from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness: the process is up. Touches no dependency, so it never flaps."""

    status: Literal["ok"]


class ReadyResponse(BaseModel):
    """Readiness: every dependency answered. Safe to expose: no hostnames, versions or errors."""

    status: Literal["ready", "not_ready"]
    checks: dict[str, Literal["ok", "fail"]]
