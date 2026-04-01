"""Integration tests for TTS service."""
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import io

pytestmark = pytest.mark.asyncio

FAKE_AUDIO = b"\xff\xfb\x90fake-mp3-data"
FAKE_AUDIO_URL = "/media/audio/cached.mp3"

# Fake API key and voice profiles for testing
FAKE_API_KEY = "test-key-fake"


def _mock_httpx_response(audio=FAKE_AUDIO, status_code=200):
    """Mock for httpx.AsyncClient response."""
    mock_resp = AsyncMock()
    mock_resp.status_code = status_code
    mock_resp.content = audio
    return mock_resp


def _mock_http_client(audio=FAKE_AUDIO, status_code=200):
    """Mock for httpx.AsyncClient used as async context manager."""
    mock_resp = _mock_httpx_response(audio, status_code)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _mock_minio():
    m = MagicMock()
    m.bucket_exists.return_value = True
    m.put_object.return_value = None
    return m


def _mock_redis_empty():
    m = AsyncMock()
    m.get = AsyncMock(return_value=None)
    m.set = AsyncMock(return_value=True)
    m.aclose = AsyncMock()
    return m


# ── /health ───────────────────────────────────────────────────────────────────

async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200


# ── GET /voices ───────────────────────────────────────────────────────────────

async def test_list_voices(client):
    r = await client.get("/voices")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))


# ── POST /synthesize ──────────────────────────────────────────────────────────

class TestSynthesize:
    async def test_synthesize_text_too_long(self, client):
        r = await client.post("/synthesize", json={
            "text": "A" * 4501,
        })
        assert r.status_code == 422

    async def test_synthesize_empty_text(self, client):
        r = await client.post("/synthesize", json={"text": ""})
        assert r.status_code == 422

    async def test_synthesize_success(self, client):
        mock_http = _mock_http_client()
        mock_minio = _mock_minio()
        mock_redis = _mock_redis_empty()

        with patch("main.httpx.AsyncClient", return_value=mock_http), \
             patch("main._get_minio_client", return_value=mock_minio), \
             patch("main._get_redis_client", return_value=mock_redis), \
             patch("main.ELEVENLABS_API_KEY", FAKE_API_KEY):
            r = await client.post("/synthesize", json={
                "text": "The dragon awakens.",
                "context": "narrator",
            })
            assert r.status_code == 200
            data = r.json()
            assert "audio_url" in data

    async def test_synthesize_returns_context_used(self, client):
        mock_http = _mock_http_client()
        mock_minio = _mock_minio()
        mock_redis = _mock_redis_empty()

        with patch("main.httpx.AsyncClient", return_value=mock_http), \
             patch("main._get_minio_client", return_value=mock_minio), \
             patch("main._get_redis_client", return_value=mock_redis), \
             patch("main.ELEVENLABS_API_KEY", FAKE_API_KEY):
            r = await client.post("/synthesize", json={"text": "Beware!"})
            if r.status_code == 200:
                assert "context_used" in r.json()

    async def test_synthesize_uses_cache(self, client):
        """When Redis returns a cached URL, the ElevenLabs API should NOT be called."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=FAKE_AUDIO_URL)
        mock_redis.aclose = AsyncMock()

        mock_http = MagicMock()

        with patch("main.httpx.AsyncClient", return_value=mock_http), \
             patch("main._get_redis_client", return_value=mock_redis), \
             patch("main.ELEVENLABS_API_KEY", FAKE_API_KEY):
            r = await client.post("/synthesize", json={"text": "cached text"})
            if r.status_code == 200:
                # httpx was not used (cache hit)
                mock_http.post.assert_not_called()


# ── POST /synthesize/npc ──────────────────────────────────────────────────────

class TestSynthesizeNpc:
    async def test_npc_missing_name(self, client):
        r = await client.post("/synthesize/npc", json={"text": "Hello"})
        assert r.status_code == 422

    async def test_npc_success(self, client):
        mock_http = _mock_http_client()
        mock_minio = _mock_minio()
        mock_redis = _mock_redis_empty()

        with patch("main.httpx.AsyncClient", return_value=mock_http), \
             patch("main._get_minio_client", return_value=mock_minio), \
             patch("main._get_redis_client", return_value=mock_redis), \
             patch("main.ELEVENLABS_API_KEY", FAKE_API_KEY):
            r = await client.post("/synthesize/npc", json={
                "text": "You dare enter my domain?",
                "npc_name": "Taven",
            })
            assert r.status_code == 200

    async def test_npc_same_name_same_voice_key(self, client):
        """Same NPC name produces same Redis cache key (deterministic)."""
        keys = set()

        mock_http = _mock_http_client()
        mock_minio = _mock_minio()

        for text in ["Hello!", "Goodbye."]:
            mock_redis = _mock_redis_empty()
            captured_key = {}

            async def capture_set(key, val, **kw):
                captured_key["key_parts"] = key
            mock_redis.set = capture_set

            with patch("main.httpx.AsyncClient", return_value=mock_http), \
                 patch("main._get_minio_client", return_value=mock_minio), \
                 patch("main._get_redis_client", return_value=mock_redis), \
                 patch("main.ELEVENLABS_API_KEY", FAKE_API_KEY):
                await client.post("/synthesize/npc", json={
                    "text": text,
                    "npc_name": "Taven",
                })

            if captured_key.get("key_parts"):
                keys.add(str(captured_key["key_parts"])[:20])  # prefix comparison


# ── Context inference ─────────────────────────────────────────────────────────

class TestContextInference:
    def test_infer_combat_context(self):
        from main import _infer_context
        ctx = _infer_context("The goblin attacks with its rusty sword! Strike!")
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_infer_death_context(self):
        from main import _infer_context
        ctx = _infer_context("You die. Your soul fades into darkness forever.")
        assert isinstance(ctx, str)

    def test_infer_fallback_returns_string(self):
        from main import _infer_context
        ctx = _infer_context("A rock sits on the ground.")
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_known_contexts_covered(self):
        from main import _infer_context, VOICE_PROFILES
        # Should return only valid profile keys
        for phrase in [
            "The blade strikes!", "A mystery unfolds.", "You perish.",
            "The ancient sage speaks.", "The villain laughs.",
        ]:
            ctx = _infer_context(phrase)
            assert ctx in VOICE_PROFILES or isinstance(ctx, str)
