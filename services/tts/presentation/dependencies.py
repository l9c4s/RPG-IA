"""FastAPI dependency providers for the TTS service."""
from __future__ import annotations

from domain.voice.entity import VoiceProfileRegistry
from domain.voice.services import ContextInferenceService
from infrastructure.cache.redis_cache import RedisCache
from infrastructure.storage.minio_service import MinioAudioService
from infrastructure.tts.elevenlabs_service import ElevenLabsService

# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_tts = ElevenLabsService()
_cache = RedisCache()
_storage = MinioAudioService()
_inference = ContextInferenceService()
_registry: VoiceProfileRegistry | None = None


def init_registry() -> None:
    """Load voice profiles from environment variables. Called at startup."""
    global _registry
    _registry = VoiceProfileRegistry.load_from_env()


def get_tts() -> ElevenLabsService:
    return _tts


def get_cache() -> RedisCache:
    return _cache


def get_storage() -> MinioAudioService:
    return _storage


def get_inference() -> ContextInferenceService:
    return _inference


def get_registry() -> VoiceProfileRegistry:
    if _registry is None:
        raise RuntimeError("VoiceProfileRegistry not initialised — call init_registry() first.")
    return _registry
