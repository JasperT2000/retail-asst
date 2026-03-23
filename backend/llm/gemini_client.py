"""
OpenAI GPT-4o-mini fallback LLM client.

Used automatically by LLMRouter when Groq hits rate limits or errors.
Replaces the original Gemini 2.0 Flash fallback which is unavailable on
the current Google API free tier (limit: 0).
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

import structlog
from openai import AsyncOpenAI

log = structlog.get_logger(__name__)

_MODEL = "gpt-4o-mini"


class GeminiStreamingClient:
    """
    Fallback LLM client — backed by OpenAI GPT-4o-mini.

    Retains the class name GeminiStreamingClient so the router requires
    no changes, but internally calls the OpenAI API.
    """

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async def stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """
        Stream response tokens from GPT-4o-mini.

        Args:
            messages: Full OpenAI-style message list (role/content dicts).

        Yields:
            Individual token strings as they arrive.
        """
        response = await self._client.chat.completions.create(
            model=_MODEL,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.3,
            max_tokens=2048,
            stream=True,
        )

        async for chunk in response:
            token = chunk.choices[0].delta.content
            if token:
                yield token

    async def complete(self, system: str, user: str) -> str:
        """
        Non-streaming completion for short tasks.

        Args:
            system: System prompt.
            user: User message.

        Returns:
            Full response string.
        """
        response = await self._client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""
