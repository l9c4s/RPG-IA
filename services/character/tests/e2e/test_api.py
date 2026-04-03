"""E2E tests — full HTTP stack: ASGI client + real test database."""
import pytest

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


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    async def test_health_ok(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["service"] == "character"


# ---------------------------------------------------------------------------
# POST /characters
# ---------------------------------------------------------------------------


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
        data = full.json()
        assert "status" in data
        assert data["status"]["hp_current"] == 0
        assert data["status"]["conditions"] == []

    async def test_create_initializes_attributes(self, client):
        r = await client.post("/characters", json=CHARACTER_PAYLOAD)
        cid = r.json()["id"]
        full = await client.get(f"/characters/{cid}")
        data = full.json()
        assert "attributes" in data
        assert data["attributes"]["strength"] == 15
        assert data["attributes"]["dexterity"] == 14

    async def test_proficiency_bonus_level_1(self, client):
        r = await client.post("/characters", json=CHARACTER_PAYLOAD)
        assert r.json().get("proficiency_bonus") == 2

    async def test_proficiency_bonus_level_5(self, client):
        payload = {**CHARACTER_PAYLOAD, "level": 5}
        r = await client.post("/characters", json=payload)
        assert r.json().get("proficiency_bonus") == 3

    async def test_create_npc(self, client):
        payload = {**CHARACTER_PAYLOAD, "char_type": "npc", "name": "Innkeeper"}
        r = await client.post("/characters", json=payload)
        assert r.status_code == 201
        assert r.json()["char_type"] == "npc"

    async def test_create_ai_companion(self, client):
        payload = {**CHARACTER_PAYLOAD, "char_type": "ai_companion", "name": "Aria"}
        r = await client.post("/characters", json=payload)
        assert r.status_code == 201
        assert r.json()["char_type"] == "ai_companion"

    async def test_invalid_char_type_returns_422(self, client):
        r = await client.post("/characters", json={**CHARACTER_PAYLOAD, "char_type": "dragon"})
        assert r.status_code == 422

    async def test_level_out_of_range_returns_422(self, client):
        r = await client.post("/characters", json={**CHARACTER_PAYLOAD, "level": 21})
        assert r.status_code == 422

    async def test_missing_name_returns_422(self, client):
        payload = {k: v for k, v in CHARACTER_PAYLOAD.items() if k != "name"}
        r = await client.post("/characters", json=payload)
        assert r.status_code == 422

    async def test_missing_class_returns_422(self, client):
        payload = {k: v for k, v in CHARACTER_PAYLOAD.items() if k != "class"}
        r = await client.post("/characters", json=payload)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /characters/{id}
# ---------------------------------------------------------------------------


class TestGetCharacter:
    async def test_get_existing(self, client, created_character):
        cid = created_character["id"]
        r = await client.get(f"/characters/{cid}")
        assert r.status_code == 200
        assert r.json()["id"] == cid

    async def test_get_not_found(self, client):
        r = await client.get("/characters/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    async def test_get_returns_full_nested_data(self, client, created_character):
        cid = created_character["id"]
        r = await client.get(f"/characters/{cid}")
        data = r.json()
        assert "status" in data
        assert "attributes" in data
        assert "inventory" in data
        assert "abilities" in data


# ---------------------------------------------------------------------------
# PATCH /characters/{id}
# ---------------------------------------------------------------------------


class TestUpdateCharacter:
    async def test_update_name(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(f"/characters/{cid}", json={"name": "Strider"})
        assert r.status_code == 200
        assert r.json()["name"] == "Strider"

    async def test_update_alignment(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(f"/characters/{cid}", json={"alignment": "Chaotic Neutral"})
        assert r.status_code == 200
        assert r.json()["alignment"] == "Chaotic Neutral"

    async def test_update_not_found(self, client):
        r = await client.patch(
            "/characters/00000000-0000-0000-0000-000000000000", json={"name": "X"}
        )
        assert r.status_code == 404

    async def test_partial_update_preserves_other_fields(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(f"/characters/{cid}", json={"name": "Strider"})
        data = r.json()
        assert data["race"] == "Human"


# ---------------------------------------------------------------------------
# DELETE /characters/{id}
# ---------------------------------------------------------------------------


class TestDeleteCharacter:
    async def test_delete_returns_200(self, client, created_character):
        cid = created_character["id"]
        r = await client.delete(f"/characters/{cid}")
        assert r.status_code == 200
        assert "mensagem" in r.json()

    async def test_deleted_character_not_found(self, client, created_character):
        cid = created_character["id"]
        await client.delete(f"/characters/{cid}")
        r = await client.get(f"/characters/{cid}")
        assert r.status_code == 404

    async def test_delete_not_found(self, client):
        r = await client.delete("/characters/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /characters/{id}/status
# ---------------------------------------------------------------------------


class TestUpdateCharacterStatus:
    async def test_update_hp(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(f"/characters/{cid}/status", json={"hp_current": 5})
        assert r.status_code == 200
        assert r.json()["status"]["hp_current"] == 5

    async def test_update_hp_max(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(f"/characters/{cid}/status", json={"hp_max": 20})
        assert r.status_code == 200
        assert r.json()["status"]["hp_max"] == 20

    async def test_add_conditions(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(
            f"/characters/{cid}/status", json={"conditions": ["poisoned", "prone"]}
        )
        assert r.status_code == 200
        conditions = r.json()["status"]["conditions"]
        assert "poisoned" in conditions
        assert "prone" in conditions

    async def test_update_spell_slots(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(
            f"/characters/{cid}/status", json={"spell_slots": {"1": 4, "2": 2}}
        )
        assert r.status_code == 200
        slots = r.json()["status"]["spell_slots"]
        assert slots["1"] == 4

    async def test_exhaustion_above_max_returns_422(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(f"/characters/{cid}/status", json={"exhaustion": 7})
        assert r.status_code == 422

    async def test_death_saves_above_max_returns_422(self, client, created_character):
        cid = created_character["id"]
        r = await client.patch(
            f"/characters/{cid}/status", json={"death_saves_success": 4}
        )
        assert r.status_code == 422

    async def test_update_status_not_found(self, client):
        r = await client.patch(
            "/characters/00000000-0000-0000-0000-000000000000/status",
            json={"hp_current": 10},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /characters/{id}/levelup
# ---------------------------------------------------------------------------


class TestLevelUp:
    async def test_levelup_increments(self, client, created_character):
        cid = created_character["id"]
        r = await client.post(f"/characters/{cid}/levelup")
        assert r.status_code == 200
        assert r.json()["new_level"] == 2

    async def test_levelup_updates_proficiency_at_5(self, client, created_character):
        cid = created_character["id"]
        for _ in range(4):
            await client.post(f"/characters/{cid}/levelup")
        r = await client.post(f"/characters/{cid}/levelup")
        assert r.json()["new_proficiency_bonus"] == 3

    async def test_levelup_cap_at_20(self, client, created_character):
        cid = created_character["id"]
        for _ in range(19):
            await client.post(f"/characters/{cid}/levelup")
        r = await client.post(f"/characters/{cid}/levelup")
        assert r.status_code == 400

    async def test_levelup_message_contains_name(self, client, created_character):
        cid = created_character["id"]
        r = await client.post(f"/characters/{cid}/levelup")
        assert "Aragorn" in r.json()["message"]

    async def test_levelup_not_found(self, client):
        r = await client.post("/characters/00000000-0000-0000-0000-000000000000/levelup")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /campaigns/{id}/characters
# ---------------------------------------------------------------------------


class TestCampaignCharacters:
    async def test_list_campaign_characters(self, client, created_character):
        campaign_id = CHARACTER_PAYLOAD["campaign_id"]
        r = await client.get(f"/campaigns/{campaign_id}/characters")
        assert r.status_code == 200
        chars = r.json()
        assert isinstance(chars, list)
        assert any(c["id"] == created_character["id"] for c in chars)

    async def test_empty_campaign_returns_empty_list(self, client):
        r = await client.get("/campaigns/00000000-0000-0000-0000-000000000099/characters")
        assert r.status_code == 200
        assert r.json() == []

    async def test_deleted_not_in_list(self, client, created_character):
        cid = created_character["id"]
        campaign_id = CHARACTER_PAYLOAD["campaign_id"]
        await client.delete(f"/characters/{cid}")
        r = await client.get(f"/campaigns/{campaign_id}/characters")
        assert not any(c["id"] == cid for c in r.json())


# ---------------------------------------------------------------------------
# POST /characters/{id}/inventory
# ---------------------------------------------------------------------------


class TestInventory:
    async def test_add_item(self, client, created_character):
        cid = created_character["id"]
        r = await client.post(
            f"/characters/{cid}/inventory",
            json={"item_name": "Longsword", "item_type": "weapon", "quantity": 1},
        )
        assert r.status_code == 201
        assert r.json()["item_name"] == "Longsword"
        assert r.json()["character_id"] == cid

    async def test_add_item_defaults(self, client, created_character):
        cid = created_character["id"]
        r = await client.post(
            f"/characters/{cid}/inventory", json={"item_name": "Mysterious Pouch"}
        )
        assert r.status_code == 201
        data = r.json()
        assert data["item_type"] == "misc"
        assert data["quantity"] == 1
        assert data["equipped"] is False

    async def test_remove_item(self, client, created_character):
        cid = created_character["id"]
        add = await client.post(
            f"/characters/{cid}/inventory",
            json={"item_name": "Torch", "item_type": "gear", "quantity": 5},
        )
        item_id = add.json()["id"]
        r = await client.delete(f"/characters/{cid}/inventory/{item_id}")
        assert r.status_code == 200

    async def test_remove_item_not_found(self, client, created_character):
        cid = created_character["id"]
        r = await client.delete(
            f"/characters/{cid}/inventory/00000000-0000-0000-0000-000000000000"
        )
        assert r.status_code == 404

    async def test_add_item_character_not_found(self, client):
        r = await client.post(
            "/characters/00000000-0000-0000-0000-000000000000/inventory",
            json={"item_name": "Sword"},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /characters/{id}/abilities
# ---------------------------------------------------------------------------


class TestAbilities:
    async def test_add_feature(self, client, created_character):
        cid = created_character["id"]
        r = await client.post(
            f"/characters/{cid}/abilities",
            json={"ability_name": "Second Wind", "ability_type": "feature", "uses_max": 1},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["ability_name"] == "Second Wind"
        assert data["uses_remaining"] == 1

    async def test_add_spell_with_level(self, client, created_character):
        cid = created_character["id"]
        r = await client.post(
            f"/characters/{cid}/abilities",
            json={"ability_name": "Fireball", "ability_type": "spell", "spell_level": 3},
        )
        assert r.status_code == 201
        assert r.json()["spell_level"] == 3

    async def test_add_spell_without_level_returns_422(self, client, created_character):
        cid = created_character["id"]
        r = await client.post(
            f"/characters/{cid}/abilities",
            json={"ability_name": "Fireball", "ability_type": "spell"},
        )
        assert r.status_code == 422

    async def test_add_ability_invalid_type_returns_422(self, client, created_character):
        cid = created_character["id"]
        r = await client.post(
            f"/characters/{cid}/abilities",
            json={"ability_name": "X", "ability_type": "legendary"},
        )
        assert r.status_code == 422

    async def test_add_ability_character_not_found(self, client):
        r = await client.post(
            "/characters/00000000-0000-0000-0000-000000000000/abilities",
            json={"ability_name": "Rage", "ability_type": "feature"},
        )
        assert r.status_code == 404
