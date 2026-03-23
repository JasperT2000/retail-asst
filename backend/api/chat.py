"""
SSE streaming chat endpoint.

Accepts a user message and store context, runs the RAGPipeline,
and streams response tokens back as Server-Sent Events.

SSE event types emitted:
  token    — {"token": "..."}
  metadata — {"confidence": 0.87, "sources": [...], "human_notified": false, "intent": "..."}
  error    — {"message": "..."}
  done     — {}
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncGenerator

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from backend.api.stores import VALID_STORES

log = structlog.get_logger(__name__)
router = APIRouter()

_MAX_HISTORY = 10
_MAX_MESSAGE_LEN = 500


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """A single turn in the conversation history."""

    role: str
    content: str


class ChatRequest(BaseModel):
    """Request body for POST /chat/stream."""

    store_slug: str
    message: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_history: list[ChatMessage] = Field(default_factory=list)

    @field_validator("store_slug")
    @classmethod
    def validate_store_slug(cls, v: str) -> str:
        if v not in VALID_STORES:
            raise ValueError(f"Unknown store: '{v}'")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if len(v) > _MAX_MESSAGE_LEN:
            raise ValueError(f"Message exceeds {_MAX_MESSAGE_LEN} characters")
        if not v.strip():
            raise ValueError("Message must not be empty")
        return v


# ---------------------------------------------------------------------------
# SSE generator
# ---------------------------------------------------------------------------


async def _event_stream(request: ChatRequest) -> AsyncGenerator[str, None]:
    """
    Run the RAGPipeline and yield SSE-formatted event strings.

    Tokens are emitted as they arrive from the LLM. After the generator is
    exhausted, a metadata event fires, then a done event closes the stream.
    Client disconnection (asyncio.CancelledError) is caught and logged cleanly.
    """
    from backend.rag.pipeline import RAGPipeline  # lazy — avoids circular import

    # Trim history to the most recent N turns
    history = [
        {"role": m.role, "content": m.content}
        for m in request.conversation_history[-_MAX_HISTORY:]
    ]

    pipeline = RAGPipeline(store_slug=request.store_slug)

    try:
        async for token in pipeline.run(
            query=request.message,
            conversation_history=history,
            session_id=request.session_id,
        ):
            yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"

        output = pipeline.get_last_output()
        metadata = {
            "confidence": round(output.confidence_score, 3),
            "sources": output.source_nodes[:5],
            "human_notified": output.human_notified,
            "intent": output.intent,
        }
        yield f"event: metadata\ndata: {json.dumps(metadata)}\n\n"

    except asyncio.CancelledError:
        log.info("chat.client_disconnected", session_id=request.session_id)
        # Don't re-raise — generator simply ends; 'finally' emits done
    except Exception as exc:
        log.error("chat.stream_error", error=str(exc), session_id=request.session_id)
        yield f"event: error\ndata: {json.dumps({'message': 'An error occurred'})}\n\n"

    finally:
        yield "event: done\ndata: {}\n\n"


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post(
    "/stream",
    response_class=StreamingResponse,
    responses={
        200: {"description": "SSE stream of tokens, metadata, then done event"},
        422: {"description": "Invalid store_slug or message"},
    },
    tags=["chat"],
)
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Stream a chat response as Server-Sent Events.

    Validates store_slug (one of the four known stores) and message length
    (max 500 characters) before starting the pipeline. Returns SSE events:
    `token`, `metadata`, `done`, or `error` followed by `done`.
    """
    log.info(
        "chat.request",
        store=request.store_slug,
        session_id=request.session_id,
        message_len=len(request.message),
    )

    return StreamingResponse(
        _event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
