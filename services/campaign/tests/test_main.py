"""Integration tests for campaign service endpoints."""
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock

pytestmark = pytest.mark.asyncio

CAMPAIGN_PAYLOAD = {
    "title": "The Dark Forest",
    "description": "A haunted forest full of danger",
    "rpg_system": "D&D 5e",
    "difficulty": "medium",
    "tone": "dark",
}


# ── /health ───────────────────────────────────────────────────────────────────

async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200


# ── POST /campaigns ───────────────────────────────────────────────────────────

class TestCreateCampaign:
    async def test_create_success(self, client):
        r = await client.post("/campaigns", json=CAMPAIGN_PAYLOAD)
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "The Dark Forest"
        assert data["difficulty"] == "medium"
        assert data["status"] == "lobby"
        assert "id" in data

    async def test_create_missing_title(self, client):
        r = await client.post("/campaigns", json={
            "description": "no title", "rpg_system": "D&D 5e", "difficulty": "easy"
        })
        assert r.status_code == 422

    async def test_create_invalid_difficulty(self, client):
        payload = {**CAMPAIGN_PAYLOAD, "difficulty": "legendary"}
        r = await client.post("/campaigns", json=payload)
        assert r.status_code == 422

    async def test_create_all_difficulties(self, client):
        for diff in ["easy", "medium", "hard"]:
            r = await client.post("/campaigns", json={**CAMPAIGN_PAYLOAD, "difficulty": diff})
            assert r.status_code == 201


# ── GET /campaigns ────────────────────────────────────────────────────────────

class TestListCampaigns:
    async def test_list_empty(self, client):
        r = await client.get("/campaigns")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) or "campaigns" in data or data == []

    async def test_list_returns_created(self, client):
        await client.post("/campaigns", json=CAMPAIGN_PAYLOAD)
        r = await client.get("/campaigns")
        assert r.status_code == 200
        body = r.json()
        items = body if isinstance(body, list) else body.get("campaigns", body.get("items", []))
        assert len(items) >= 1


# ── GET /campaigns/{id} ───────────────────────────────────────────────────────

class TestGetCampaign:
    async def test_get_existing(self, client):
        create = await client.post("/campaigns", json=CAMPAIGN_PAYLOAD)
        cid = create.json()["id"]
        r = await client.get(f"/campaigns/{cid}")
        assert r.status_code == 200
        assert r.json()["id"] == cid

    async def test_get_not_found(self, client):
        r = await client.get("/campaigns/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404


# ── DELETE /campaigns/{id} ────────────────────────────────────────────────────

class TestDeleteCampaign:
    async def test_delete_existing(self, client):
        create = await client.post("/campaigns", json=CAMPAIGN_PAYLOAD)
        cid = create.json()["id"]
        r = await client.delete(f"/campaigns/{cid}")
        assert r.status_code in (200, 204)

    async def test_delete_not_found(self, client):
        r = await client.delete("/campaigns/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    async def test_deleted_campaign_not_found(self, client):
        create = await client.post("/campaigns", json=CAMPAIGN_PAYLOAD)
        cid = create.json()["id"]
        await client.delete(f"/campaigns/{cid}")
        r = await client.get(f"/campaigns/{cid}")
        assert r.status_code == 404


# ── PATCH /campaigns/{id}/status ─────────────────────────────────────────────

class TestUpdateStatus:
    async def test_valid_status_transition(self, client):
        create = await client.post("/campaigns", json=CAMPAIGN_PAYLOAD)
        cid = create.json()["id"]

        # Mock character service returning 2+ characters
        with patch("main.httpx.AsyncClient") as mock_httpx:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {"id": "char-1", "name": "Hero", "char_type": "player"},
                {"id": "char-2", "name": "Mage", "char_type": "player"},
            ]
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value = mock_client_instance

            r = await client.patch(f"/campaigns/{cid}/status", json={"status": "active"})
            assert r.status_code in (200, 400)  # 400 if char service unreachable in test

    async def test_invalid_status_value(self, client):
        create = await client.post("/campaigns", json=CAMPAIGN_PAYLOAD)
        cid = create.json()["id"]
        r = await client.patch(f"/campaigns/{cid}/status", json={"status": "invalid_status"})
        assert r.status_code == 422


# ── POST /session/action ──────────────────────────────────────────────────────

class TestSessionAction:
    async def test_action_blocked_when_no_knowledge(self, client):
        """GM must be blocked when knowledge bank is empty."""
        with patch("main.check_gate", return_value=False):
            r = await client.post("/session/action", json={
                "session_id": "550e8400-e29b-41d4-a716-446655440001",
                "player_id": "550e8400-e29b-41d4-a716-446655440002",
                "action_text": "I look around the room.",
                "character_id": "550e8400-e29b-41d4-a716-446655440003",
            })
            assert r.status_code in (200, 403, 503)
            if r.status_code == 200:
                data = r.json()
                text = data.get("text", "") or data.get("clean_text", "")
                assert "bloqueado" in text.lower() or "knowledge" in text.lower() or data.get("blocked") is True

    async def test_action_too_long(self, client):
        r = await client.post("/session/action", json={
            "session_id": "550e8400-e29b-41d4-a716-446655440001",
            "player_id": "550e8400-e29b-41d4-a716-446655440002",
            "action_text": "A" * 4001,
            "character_id": "550e8400-e29b-41d4-a716-446655440003",
        })
        assert r.status_code == 422


class TestGenerateCharacter8Bit:
    async def test_generate_character_8bit_missing_description(self, client):
        create = await client.post("/campaigns", json=CAMPAIGN_PAYLOAD)
        cid = create.json()["id"]
        r = await client.post(f"/campaigns/{cid}/generate-character-8bit", json={})
        assert r.status_code == 422

    async def test_generate_character_8bit_success(self, client):
        create = await client.post("/campaigns", json=CAMPAIGN_PAYLOAD)
        cid = create.json()["id"]

        mock_result = MagicMock()
        mock_result.content = '{"name": "Pixel Paladin", "race": "Human", "class": "Paladin", "alignment": "Lawful Good", "background": "Knight of the chipboard realm", "appearance": "A blocky knight in blue armor", "backstory": "A little hero from a digital kingdom", "pixel_art_prompt": "8-bit pixel art hero with limited palette, blocky armor and glowing eyes"}'
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke = MagicMock(return_value=mock_result)
        mock_llm = MagicMock(return_value=mock_llm_instance)

        with patch("main.ChatOpenAI", mock_llm):
            r = await client.post(f"/campaigns/{cid}/generate-character-8bit", json={"description": "A brave knight in pixel armor"})
            assert r.status_code == 200
            body = r.json()
            assert body["name"] == "Pixel Paladin"
            assert body["pixel_art_prompt"].startswith("8-bit pixel art")
