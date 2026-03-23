"""
LLM router with automatic Groq → Gemini fallback.

All LLM calls in the pipeline must go through this router — never call
Groq or Gemini clients directly. On GroqRateLimitError or any Groq
exception, the router falls back to Gemini seamlessly.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

import structlog

from backend.llm.groq_client import GroqStreamingClient, GroqRateLimitError
from backend.llm.gemini_client import GeminiStreamingClient

log = structlog.get_logger(__name__)


class LLMRouter:
    """Routes LLM requests between Groq (primary) and OpenAI (fallback).

    Set OPENAI_ONLY=1 in the environment to skip Groq entirely — useful
    when Groq's rate limits would add retry delays (e.g. during eval runs).
    """

    def __init__(self) -> None:
        self._groq = GroqStreamingClient()
        self._gemini = GeminiStreamingClient()
        self._openai_only = os.getenv("OPENAI_ONLY", "0") == "1"

    async def stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens from Groq, falling back to OpenAI on failure.

        Args:
            messages: Full messages list including the system message as
                      the first element (role="system").

        Yields:
            Token strings in arrival order.
        """
        if self._openai_only:
            log.info("llm_router.using_openai_only")
            async for token in self._gemini.stream(messages):
                yield token
            return

        try:
            log.info("llm_router.using_groq")
            async for token in self._groq.stream(messages):
                yield token
        except GroqRateLimitError:
            log.warning("llm_router.groq_rate_limit_falling_back_to_gemini")
            async for token in self._gemini.stream(messages):
                yield token
        except Exception as exc:
            log.warning(
                "llm_router.groq_error_falling_back_to_gemini",
                error=str(exc),
            )
            async for token in self._gemini.stream(messages):
                yield token

    async def complete(self, system: str, user: str) -> str:
        """
        Non-streaming completion with automatic fallback.

        Args:
            system: System prompt string.
            user: User message string.

        Returns:
            Full response string.
        """
        if self._openai_only:
            return await self._gemini.complete(system, user)

        try:
            return await self._groq.complete(system, user)
        except GroqRateLimitError:
            log.warning("llm_router.groq_rate_limit_complete_fallback_gemini")
            return await self._gemini.complete(system, user)
        except Exception as exc:
            log.warning(
                "llm_router.groq_error_complete_fallback_gemini",
                error=str(exc),
            )
            return await self._gemini.complete(system, user)
