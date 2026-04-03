"""Use cases for the TTS context."""
from __future__ import annotations

import hashlib
import logging

from domain.voice.entity import VoiceProfile, VoiceProfileRegistry
from domain.voice.repository import IAudioStoragePort, ICachePort, ITtsPort
from domain.voice.services import CONTEXT_KEYWORDS, ContextInferenceService

from .dtos import AudioResultDTO, SynthesizeDTO, SynthesizeNpcDTO, VoiceProfileDTO

logger = logging.getLogger(__name__)

TEXT_MAX_LENGTH = 4500
CACHE_TTL = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Shared cache helper
# ---------------------------------------------------------------------------


def _cache_key(text: str, voice_id: str, stability: float, style: float) -> str:
    payload = f"{text}:{voice_id}:{stability:.2f}:{style:.2f}"
    return "tts:" + hashlib.sha256(payload.encode()).hexdigest()


def _object_name(cache_key: str) -> str:
    return f"audio/{cache_key.removeprefix('tts:')}.mp3"


async def _synthesize_and_cache(
    text: str,
    profile: VoiceProfile,
    tts: ITtsPort,
    cache: ICachePort,
    storage: IAudioStoragePort,
) -> str:
    key = _cache_key(text, profile.voice_id, profile.stability, profile.style)
    obj = _object_name(key)

    try:
        cached = await cache.get(key)
        if cached:
            logger.info("Cache hit: %s", key[:16])
            return cached
    except Exception as exc:
        logger.warning("Redis indisponível (continuando sem cache): %s", exc)

    audio_bytes = await tts.synthesize(text, profile)
    audio_url = await storage.upload(obj, audio_bytes)

    try:
        await cache.set(key, audio_url, CACHE_TTL)
    except Exception as exc:
        logger.warning("Erro ao cachear no Redis: %s", exc)

    return audio_url


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------


class SynthesizeUseCase:
    def __init__(
        self,
        registry: VoiceProfileRegistry,
        tts: ITtsPort,
        cache: ICachePort,
        storage: IAudioStoragePort,
        inference: ContextInferenceService,
    ) -> None:
        self._registry = registry
        self._tts = tts
        self._cache = cache
        self._storage = storage
        self._inference = inference

    async def execute(self, dto: SynthesizeDTO) -> AudioResultDTO:
        text = dto.text.strip()
        if not text:
            raise ValueError("empty_text")
        if len(text) > TEXT_MAX_LENGTH:
            raise ValueError("text_too_long")

        context = dto.context or self._inference.infer(text)
        profile = self._registry.get(context)
        if profile is None:
            raise ValueError(f"invalid_context:{context}")

        if dto.voice_id_override:
            profile = profile.with_voice_id(dto.voice_id_override)

        logger.info("Síntese: contexto='%s' stability=%.2f chars=%d", context, profile.stability, len(text))
        audio_url = await _synthesize_and_cache(text, profile, self._tts, self._cache, self._storage)
        return AudioResultDTO(audio_url=audio_url, context_used=context, voice_profile=profile.description)


class SynthesizeNpcUseCase:
    def __init__(
        self,
        registry: VoiceProfileRegistry,
        tts: ITtsPort,
        cache: ICachePort,
        storage: IAudioStoragePort,
    ) -> None:
        self._registry = registry
        self._tts = tts
        self._cache = cache
        self._storage = storage

    async def execute(self, dto: SynthesizeNpcDTO) -> AudioResultDTO:
        text = dto.text.strip()
        npc_name = dto.npc_name.strip()
        if not text:
            raise ValueError("empty_text")
        if not npc_name:
            raise ValueError("empty_npc_name")
        if len(text) > TEXT_MAX_LENGTH:
            raise ValueError("text_too_long")

        if dto.context and self._registry.get(dto.context) is not None:
            profile = self._registry.get(dto.context)
            ctx_used = dto.context
        else:
            profile = self._registry.select_npc_profile(npc_name, dto.npc_type)
            ctx_used = dto.npc_type or "auto"

        logger.info("NPC '%s': perfil '%s' stability=%.2f", npc_name, ctx_used, profile.stability)
        audio_url = await _synthesize_and_cache(text, profile, self._tts, self._cache, self._storage)
        return AudioResultDTO(audio_url=audio_url, context_used=ctx_used, voice_profile=profile.description)


class ListVoicesUseCase:
    def __init__(self, registry: VoiceProfileRegistry) -> None:
        self._registry = registry

    def execute(self) -> tuple[list[VoiceProfileDTO], dict[str, list[str]]]:
        profiles = [
            VoiceProfileDTO(
                name=name,
                voice_id=p.voice_id,
                stability=p.stability,
                similarity_boost=p.similarity_boost,
                style=p.style,
                speed=p.speed,
                description=p.description,
            )
            for name, p in self._registry.all().items()
        ]
        return profiles, CONTEXT_KEYWORDS
