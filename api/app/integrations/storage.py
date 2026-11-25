"""Object storage (Cloudflare R2 in deployment, RustFS on a developer's machine), over the S3 API.

Everything in the bucket is private. A file is reached only through a presigned link that the API
hands to someone who has just been checked, and which stops working after 60 seconds.

boto3 is synchronous, so each call runs in a worker thread and never blocks the event loop.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, BinaryIO, TypeVar

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from datetime import datetime

    from app.core.config import Settings

logger = get_logger("app.storage")

PRESIGN_SECONDS = 60
STREAM_CHUNK = 256 * 1024
T = TypeVar("T")


class StorageError(RuntimeError):
    """The storage service did not do what was asked. The message never includes keys or hosts."""


@dataclass(frozen=True)
class StoredObject:
    key: str
    last_modified: datetime
    size: int


class Storage:
    def __init__(self, *, endpoint: str, access_key: str, secret_key: str, bucket: str) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                # R2 and most S3 look-alikes reject the newer default checksum headers.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=30,
            ),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> Storage | None:
        """None when storage is not configured (no bucket on this machine); uploads then say so."""
        endpoint, access, secret, bucket = (
            settings.r2_endpoint,
            settings.r2_access_key_id,
            settings.r2_secret_access_key,
            settings.r2_bucket_files,
        )
        if not (endpoint and access and secret and bucket):
            return None
        return cls(
            endpoint=endpoint,
            access_key=access.get_secret_value(),
            secret_key=secret.get_secret_value(),
            bucket=bucket,
        )

    async def put(self, key: str, body: BinaryIO, *, content_type: str, size: int) -> None:
        def run() -> None:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                ContentLength=size,
                # Never shown inline by the browser, whatever the file claims to be.
                ContentDisposition="attachment",
                CacheControl="private, no-store",
            )

        await self._call(run)

    async def read(self, key: str) -> bytes:
        """The whole object. For small files only (a logo); big ones go by presigned link."""

        def run() -> bytes:
            body = self._client.get_object(Bucket=self._bucket, Key=key)["Body"]
            try:
                return bytes(body.read())
            finally:
                body.close()

        return await self._call(run)

    async def open(self, key: str) -> AsyncIterator[bytes]:
        """The object in pieces, for a file too big to hold in memory (an inline policy view).

        The object is opened before this returns, so a missing object or a storage failure raises
        here, before any response has started; the pieces are then read as they are sent."""
        body = await self._call(
            lambda: self._client.get_object(Bucket=self._bucket, Key=key)["Body"]
        )

        async def pieces() -> AsyncIterator[bytes]:
            try:
                while chunk := await asyncio.to_thread(body.read, STREAM_CHUNK):
                    yield bytes(chunk)
            finally:
                await asyncio.to_thread(body.close)

        return pieces()

    async def delete(self, key: str) -> None:
        await self._call(lambda: self._client.delete_object(Bucket=self._bucket, Key=key))

    async def exists(self, key: str) -> bool:
        def run() -> bool:
            try:
                self._client.head_object(Bucket=self._bucket, Key=key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                    return False
                raise
            return True

        return await self._call(run)

    def presign_get(self, key: str, *, filename: str, seconds: int = PRESIGN_SECONDS) -> str:
        """A link that downloads ``key`` as an attachment named ``filename``, for ``seconds``."""
        return str(
            self._client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    "ResponseContentDisposition": content_disposition(filename),
                    "ResponseContentType": "application/octet-stream",
                },
                ExpiresIn=seconds,
            )
        )

    async def list_objects(self, prefix: str) -> list[StoredObject]:
        def run() -> list[StoredObject]:
            found: list[StoredObject] = []
            for page in self._client.get_paginator("list_objects_v2").paginate(
                Bucket=self._bucket, Prefix=prefix
            ):
                found += [
                    StoredObject(item["Key"], item["LastModified"], int(item["Size"]))
                    for item in page.get("Contents", [])
                ]
            return found

        return await self._call(run)

    async def list_pages(
        self, prefix: str, *, page_size: int = 1000
    ) -> AsyncIterator[list[StoredObject]]:
        """The objects under ``prefix`` one page at a time (ISS-36), never the whole listing."""
        token: str | None = None
        while True:

            def run(token: str | None = token) -> dict[str, Any]:
                options: dict[str, Any] = {
                    "Bucket": self._bucket,
                    "Prefix": prefix,
                    "MaxKeys": page_size,
                }
                if token:
                    options["ContinuationToken"] = token
                return dict(self._client.list_objects_v2(**options))

            page = await self._call(run)
            yield [
                StoredObject(item["Key"], item["LastModified"], int(item["Size"]))
                for item in page.get("Contents", [])
            ]
            token = page.get("NextContinuationToken") if page.get("IsTruncated") else None
            if not token:
                return

    async def _call(self, run: Callable[[], T]) -> T:
        try:
            return await asyncio.to_thread(run)
        except (BotoCoreError, ClientError) as exc:
            logger.warning("storage_error", kind=type(exc).__name__)
            raise StorageError("The file store did not answer.") from exc


def content_disposition(filename: str) -> str:
    """``attachment`` with the name in both the plain and the RFC 5987 form, quotes made safe."""
    from urllib.parse import quote

    plain = "".join(
        ch if ch.isascii() and ch.isprintable() and ch not in '"\\' else "_" for ch in filename
    )
    return f"attachment; filename=\"{plain}\"; filename*=UTF-8''{quote(filename, safe='')}"
