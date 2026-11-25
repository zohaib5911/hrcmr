"""ISS-35: PDF rendering is bounded per worker and overload is a predictable, retryable 503."""

from __future__ import annotations

import asyncio
import threading

import pytest

from app.core.errors import AppError
from app.modules.employees import record_pdf


async def test_renders_beyond_capacity_get_a_retryable_busy_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    started = 0

    def slow(html: str) -> bytes:
        nonlocal started
        started += 1
        release.wait(5)
        return b"%PDF"

    monkeypatch.setattr(record_pdf, "render_pdf", slow)
    monkeypatch.setattr(record_pdf, "_pdf_slots", asyncio.Semaphore(2))
    monkeypatch.setattr(record_pdf, "PDF_WAIT_SECONDS", 0.2)
    running = [asyncio.create_task(record_pdf.render_pdf_async("<p>x</p>")) for _ in range(2)]
    await asyncio.sleep(0.05)
    with pytest.raises(AppError) as busy:
        await record_pdf.render_pdf_async("<p>x</p>")
    assert (busy.value.code, busy.value.status_code) == ("PDF_BUSY", 503)
    assert busy.value.headers == {"Retry-After": record_pdf.PDF_RETRY_AFTER}
    assert started == 2  # the third render never started
    release.set()
    assert await asyncio.gather(*running) == [b"%PDF", b"%PDF"]
    assert await record_pdf.render_pdf_async("<p>x</p>") == b"%PDF"  # capacity is back
