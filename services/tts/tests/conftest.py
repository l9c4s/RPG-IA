import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, patch, AsyncMock

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import main as main_module
from main import app, _load_profiles, VoiceProfile

FAKE_VOICE_ID = "test-voice-id-0000"

_TEST_PROFILES = {
    name: VoiceProfile(voice_id=FAKE_VOICE_ID, stability=0.5, similarity_boost=0.75,
                       style=0.0, speed=1.0, description=f"test profile {name}")
    for name in ["narrator", "combat", "mystery", "epic", "tavern",
                 "sage", "villain", "creature", "death", "triumph"]
}


@pytest_asyncio.fixture(scope="function")
async def client():
    # Startup event does NOT run with ASGITransport — pre-populate with test profiles
    main_module.VOICE_PROFILES = _TEST_PROFILES.copy()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()

    mock_minio = MagicMock()
    mock_minio.bucket_exists.return_value = True
    mock_minio.put_object.return_value = None

    with patch("main._get_redis_client", return_value=mock_redis), \
         patch("main._get_minio_client", return_value=mock_minio):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
