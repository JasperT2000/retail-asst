"""
Groq LLM streaming client.

Primary LLM provider using llama-3.3-70b-versatile via the Groq API.
Streams tokens using the Groq Python SDK's async streaming interface.
Raises GroqRateLimitError (a local wrapper) so the router can catch it
without importing the Groq SDK directly.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

import structlog
from groq import AsyncGroq
from groq import RateLimitError as _GroqSDKRateLimitError

log = structlog.get_logger(__name__)

_MODEL = "llama-3.3-70b-versatile"


class GroqRateLimitError(Exception):
    """Raised when the Groq API returns a 429 rate limit response."""


class GroqStreamingClient:
    """Async Groq client for streaming LLM completions."""

    def __init__(self) -> None:
        self._client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

    async def stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """
        Stream response tokens from Groq.

        Args:
            messages: Full message list including the system message as the
                      first element (role="system").

        Yields:
            Individual token strings as they arrive.

        Raises:
            GroqRateLimitError: When the Groq API returns 429.
        """
        try:
            stream = await self._client.chat.completions.create(
                model=_MODEL,
                messages=messages,  # type: ignore[arg-type]
                stream=True,
                temperature=0.3,
                max_tokens=1024,
            )
            async for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    yield token
        except _GroqSDKRateLimitError as exc:
            raise GroqRateLimitError(str(exc)) from exc

    async def complete(self, system: str, user: str) -> str:
        """
        Non-streaming completion for short tasks like intent classification.

        Args:
            system: System prompt string.
            user: User message string.

        Returns:
            Full response string.

        Raises:
            GroqRateLimitError: When the Groq API returns 429.
        """
        try:
            response = await self._client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                stream=False,
                temperature=0.0,
                max_tokens=64,
            )
            return response.choices[0].message.content or ""
        except _GroqSDKRateLimitError as exc:
            raise GroqRateLimitError(str(exc)) from exc
