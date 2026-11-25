"""ISS-37: concurrent first searches construct one model per worker; a failed load can recover."""

from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.soc import router as soc_router


async def test_concurrent_first_searches_share_one_load_and_a_failure_can_recover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built = 0
    lock = threading.Lock()
    fail = True

    def load() -> Any:
        nonlocal built
        time.sleep(0.05)
        with lock:
            built += 1
        if fail:
            raise OSError("weights not downloaded")
        return lambda texts: [[0.0] for _ in texts]

    monkeypatch.setattr(soc_router, "fastembed_embedder", load)
    state = SimpleNamespace()
    failed = await asyncio.gather(
        *(soc_router.embedder(state) for _ in range(5)), return_exceptions=True
    )
    assert all(isinstance(result, OSError) for result in failed)
    assert built == 1  # five concurrent first searches, one load
    assert getattr(state, "soc_embedder", None) is None

    fail = False
    models = await asyncio.gather(*(soc_router.embedder(state) for _ in range(5)))
    assert built == 2  # the failed load was forgotten; one retry served all five
    assert all(model is models[0] for model in models)
    assert await soc_router.embedder(state) is models[0]
    assert built == 2
