from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from app.core.errors import AIUnavailable

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_TIMEOUT_SECONDS = 45


class AIProvider(Protocol):
    """Small abstraction so ChatService never touches the Gemini SDK."""

    async def complete(self, *, system_prompt: str, prompt: str) -> str: ...


class GeminiProvider:
    """Async wrapper around the google-genai SDK.

    All failures (missing key, timeout, rate limit, transport error, empty
    response) are converted into AIUnavailable. Raw SDK exception text is only
    logged server-side and never returned to a caller, so the API key can
    never leak into a response.
    """

    def __init__(
        self,
        api_key: str | None,
        model: str | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._model = model or DEFAULT_MODEL
        self._timeout_seconds = timeout_seconds

    async def complete(self, *, system_prompt: str, prompt: str) -> str:
        if not self._api_key:
            raise AIUnavailable("GEMINI_API_KEY is not configured")

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._api_key)
            async with client.aio as aio_client:
                response = await asyncio.wait_for(
                    aio_client.models.generate_content(
                        model=self._model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.4,
                        ),
                    ),
                    timeout=self._timeout_seconds,
                )
            text = response.text if response is not None else None
        except AIUnavailable:
            raise
        except Exception:
            logger.exception("Gemini chat request failed")
            raise AIUnavailable("Gemini request failed") from None

        if not text or not text.strip():
            raise AIUnavailable("Gemini returned an empty response")
        return text.strip()
