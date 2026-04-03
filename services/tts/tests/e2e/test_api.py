"""E2E tests — full HTTP stack with all external adapters mocked."""
import pytest

FAKE_AUDIO_URL = "/media/rpg-audio/audio/fake.mp3"


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class TestHealth:
    async def test_health_returns_ok(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["service"] == "tts"
        assert "profiles_configured" in data


# ---------------------------------------------------------------------------
# GET /voices
# ---------------------------------------------------------------------------


class TestListVoices:
    async def test_returns_200(self, client):
        r = await client.get("/voices")
        assert r.status_code == 200

    async def test_has_profiles_and_keywords(self, client):
        r = await client.get("/voices")
        data = r.json()
        assert "profiles" in data
        assert "inference_keywords" in data

    async def test_all_10_contexts_present(self, client):
        r = await client.get("/voices")
        profiles = r.json()["profiles"]
        for ctx in ["narrator", "combat", "mystery", "epic", "tavern",
                    "sage", "villain", "creature", "death", "triumph"]:
            assert ctx in profiles


# ---------------------------------------------------------------------------
# POST /synthesize
# ---------------------------------------------------------------------------


class TestSynthesize:
    async def test_success_returns_200(self, client):
        r = await client.post("/synthesize", json={"text": "The dragon roars.", "context": "narrator"})
        assert r.status_code == 200
        data = r.json()
        assert "audio_url" in data
        assert "context_used" in data
        assert "voice_profile" in data

    async def test_audio_url_returned(self, client):
        r = await client.post("/synthesize", json={"text": "Hello, adventurer!"})
        assert r.status_code == 200
        assert r.json()["audio_url"] == FAKE_AUDIO_URL

    async def test_context_used_matches_request(self, client):
        r = await client.post("/synthesize", json={"text": "Enter the dungeon.", "context": "mystery"})
        assert r.status_code == 200
        assert r.json()["context_used"] == "mystery"

    async def test_empty_text_422(self, client):
        r = await client.post("/synthesize", json={"text": ""})
        assert r.status_code == 422

    async def test_text_too_long_422(self, client):
        r = await client.post("/synthesize", json={"text": "x" * 4501})
        assert r.status_code == 422

    async def test_invalid_context_422(self, client):
        r = await client.post("/synthesize", json={"text": "Hello", "context": "unknown_ctx"})
        assert r.status_code == 422

    async def test_all_valid_contexts_accepted(self, client):
        for ctx in ["narrator", "combat", "mystery", "epic", "tavern",
                    "sage", "villain", "creature", "death", "triumph"]:
            r = await client.post("/synthesize", json={"text": "Test narration.", "context": ctx})
            assert r.status_code == 200, f"Context '{ctx}' failed: {r.json()}"

    async def test_no_context_infers_automatically(self, client):
        r = await client.post("/synthesize", json={"text": "The goblin ataca com a espada!"})
        assert r.status_code == 200
        assert r.json()["context_used"] in [
            "narrator", "combat", "mystery", "epic", "tavern",
            "sage", "villain", "creature", "death", "triumph",
        ]

    async def test_voice_id_override_accepted(self, client):
        r = await client.post("/synthesize", json={
            "text": "Override test.",
            "context": "narrator",
            "voice_id_override": "custom-voice-xyz",
        })
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /synthesize/npc
# ---------------------------------------------------------------------------


class TestSynthesizeNpc:
    async def test_success_returns_200(self, client):
        r = await client.post("/synthesize/npc", json={
            "text": "You dare enter my domain?",
            "npc_name": "Taven the Dark",
        })
        assert r.status_code == 200
        data = r.json()
        assert "audio_url" in data

    async def test_missing_npc_name_422(self, client):
        r = await client.post("/synthesize/npc", json={"text": "Hello"})
        assert r.status_code == 422

    async def test_empty_text_422(self, client):
        r = await client.post("/synthesize/npc", json={"text": "", "npc_name": "Bob"})
        assert r.status_code == 422

    async def test_with_npc_type(self, client):
        r = await client.post("/synthesize/npc", json={
            "text": "I am the villain.",
            "npc_name": "Sauron",
            "npc_type": "villain",
        })
        assert r.status_code == 200
        assert r.json()["context_used"] == "villain"

    async def test_with_context_override(self, client):
        r = await client.post("/synthesize/npc", json={
            "text": "This is an epic moment!",
            "npc_name": "Gandalf",
            "context": "epic",
        })
        assert r.status_code == 200
        assert r.json()["context_used"] == "epic"
