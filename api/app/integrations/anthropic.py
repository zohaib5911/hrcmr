"""Anthropic Claude (plan.md 8.12). Only the API calls it; the browser never holds the key.

It is optional: with no ``ANTHROPIC_API_KEY`` there is no client and every AI feature is hidden.
Every request body passes ``assert_clean`` just before it is sent, so a restricted identifier that
slipped past ``scrub`` stops the call instead of reaching the provider.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

from app.ai.redaction import assert_clean
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.config import Settings

logger = get_logger("app.anthropic")

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
TIMEOUT_SECONDS = 30.0


class AnthropicError(Exception):
    """The provider could not answer (unreachable, refused, or an unexpected reply)."""


@dataclass(frozen=True)
class Completion:
    reply: str
    model: str
    input_tokens: int
    output_tokens: int


class Anthropic:
    def __init__(
        self,
        api_key: str,
        *,
        model_main: str,
        model_fast: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._key = api_key
        self.model_main = model_main
        self.model_fast = model_fast
        self._client = client

    @classmethod
    def from_settings(
        cls, settings: Settings, client: httpx.AsyncClient | None = None
    ) -> Anthropic | None:
        key = settings.anthropic_api_key
        if key is None:
            return None
        return cls(
            key.get_secret_value(),
            model_main=settings.anthropic_model_main,
            model_fast=settings.anthropic_model_fast,
            client=client,
        )

    @staticmethod
    def build_body(
        *, model: str, system: str, messages: list[dict[str, Any]], max_tokens: int
    ) -> str:
        """The exact JSON that goes on the wire, checked for restricted data."""
        body = json.dumps(
            {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages},
            ensure_ascii=False,
        )
        assert_clean(body)
        return body

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        fast: bool = True,
        max_tokens: int = 1024,
    ) -> Completion:
        model = self.model_fast if fast else self.model_main
        body = self.build_body(model=model, system=system, messages=messages, max_tokens=max_tokens)
        headers = {
            "x-api-key": self._key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }
        client = self._client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
        try:
            response = await client.post(
                API_URL, content=body.encode("utf-8"), headers=headers, timeout=TIMEOUT_SECONDS
            )
        except httpx.HTTPError as exc:
            logger.warning("anthropic_unreachable")
            raise AnthropicError from exc
        finally:
            if self._client is None:
                await client.aclose()
        if response.status_code != 200:
            logger.warning("anthropic_error", status=response.status_code)
            raise AnthropicError
        try:
            data = response.json()
            text = "".join(
                block.get("text", "") for block in data["content"] if block.get("type") == "text"
            )
            usage = data.get("usage", {})
            return Completion(
                reply=text,
                model=str(data.get("model", model)),
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
            )
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("anthropic_bad_reply")
            raise AnthropicError from exc
