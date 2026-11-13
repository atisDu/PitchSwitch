"""Gemini wrapper (B2): one call that returns a validated Pydantic model.

Every Gemini call in core/ and agent/ goes through `structured()`. Model names come from
GEMINI_MODEL_FAST / GEMINI_MODEL_SMART, the key from GEMINI_API_KEY.
"""

import asyncio
import os
from functools import cache
from typing import Any, Literal, TypeVar

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

RETRY_CODES = {429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    """Gemini is not configured, or no valid answer after all retries."""


def model_name(tier: Literal["fast", "smart"] = "fast") -> str:
    """Model id for a tier; `smart` falls back to the fast model when unset."""
    fast = os.environ.get("GEMINI_MODEL_FAST", "").strip()
    name = (os.environ.get("GEMINI_MODEL_SMART", "").strip() or fast) if tier == "smart" else fast
    if not name:
        raise LLMError("GEMINI_MODEL_FAST is not set in .env")
    return name


@cache
def _client() -> genai.Client:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise LLMError("GEMINI_API_KEY is not set in .env")
    return genai.Client(api_key=key)


async def structured(
    prompt: str,
    schema: type[T],
    *,
    system: str | None = None,
    tier: Literal["fast", "smart"] = "fast",
    retries: int = 3,
    backoff: float = 1.0,
    client: Any = None,
) -> T:
    """Ask Gemini for JSON matching `schema` (temperature 0) and return it validated.

    Retries on rate limits, 5xx, network errors and answers that don't validate.
    Raises LLMError when it still fails after `retries` attempts.
    """
    client = client or _client()
    config = types.GenerateContentConfig(
        temperature=0,
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,  # the SDK converts the Pydantic model to Gemini's schema format
    )
    last: Exception | None = None
    for attempt in range(retries):
        if attempt:
            await asyncio.sleep(backoff * 2 ** (attempt - 1))
        try:
            resp = await client.aio.models.generate_content(
                model=model_name(tier), contents=prompt, config=config
            )
            return schema.model_validate_json(resp.text or "")
        except errors.APIError as e:
            if e.code not in RETRY_CODES:
                raise LLMError(f"Gemini error {e.code}: {e.message}") from e
            last = e
        except (ValidationError, httpx.TransportError) as e:  # bad/empty JSON, network trouble
            last = e
    raise LLMError(f"Gemini: no valid answer after {retries} attempts: {last}") from last
