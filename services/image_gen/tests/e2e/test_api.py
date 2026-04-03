"""E2E tests — full HTTP stack with DALL-E and MinIO mocked."""
import pytest

_FAKE_BYTES = b"\x89PNG\r\n\x1a\n"
_FAKE_URL = "/media/images/fake-image.png"


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class TestHealth:
    async def test_health_returns_ok(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["service"] == "image_gen"


# ---------------------------------------------------------------------------
# POST /generate/character
# ---------------------------------------------------------------------------


class TestGenerateCharacter:
    async def test_success_returns_201(self, client):
        r = await client.post("/generate/character", json={"description": "a brave knight"})
        assert r.status_code == 201
        data = r.json()
        assert "image_url" in data
        assert "image_id" in data
        assert data["image_type"] == "character"

    async def test_with_character_and_campaign_ids(self, client):
        from uuid import uuid4
        r = await client.post("/generate/character", json={
            "description": "an elven ranger",
            "character_id": str(uuid4()),
            "campaign_id": str(uuid4()),
        })
        assert r.status_code == 201

    async def test_empty_description_422(self, client):
        r = await client.post("/generate/character", json={"description": ""})
        assert r.status_code == 422

    async def test_description_too_long_422(self, client):
        r = await client.post("/generate/character", json={"description": "x" * 2001})
        assert r.status_code == 422

    async def test_missing_description_422(self, client):
        r = await client.post("/generate/character", json={})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /generate/npc
# ---------------------------------------------------------------------------


class TestGenerateNpc:
    async def test_success_returns_201(self, client):
        r = await client.post("/generate/npc", json={"description": "a suspicious merchant"})
        assert r.status_code == 201
        assert r.json()["image_type"] == "npc"


# ---------------------------------------------------------------------------
# POST /generate/scene
# ---------------------------------------------------------------------------


class TestGenerateScene:
    async def test_success_returns_201(self, client):
        r = await client.post("/generate/scene", json={"description": "a dark dungeon corridor"})
        assert r.status_code == 201
        assert r.json()["image_type"] == "scene"

    async def test_with_campaign_id(self, client):
        from uuid import uuid4
        r = await client.post("/generate/scene", json={
            "description": "an epic battle",
            "campaign_id": str(uuid4()),
        })
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# POST /generate/map
# ---------------------------------------------------------------------------


class TestGenerateMap:
    async def test_success_returns_201(self, client):
        r = await client.post("/generate/map", json={"description": "a coastal city"})
        assert r.status_code == 201
        assert r.json()["image_type"] == "map"

    async def test_with_location_id(self, client):
        from uuid import uuid4
        r = await client.post("/generate/map", json={
            "description": "a mountain fortress",
            "location_id": str(uuid4()),
        })
        assert r.status_code == 201
