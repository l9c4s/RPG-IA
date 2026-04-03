"""TTS router — all endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from application.tts.dtos import SynthesizeDTO, SynthesizeNpcDTO
from application.tts.use_cases import ListVoicesUseCase, SynthesizeNpcUseCase, SynthesizeUseCase
from domain.voice.entity import VoiceProfileRegistry
from domain.voice.services import ContextInferenceService
from infrastructure.cache.redis_cache import RedisCache
from infrastructure.storage.minio_service import MinioAudioService
from infrastructure.tts.elevenlabs_service import ElevenLabsService
from presentation.dependencies import get_cache, get_inference, get_registry, get_storage, get_tts
from presentation.schemas.tts import (
    AudioResponse,
    SynthesizeNpcRequest,
    SynthesizeRequest,
    VoiceProfileInfo,
    VoicesResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_VALUE_ERROR_MAP = {
    "empty_text": (422, "O campo 'text' não pode estar vazio."),
    "empty_npc_name": (422, "O campo 'npc_name' não pode estar vazio."),
    "text_too_long": (422, "Texto excede 4500 caracteres."),
}


def _handle_value_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code in _VALUE_ERROR_MAP:
        status, detail = _VALUE_ERROR_MAP[code]
        return HTTPException(status_code=status, detail=detail)
    if code.startswith("invalid_context:"):
        ctx = code.split(":", 1)[1]
        return HTTPException(status_code=422, detail=f"Contexto '{ctx}' inválido.")
    return HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
async def health(registry: VoiceProfileRegistry = Depends(get_registry)) -> dict:
    configured = sum(1 for p in registry.all().values() if p.voice_id)
    return {"status": "ok", "service": "tts", "profiles_configured": configured}


# ---------------------------------------------------------------------------
# GET /voices
# ---------------------------------------------------------------------------


@router.get("/voices", response_model=VoicesResponse)
async def list_voices(registry: VoiceProfileRegistry = Depends(get_registry)) -> VoicesResponse:
    profiles_dto, keywords = ListVoicesUseCase(registry).execute()
    return VoicesResponse(
        profiles={
            p.name: VoiceProfileInfo(
                name=p.name,
                voice_id=p.voice_id,
                stability=p.stability,
                similarity_boost=p.similarity_boost,
                style=p.style,
                speed=p.speed,
                description=p.description,
            )
            for p in profiles_dto
        },
        inference_keywords=keywords,
    )


# ---------------------------------------------------------------------------
# POST /synthesize
# ---------------------------------------------------------------------------


@router.post("/synthesize", response_model=AudioResponse)
async def synthesize(
    request: SynthesizeRequest,
    registry: VoiceProfileRegistry = Depends(get_registry),
    tts: ElevenLabsService = Depends(get_tts),
    cache: RedisCache = Depends(get_cache),
    storage: MinioAudioService = Depends(get_storage),
    inference: ContextInferenceService = Depends(get_inference),
) -> AudioResponse:
    dto = SynthesizeDTO(
        text=request.text,
        context=request.context,
        voice_id_override=request.voice_id_override,
    )
    try:
        result = await SynthesizeUseCase(
            registry=registry, tts=tts, cache=cache, storage=storage, inference=inference
        ).execute(dto)
    except ValueError as exc:
        raise _handle_value_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return AudioResponse(
        audio_url=result.audio_url,
        context_used=result.context_used,
        voice_profile=result.voice_profile,
    )


# ---------------------------------------------------------------------------
# POST /synthesize/npc
# ---------------------------------------------------------------------------


@router.post("/synthesize/npc", response_model=AudioResponse)
async def synthesize_npc(
    request: SynthesizeNpcRequest,
    registry: VoiceProfileRegistry = Depends(get_registry),
    tts: ElevenLabsService = Depends(get_tts),
    cache: RedisCache = Depends(get_cache),
    storage: MinioAudioService = Depends(get_storage),
) -> AudioResponse:
    dto = SynthesizeNpcDTO(
        text=request.text,
        npc_name=request.npc_name,
        npc_type=request.npc_type,
        context=request.context,
    )
    try:
        result = await SynthesizeNpcUseCase(
            registry=registry, tts=tts, cache=cache, storage=storage
        ).execute(dto)
    except ValueError as exc:
        raise _handle_value_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return AudioResponse(
        audio_url=result.audio_url,
        context_used=result.context_used,
        voice_profile=result.voice_profile,
    )
