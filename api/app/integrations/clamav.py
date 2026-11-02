"""Virus scanning with ClamAV's ``clamd`` over its INSTREAM protocol (plan.md 4.5).

The file is streamed to the scanner in chunks and never touches clamd's disk. The check fails
CLOSED: if the scanner cannot be reached, times out or answers with an error, the file is not
accepted. A scanner that is down must not turn into a way to upload anything.
"""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, BinaryIO, Literal

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.config import Settings

logger = get_logger("app.clamav")

CHUNK = 64 * 1024
TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class ScanResult:
    status: Literal["clean", "infected", "error"]
    signature: str | None = None


class ClamAV:
    def __init__(self, host: str, port: int) -> None:
        self._host, self._port = host, port

    @classmethod
    def from_settings(cls, settings: Settings) -> ClamAV:
        return cls(settings.clamav_host, settings.clamav_port)

    async def scan(self, stream: BinaryIO) -> ScanResult:
        try:
            return await asyncio.wait_for(self._scan(stream), TIMEOUT_SECONDS)
        except (OSError, TimeoutError, asyncio.IncompleteReadError, ValueError):
            logger.warning("clamav_unavailable")
            return ScanResult("error")

    async def _scan(self, stream: BinaryIO) -> ScanResult:
        reader, writer = await asyncio.open_connection(self._host, self._port)
        try:
            writer.write(b"zINSTREAM\0")
            while chunk := await asyncio.to_thread(stream.read, CHUNK):
                writer.write(struct.pack(">I", len(chunk)) + chunk)
                await writer.drain()
            writer.write(struct.pack(">I", 0))
            await writer.drain()
            reply = (await reader.readuntil(b"\0")).rstrip(b"\0").decode("utf-8", "replace").strip()
        finally:
            writer.close()
        # "stream: OK", "stream: Eicar-Test-Signature FOUND", or "... ERROR".
        verdict = reply.removeprefix("stream:").strip()
        if verdict == "OK":
            return ScanResult("clean")
        if verdict.endswith(" FOUND"):
            return ScanResult("infected", verdict.removesuffix(" FOUND"))
        logger.warning("clamav_error_reply")
        return ScanResult("error")
