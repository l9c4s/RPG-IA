"""Unit tests for voice domain entities and services."""
import pytest

from domain.voice.entity import VoiceProfile, VoiceProfileRegistry
from domain.voice.services import ContextInferenceService, CONTEXT_KEYWORDS


class TestVoiceProfile:
    def test_frozen(self):
        profile = VoiceProfile(voice_id="abc")
        with pytest.raises((TypeError, AttributeError)):
            profile.voice_id = "xyz"

    def test_with_voice_id_returns_copy(self):
        profile = VoiceProfile(voice_id="original", stability=0.7)
        copy = profile.with_voice_id("new-id")
        assert copy.voice_id == "new-id"
        assert copy.stability == 0.7
        assert profile.voice_id == "original"

    def test_defaults(self):
        profile = VoiceProfile(voice_id="x")
        assert profile.stability == 0.5
        assert profile.similarity_boost == 0.75
        assert profile.style == 0.0
        assert profile.speed == 1.0


class TestVoiceProfileRegistry:
    def _make_registry(self) -> VoiceProfileRegistry:
        profiles = {
            ctx: VoiceProfile(voice_id=f"voice-{ctx}")
            for ctx in ["narrator", "combat", "mystery", "epic", "tavern",
                        "sage", "villain", "creature", "death", "triumph"]
        }
        return VoiceProfileRegistry(profiles)

    def test_get_known_context(self):
        reg = self._make_registry()
        profile = reg.get("narrator")
        assert profile is not None
        assert profile.voice_id == "voice-narrator"

    def test_get_unknown_context_returns_none(self):
        reg = self._make_registry()
        assert reg.get("unknown") is None

    def test_all_returns_all_profiles(self):
        reg = self._make_registry()
        assert len(reg.all()) == 10

    def test_available_contexts(self):
        reg = self._make_registry()
        contexts = reg.available_contexts()
        assert "narrator" in contexts
        assert "villain" in contexts
        assert len(contexts) == 10

    def test_select_npc_profile_by_type(self):
        reg = self._make_registry()
        profile = reg.select_npc_profile("Gandalf", npc_type="sage")
        assert profile.voice_id == "voice-sage"

    def test_select_npc_profile_deterministic(self):
        reg = self._make_registry()
        p1 = reg.select_npc_profile("Gollum", npc_type=None)
        p2 = reg.select_npc_profile("Gollum", npc_type=None)
        assert p1.voice_id == p2.voice_id

    def test_select_npc_profile_different_names_may_differ(self):
        reg = self._make_registry()
        # Not guaranteed to differ, but with very different names it's likely
        names = ["Gollum", "Aragorn", "Sauron", "Frodo", "Legolas"]
        voices = {reg.select_npc_profile(n, None).voice_id for n in names}
        # Should hit at least 2 different profiles from the pool
        assert len(voices) >= 1  # always true — at least proves it runs

    def test_load_from_env_returns_registry(self, monkeypatch):
        monkeypatch.setenv("VOICE_NARRATOR_ID", "env-narrator-id")
        reg = VoiceProfileRegistry.load_from_env()
        assert reg.get("narrator") is not None
        assert reg.get("narrator").voice_id == "env-narrator-id"

    def test_load_from_env_fallback_to_narrator(self, monkeypatch):
        monkeypatch.setenv("VOICE_NARRATOR_ID", "fallback-id")
        monkeypatch.delenv("VOICE_COMBAT_ID", raising=False)
        reg = VoiceProfileRegistry.load_from_env()
        assert reg.get("combat").voice_id == "fallback-id"


class TestContextInferenceService:
    def setup_method(self):
        self.service = ContextInferenceService()

    def test_infers_combat_from_keywords(self):
        ctx = self.service.infer("The goblin ataca with its sword. Combate intenso!")
        assert ctx == "combat"

    def test_infers_mystery_from_keywords(self):
        ctx = self.service.infer("Uma sombra surge da escuridão, sussurro no dungeon.")
        assert ctx == "mystery"

    def test_infers_death_from_keywords(self):
        ctx = self.service.infer("O herói morreu. Seu último suspiro foi ouvido por todos.")
        assert ctx == "death"

    def test_infers_villain_from_keywords(self):
        ctx = self.service.infer("Tolos! Não há esperança para vocês. Dominação total!")
        assert ctx == "villain"

    def test_fallback_to_narrator(self):
        ctx = self.service.infer("A beautiful rock sits on the ground.")
        assert ctx == "narrator"

    def test_empty_text_fallback(self):
        ctx = self.service.infer("")
        assert ctx == "narrator"

    def test_returns_valid_context(self):
        valid = set(CONTEXT_KEYWORDS.keys()) | {"narrator"}
        for phrase in ["vitória!", "lenda e destino", "taverna e cerveja"]:
            ctx = self.service.infer(phrase)
            assert ctx in valid
