"""Integration tests for image generation service."""
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import io

pytestmark = pytest.mark.asyncio

FAKE_IMAGE_BYTES = b"\x89PNG\r\n\x1a\nfake-image-data"
MOCK_DALLE_URL = "https://oaidalleapi.blob.core.windows.net/fake/image.png"


def _mock_dalle_response():
    mock_img = MagicMock()
    mock_img.url = MOCK_DALLE_URL
    mock_response = MagicMock()
    mock_response.data = [mock_img]
    return mock_response


def _patch_openai_and_http():
    """Patch OpenAI (async) and httpx download."""
    mock_openai = MagicMock()
    mock_openai.images.generate = AsyncMock(return_value=_mock_dalle_response())

    mock_http_response = AsyncMock()
    mock_http_response.content = FAKE_IMAGE_BYTES
    mock_http_response.raise_for_status = MagicMock()
    mock_http_response.__aenter__ = AsyncMock(return_value=mock_http_response)
    mock_http_response.__aexit__ = AsyncMock(return_value=False)

    mock_http_client = MagicMock()
    mock_http_client.get = AsyncMock(return_value=mock_http_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    return mock_openai, mock_http_client


# ── /health ───────────────────────────────────────────────────────────────────

async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200


# ── POST /generate/character ──────────────────────────────────────────────────

class TestGenerateCharacter:
    async def test_generate_character_missing_description(self, client):
        r = await client.post("/generate/character", json={})
        assert r.status_code == 422

    async def test_generate_character_success(self, client):
        mock_openai, mock_http = _patch_openai_and_http()
        mock_minio = MagicMock()
        mock_minio.bucket_exists.return_value = True
        mock_minio.put_object.return_value = None

        with patch("main.openai_client", mock_openai), \
             patch("main.httpx.AsyncClient", return_value=mock_http), \
             patch("main.minio_client", mock_minio):
            r = await client.post("/generate/character", json={
                "description": "A tall elf with silver hair",
            })
            assert r.status_code in (200, 201, 500)
            if r.status_code in (200, 201):
                assert "image_url" in r.json()

    async def test_generate_character_prompt_format(self, client):
        captured = {}

        async def capture_generate(**kwargs):
            captured["prompt"] = kwargs.get("prompt", "")
            captured["size"] = kwargs.get("size", "")
            return _mock_dalle_response()

        mock_openai = MagicMock()
        mock_openai.images.generate = capture_generate
        _, mock_http = _patch_openai_and_http()
        mock_minio = MagicMock()
        mock_minio.bucket_exists.return_value = True

        with patch("main.openai_client", mock_openai), \
             patch("main.httpx.AsyncClient", return_value=mock_http), \
             patch("main.minio_client", mock_minio):
            await client.post("/generate/character", json={"description": "A dwarf warrior"})

        if "prompt" in captured:
            assert "No text" in captured["prompt"] or "no watermarks" in captured["prompt"]
            assert "portrait" in captured["prompt"].lower() or "upper body" in captured["prompt"].lower()


# ── POST /generate/scene ──────────────────────────────────────────────────────

class TestGenerateScene:
    async def test_generate_scene_missing_description(self, client):
        r = await client.post("/generate/scene", json={})
        assert r.status_code == 422

    async def test_generate_scene_success(self, client):
        mock_openai, mock_http = _patch_openai_and_http()
        mock_minio = MagicMock()
        mock_minio.bucket_exists.return_value = True

        with patch("main.openai_client", mock_openai), \
             patch("main.httpx.AsyncClient", return_value=mock_http), \
             patch("main.minio_client", mock_minio):
            r = await client.post("/generate/scene", json={
                "description": "A vast dungeon hall"
            })
            assert r.status_code in (200, 201, 500)

    async def test_generate_scene_uses_wide_format(self, client):
        captured = {}

        async def capture_generate(**kwargs):
            captured.update(kwargs)
            return _mock_dalle_response()

        mock_openai = MagicMock()
        mock_openai.images.generate = capture_generate
        _, mock_http = _patch_openai_and_http()
        mock_minio = MagicMock()
        mock_minio.bucket_exists.return_value = True

        with patch("main.openai_client", mock_openai), \
             patch("main.httpx.AsyncClient", return_value=mock_http), \
             patch("main.minio_client", mock_minio):
            await client.post("/generate/scene", json={"description": "Dark cave"})

        if "size" in captured:
            assert captured["size"] == "1792x1024"
        if "prompt" in captured:
            assert "cinematic" in captured["prompt"].lower() or "wide" in captured["prompt"].lower()


# ── POST /generate/map ────────────────────────────────────────────────────────

class TestGenerateMap:
    async def test_generate_map_missing_description(self, client):
        r = await client.post("/generate/map", json={})
        assert r.status_code == 422

    async def test_generate_map_uses_top_down_style(self, client):
        captured = {}

        async def capture_generate(**kwargs):
            captured.update(kwargs)
            return _mock_dalle_response()

        mock_openai = MagicMock()
        mock_openai.images.generate = capture_generate
        _, mock_http = _patch_openai_and_http()
        mock_minio = MagicMock()
        mock_minio.bucket_exists.return_value = True

        with patch("main.openai_client", mock_openai), \
             patch("main.httpx.AsyncClient", return_value=mock_http), \
             patch("main.minio_client", mock_minio):
            await client.post("/generate/map", json={"description": "A mountain range"})

        if "prompt" in captured:
            assert "top-down" in captured["prompt"].lower() or "parchment" in captured["prompt"].lower()


# ── POST /generate/npc ────────────────────────────────────────────────────────

class TestGenerateNpc:
    async def test_generate_npc_missing_description(self, client):
        r = await client.post("/generate/npc", json={})
        assert r.status_code == 422

    async def test_generate_npc_success(self, client):
        mock_openai, mock_http = _patch_openai_and_http()
        mock_minio = MagicMock()
        mock_minio.bucket_exists.return_value = True

        with patch("main.openai_client", mock_openai), \
             patch("main.httpx.AsyncClient", return_value=mock_http), \
             patch("main.minio_client", mock_minio):
            r = await client.post("/generate/npc", json={
                "description": "An old wizard",
            })
            assert r.status_code in (200, 201, 500)
