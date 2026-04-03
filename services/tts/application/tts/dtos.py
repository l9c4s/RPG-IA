"""Application DTOs for the TTS context."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SynthesizeDTO:
    text: str
    context: str | None = None
    voice_id_override: str | None = None


@dataclass(frozen=True)
class SynthesizeNpcDTO:
    text: str
    npc_name: str
    npc_type: str | None = None
    context: str | None = None


@dataclass(frozen=True)
class AudioResultDTO:
    audio_url: str
    context_used: str
    voice_profile: str


@dataclass(frozen=True)
class VoiceProfileDTO:
    name: str
    voice_id: str
    stability: float
    similarity_boost: float
    style: float
    speed: float
    description: str
