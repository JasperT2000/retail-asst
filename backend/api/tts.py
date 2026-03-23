"""
Text-to-speech endpoint using Google Cloud TTS Neural2.

POST /tts/synthesize
  Body: {"text": "...", "store_slug": "jbhifi"}
  Returns: audio/mpeg binary stream

Uses en-AU-Neural2-C (natural Australian English) via the Google Cloud TTS REST API.
The GOOGLE_TTS_API_KEY env var must be set.
"""

from __future__ import annotations

import logging
import os

import httpx
import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, field_validator

log = structlog.get_logger(__name__)
router = APIRouter()

_GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
_MAX_CHARS = 800  # truncate long responses to stay well within API limits


class TTSRequest(BaseModel):
    """Request body for POST /tts/synthesize."""

    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be empty")
        # Truncate gracefully at a sentence boundary if over limit
        if len(v) > _MAX_CHARS:
            truncated = v[:_MAX_CHARS]
            last_period = truncated.rfind(".")
            v = truncated[: last_period + 1] if last_period > _MAX_CHARS // 2 else truncated
        return v


@router.post(
    "/synthesize",
    response_class=Response,
    responses={
        200: {"content": {"audio/mpeg": {}}, "description": "MP3 audio of the synthesised speech"},
        400: {"description": "Empty or invalid text"},
        503: {"description": "Google TTS unavailable"},
    },
    tags=["tts"],
)
async def synthesize(request: TTSRequest) -> Response:
    """
    Synthesise speech using Google Cloud TTS Neural2 (en-AU-Neural2-C).

    Returns raw MP3 bytes so the frontend can play them directly via the
    Web Audio API without any base64 overhead on the wire.
    """
    api_key = os.getenv("GOOGLE_TTS_API_KEY")
    if not api_key:
        log.error("tts.missing_api_key")
        raise HTTPException(status_code=503, detail="TTS service not configured")

    payload = {
        "input": {"text": request.text},
        "voice": {
            "languageCode": "en-AU",
            "name": "en-AU-Neural2-C",  # natural Australian English, female
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": 1.0,
            "pitch": 0.0,
        },
    }

    log.info("tts.request", chars=len(request.text))

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _GOOGLE_TTS_URL,
                params={"key": api_key},
                json=payload,
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log.error("tts.google_error", status=exc.response.status_code, detail=exc.response.text)
        raise HTTPException(status_code=503, detail="TTS service error") from exc
    except httpx.RequestError as exc:
        log.error("tts.request_error", error=str(exc))
        raise HTTPException(status_code=503, detail="TTS service unreachable") from exc

    import base64

    audio_b64: str = resp.json().get("audioContent", "")
    if not audio_b64:
        raise HTTPException(status_code=503, detail="Empty audio response from TTS")

    audio_bytes = base64.b64decode(audio_b64)
    log.info("tts.success", audio_bytes=len(audio_bytes))

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )
