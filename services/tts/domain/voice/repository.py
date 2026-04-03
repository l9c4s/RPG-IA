"""Port interfaces for the voice/TTS domain."""
from __future__ import annotations

from typing import Protocol

from .entity import VoiceProfile


class ITtsPort(Protocol):
    """Calls the external TTS API and returns raw audio bytes."""

    async def synthesize(self, text: str, profile: VoiceProfile) -> bytes: ...


class ICachePort(Protocol):
    """Read-through audio URL cache (Redis)."""

    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int) -> None: ...


class IAudioStoragePort(Protocol):
    """Stores synthesised audio files (MinIO)."""

    async def upload(self, object_name: str, data: bytes) -> str: ...
    async def ensure_bucket(self) -> None: ...
