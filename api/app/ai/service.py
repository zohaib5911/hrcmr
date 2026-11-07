"""One way to ask the AI anything (plan.md 8.12): gate, rate limit, redact, call, log.

Features (letters, reminder wording, later SOC and CV match) call ``ai_ready`` to decide whether to
offer AI at all, and ``generate`` to get text. ``generate`` sends only what ``scrub`` lets through,
maps employee labels back to names in the answer, and logs metadata only (no prompt, no answer).
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.ai.models import AiInteraction
from app.ai.redaction import Pseudonymiser, RestrictedDataError, redact_text, scrub
from app.core.errors import AppError
from app.core.rate_limit import AI_PER_USER, RateLimiter
from app.integrations.anthropic import Anthropic, AnthropicError
from app.modules.companies.models import Company

if TYPE_CHECKING:
    from fastapi import Request

    from app.modules.rbac.deps import Access

# Guardrails shared by every feature; each feature adds its own task after this.
BASE_SYSTEM = (
    "You help HR staff at a UK company with HR administration. Rules: do not give legal advice; "
    "answer only HR questions; use figures only from the data provided and never invent them; if "
    'the data does not include something, say "I can\'t see that". People appear as labels such '
    "as Employee A; keep the labels exactly as given. Use British English."
)


def client_for(request: Request) -> Anthropic | None:
    return getattr(request.app.state, "anthropic", None)


async def ai_ready(request: Request, access: Access) -> bool:
    """True when the server has a key, AI is on for the platform, and on for this company."""
    if client_for(request) is None or not request.app.state.settings.ai_features_enabled:
        return False
    enabled = (
        await access.db.execute(
            select(Company.ai_features_enabled).where(Company.id == access.company_id)
        )
    ).scalar_one_or_none()
    return bool(enabled)


async def _log(
    access: Access, *, feature: str, model: str, status: str, started: float, usage: tuple[int, int]
) -> None:
    access.db.add(
        AiInteraction(
            company_id=access.company_id,
            user_id=access.caller.user_id,
            feature=feature,
            model=model,
            status=status,
            input_tokens=usage[0],
            output_tokens=usage[1],
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    )
    await access.db.commit()


def build_prompt(instruction: str, data: Any, pseudonymiser: Pseudonymiser) -> str:
    """The user message: the task in words, then the scrubbed data as JSON."""
    safe = scrub(data, pseudonymiser)
    text = redact_text(pseudonymiser.replace_names(instruction))
    return f"{text}\n\nData:\n{json.dumps(safe, ensure_ascii=False, default=str)}"


async def generate(
    request: Request,
    access: Access,
    *,
    feature: str,
    task: str,
    instruction: str,
    data: Any = None,
    fast: bool = True,
    max_tokens: int = 1024,
) -> str:
    client = client_for(request)
    if client is None or not await ai_ready(request, access):
        raise AppError("AI_UNAVAILABLE", "AI features are turned off.", status_code=409)
    name, limit, window = AI_PER_USER
    result = await RateLimiter(request.app.state.auth.redis).hit(
        name, str(access.caller.user_id), limit=limit, window_seconds=window
    )
    if not result.allowed:
        raise AppError(
            "RATE_LIMITED",
            "You have used the AI 30 times this hour. Try again later.",
            status_code=429,
        )
    pseudonymiser = Pseudonymiser()
    prompt = build_prompt(instruction, data, pseudonymiser)
    model = client.model_fast if fast else client.model_main
    started = time.monotonic()
    try:
        completion = await client.complete(
            system=f"{BASE_SYSTEM}\n\n{task}",
            messages=[{"role": "user", "content": prompt}],
            fast=fast,
            max_tokens=max_tokens,
        )
    except RestrictedDataError as exc:
        await _log(
            access, feature=feature, model=model, status="refused", started=started, usage=(0, 0)
        )
        raise AppError(
            "AI_REFUSED",
            "This request held personal data that is never sent to the AI.",
            status_code=422,
        ) from exc
    except AnthropicError as exc:
        await _log(
            access, feature=feature, model=model, status="error", started=started, usage=(0, 0)
        )
        raise AppError("AI_FAILED", "The AI could not answer. Try again.", status_code=502) from exc
    await _log(
        access,
        feature=feature,
        model=completion.model,
        status="ok",
        started=started,
        usage=(completion.input_tokens, completion.output_tokens),
    )
    return pseudonymiser.restore(completion.reply)
