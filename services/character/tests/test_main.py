"""Integration tests for character service."""
import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

CHARACTER_PAYLOAD = {
    "name": "Aragorn",
    "race": "Human",
    "class": "Ranger",
    "level": 1,
    "char_type": "player",
    "alignment": "Lawful Good",
    "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
    "owner_id": "550e8400-e29b-41d4-a716-446655440099",
    "attributes": {
        "strength": 15,
        "dexterity": 14,
        "constitution": 13,
        "intelligence": 12,
        "wisdom": 10,
        "charisma": 8,
        "armor_class": 12,
        "initiative": 2,
        "speed": 30,
    },
}


# ── /health ───────────────────────────────────────────────────────────────────

async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200


# ── POST /characters ──────────────────────────────────────────────────────────

class TestCreateCharacter:
    async def test_create_player_character(self, client):
        r = await client.post("/characters", json=CHARACTER_PAYLOAD)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Aragorn"
        assert data["race"] == "Human"
        assert "id" in data

    async def test_create_initializes_status(self, client):
        r = await client.post("/characters", json=CHARACTER_PAYLOAD)
        assert r.status_code == 201
        cid = r.json()["id"]
        full = await client.get(f"/characters/{cid}")
        assert full.status_code == 200
        data = full.json()
        assert "status" in data
        assert data["status"]["hp_current"] >= 0

    async def test_create_initializes_attributes(self, client):
        r = await client.post("/characters", json=CHARACTER_PAYLOAD)
        cid = r.json()["id"]
        full = await client.get(f"/characters/{cid}")
        data = full.json()
        assert "attributes" in data
        assert data["attributes"]["strength"] == 15

    async def test_create_ai_companion(self, client):
        payload = {**CHARACTER_PAYLOAD, "char_type": "ai_companion", "name": "Aria"}
        r = await client.post("/characters", json=payload)
        assert r.status_code == 201
        assert r.json()["char_type"] == "ai_companion"

    async def test_create_invalid_char_type(self, client):
        payload = {**CHARACTER_PAYLOAD, "char_type": "dragon"}
        r = await client.post("/characters", json=payload)
        assert r.status_code == 422

    async def test_create_level_out_of_range(self, client):
        r = await client.post("/characters", json={**CHARACTER_PAYLOAD, "level": 21})
        assert r.status_code == 422

    async def test_create_missing_name(self, client):
        payload = {k: v for k, v in CHARACTER_PAYLOAD.items() if k != "name"}
        r = await client.post("/characters", json=payload)
        assert r.status_code == 422

    async def test_proficiency_bonus_level_1(self, client):
        r = await client.post("/characters", json=CHARACTER_PAYLOAD)
        data = r.json()
        assert data.get("proficiency_bonus") == 2


# ── GET /characters/{id} ──────────────────────────────────────────────────────

class TestGetCharacter:
    async def test_get_existing(self, client, created_character):
        cid = created_character["id"]
        r = await client.get(f"/characters/{cid}")
        assert r.status_code == 200
        assert r.json()["id"] == cid

    async def test_get_not_found(self, client):
        r = await client.get("/characters/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404


# ── PATCH /characters/{id} ────────────────────────────────────────────────────

class TestUpdateCharacter:
    async def test_update_name(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(f"/characters/{cid}", json={"name": "Strider"})
        assert r.status_code == 200
        assert r.json()["name"] == "Strider"

    async def test_update_not_found(self, client):
        r = await client.patch("/characters/00000000-0000-0000-0000-000000000000", json={"name": "X"})
        assert r.status_code == 404


# ── DELETE /characters/{id} ───────────────────────────────────────────────────

class TestDeleteCharacter:
    async def test_delete_marks_dead(self, client, created_character):
        cid = created_character["id"]
        r = await client.delete(f"/characters/{cid}")
        assert r.status_code in (200, 204)

    async def test_delete_not_found(self, client):
        r = await client.delete("/characters/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404


# ── PATCH /characters/{id}/status ────────────────────────────────────────────

class TestUpdateStatus:
    async def test_update_hp(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(f"/characters/{cid}/status", json={"hp_current": 5})
        assert r.status_code == 200
        data = r.json()
        assert data["status"]["hp_current"] == 5

    async def test_add_condition(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(f"/characters/{cid}/status", json={"conditions": ["poisoned"]})
        assert r.status_code == 200
        assert "poisoned" in r.json()["status"]["conditions"]

    async def test_update_exhaustion_max(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(f"/characters/{cid}/status", json={"exhaustion": 7})
        assert r.status_code == 422  # max is 6


# ── POST /characters/{id}/levelup ─────────────────────────────────────────────

class TestLevelUp:
    async def test_levelup_increments(self, client, created_character):
        cid = created_character["id"]
        r = await client.post(f"/characters/{cid}/levelup")
        assert r.status_code == 200
        assert r.json()["new_level"] == 2

    async def test_levelup_updates_proficiency(self, client, created_character):
        cid = created_character["id"]
        # Level 5 = proficiency +3
        for _ in range(4):
            await client.post(f"/characters/{cid}/levelup")
        r = await client.post(f"/characters/{cid}/levelup")
        assert r.json()["new_proficiency_bonus"] == 3

    async def test_levelup_cap_at_20(self, client, created_character):
        cid = created_character["id"]
        for _ in range(19):
            await client.post(f"/characters/{cid}/levelup")
        # One more should fail or stay at 20
        r = await client.post(f"/characters/{cid}/levelup")
        assert r.status_code in (200, 400)
        if r.status_code == 200:
            assert r.json()["new_level"] == 20


# ── GET /campaigns/{id}/characters ───────────────────────────────────────────

class TestCampaignCharacters:
    async def test_list_campaign_characters(self, client, created_character):
        campaign_id = CHARACTER_PAYLOAD["campaign_id"]
        r = await client.get(f"/campaigns/{campaign_id}/characters")
        assert r.status_code == 200
        chars = r.json()
        assert isinstance(chars, list)
        assert any(c["id"] == created_character["id"] for c in chars)

    async def test_empty_campaign(self, client):
        r = await client.get("/campaigns/00000000-0000-0000-0000-000000000099/characters")
        assert r.status_code == 200
        assert r.json() == []


# ── POST /characters/{id}/inventory ──────────────────────────────────────────

class TestInventory:
    async def test_add_item(self, client, created_character):
        cid = created_character["id"]
        r = await client.post(f"/characters/{cid}/inventory", json={
            "item_name": "Longsword",
            "item_type": "weapon",
            "quantity": 1,
        })
        assert r.status_code == 201
        assert r.json()["item_name"] == "Longsword"

    async def test_remove_item(self, client, created_character):
        cid = created_character["id"]
        add = await client.post(f"/characters/{cid}/inventory", json={
            "item_name": "Torch", "item_type": "gear", "quantity": 5
        })
        item_id = add.json()["id"]
        r = await client.delete(f"/characters/{cid}/inventory/{item_id}")
        assert r.status_code in (200, 204)
