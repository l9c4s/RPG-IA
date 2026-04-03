"""Unit tests for TTS use cases."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from application.tts.dtos import SynthesizeDTO, SynthesizeNpcDTO
from application.tts.use_cases import ListVoicesUseCase, SynthesizeNpcUseCase, SynthesizeUseCase
from domain.voice.entity import VoiceProfile, VoiceProfileRegistry
from domain.voice.services import ContextInferenceService

FAKE_VOICE_ID = "test-voice-id"
FAKE_AUDIO = b"\xff\xfb\x90fake"
FAKE_URL = "/media/rpg-audio/audio/abc.mp3"

_PROFILES = {
    ctx: VoiceProfile(voice_id=FAKE_VOICE_ID, description=f"desc-{ctx}")
    for ctx in ["narrator", "combat", "mystery", "epic", "tavern",
                "sage", "villain", "creature", "death", "triumph"]
}
REGISTRY = VoiceProfileRegistry(_PROFILES)


def _make_tts(audio=FAKE_AUDIO):
    m = AsyncMock()
    m.synthesize.return_value = audio
    return m


def _make_cache(cached_url=None):
    m = AsyncMock()
    m.get.return_value = cached_url
    m.set.return_value = None
    return m


def _make_storage(url=FAKE_URL):
    m = AsyncMock()
    m.upload.return_value = url
    return m


class TestSynthesizeUseCase:
    @pytest.fixture
    def inference(self):
        return ContextInferenceService()

    async def test_success_returns_audio_result(self, inference):
        use_case = SynthesizeUseCase(REGISTRY, _make_tts(), _make_cache(), _make_storage(), inference)
        result = await use_case.execute(SynthesizeDTO(text="The dragon roars.", context="narrator"))
        assert result.audio_url == FAKE_URL
        assert result.context_used == "narrator"

    async def test_infers_context_when_not_provided(self, inference):
        use_case = SynthesizeUseCase(REGISTRY, _make_tts(), _make_cache(), _make_storage(), inference)
        result = await use_case.execute(SynthesizeDTO(text="The goblin ataca!"))
        assert result.context_used in REGISTRY.available_contexts()

    async def test_empty_text_raises(self, inference):
        use_case = SynthesizeUseCase(REGISTRY, _make_tts(), _make_cache(), _make_storage(), inference)
        with pytest.raises(ValueError, match="empty_text"):
            await use_case.execute(SynthesizeDTO(text=""))

    async def test_text_too_long_raises(self, inference):
        use_case = SynthesizeUseCase(REGISTRY, _make_tts(), _make_cache(), _make_storage(), inference)
        with pytest.raises(ValueError, match="text_too_long"):
            await use_case.execute(SynthesizeDTO(text="x" * 4501))

    async def test_invalid_context_raises(self, inference):
        use_case = SynthesizeUseCase(REGISTRY, _make_tts(), _make_cache(), _make_storage(), inference)
        with pytest.raises(ValueError, match="invalid_context"):
            await use_case.execute(SynthesizeDTO(text="hello", context="unknown"))

    async def test_cache_hit_skips_tts(self, inference):
        tts = _make_tts()
        use_case = SynthesizeUseCase(REGISTRY, tts, _make_cache(FAKE_URL), _make_storage(), inference)
        result = await use_case.execute(SynthesizeDTO(text="cached text", context="narrator"))
        assert result.audio_url == FAKE_URL
        tts.synthesize.assert_not_called()

    async def test_voice_id_override_applied(self, inference):
        tts = _make_tts()
        use_case = SynthesizeUseCase(REGISTRY, tts, _make_cache(), _make_storage(), inference)
        await use_case.execute(SynthesizeDTO(text="hello", context="narrator", voice_id_override="custom-voice"))
        call_args = tts.synthesize.call_args
        profile_used = call_args[0][1]
        assert profile_used.voice_id == "custom-voice"


class TestSynthesizeNpcUseCase:
    async def test_success(self):
        use_case = SynthesizeNpcUseCase(REGISTRY, _make_tts(), _make_cache(), _make_storage())
        result = await use_case.execute(SynthesizeNpcDTO(text="Hello traveller!", npc_name="Trader"))
        assert result.audio_url == FAKE_URL

    async def test_empty_text_raises(self):
        use_case = SynthesizeNpcUseCase(REGISTRY, _make_tts(), _make_cache(), _make_storage())
        with pytest.raises(ValueError, match="empty_text"):
            await use_case.execute(SynthesizeNpcDTO(text="", npc_name="Bob"))

    async def test_empty_npc_name_raises(self):
        use_case = SynthesizeNpcUseCase(REGISTRY, _make_tts(), _make_cache(), _make_storage())
        with pytest.raises(ValueError, match="empty_npc_name"):
            await use_case.execute(SynthesizeNpcDTO(text="Hello", npc_name=""))

    async def test_npc_type_overrides_profile(self):
        tts = _make_tts()
        use_case = SynthesizeNpcUseCase(REGISTRY, tts, _make_cache(), _make_storage())
        result = await use_case.execute(SynthesizeNpcDTO(text="I am the villain!", npc_name="Sauron", npc_type="villain"))
        assert result.context_used == "villain"

    async def test_same_npc_deterministic(self):
        use_case = SynthesizeNpcUseCase(REGISTRY, _make_tts(), _make_cache(), _make_storage())
        r1 = await use_case.execute(SynthesizeNpcDTO(text="Hi", npc_name="Gandalf"))
        r2 = await use_case.execute(SynthesizeNpcDTO(text="Bye", npc_name="Gandalf"))
        assert r1.context_used == r2.context_used


class TestListVoicesUseCase:
    def test_returns_all_profiles(self):
        profiles, keywords = ListVoicesUseCase(REGISTRY).execute()
        assert len(profiles) == 10
        assert "combat" in keywords

    def test_profiles_have_correct_fields(self):
        profiles, _ = ListVoicesUseCase(REGISTRY).execute()
        for p in profiles:
            assert p.voice_id == FAKE_VOICE_ID
            assert p.name in REGISTRY.available_contexts()
