"""Shared fixtures for all test layers."""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from domain.voice.entity import VoiceProfile, VoiceProfileRegistry
from presentation.dependencies import get_cache, get_registry, get_storage, get_tts, get_inference
from presentation.main import create_app

FAKE_VOICE_ID = "test-voice-id-0000"
FAKE_AUDIO = b"\xff\xfb\x90fake-mp3-data"
FAKE_AUDIO_URL = "/media/rpg-audio/audio/fake.mp3"

# ---------------------------------------------------------------------------
# Test registry — all 10 profiles with a predictable fake voice_id
# ---------------------------------------------------------------------------

_ALL_CONTEXTS = [
    "narrator", "combat", "mystery", "epic", "tavern",
    "sage", "villain", "creature", "death", "triumph",
]

_TEST_PROFILES = {
    ctx: VoiceProfile(
        voice_id=FAKE_VOICE_ID,
        stability=0.5,
        similarity_boost=0.75,
        style=0.0,
        speed=1.0,
        description=f"test profile {ctx}",
    )
    for ctx in _ALL_CONTEXTS
}

TEST_REGISTRY = VoiceProfileRegistry(_TEST_PROFILES)


# ---------------------------------------------------------------------------
# Fake adapters
# ---------------------------------------------------------------------------


def _fake_tts():
    mock = AsyncMock()
    mock.synthesize.return_value = FAKE_AUDIO
    return mock


def _fake_cache():
    mock = AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = None
    return mock


def _fake_storage():
    mock = AsyncMock()
    mock.upload.return_value = FAKE_AUDIO_URL
    mock.ensure_bucket.return_value = None
    return mock


# ---------------------------------------------------------------------------
# HTTP client (E2E)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def client():
    app = create_app()
    app.dependency_overrides[get_registry] = lambda: TEST_REGISTRY
    app.dependency_overrides[get_tts] = _fake_tts
    app.dependency_overrides[get_cache] = _fake_cache
    app.dependency_overrides[get_storage] = _fake_storage

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
