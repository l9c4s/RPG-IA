"""Pydantic v2 HTTP schemas for the TTS service."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SynthesizeRequest(BaseModel):
    text: str
    context: str | None = None
    voice_id_override: str | None = None


class SynthesizeNpcRequest(BaseModel):
    text: str
    npc_name: str
    npc_type: str | None = None
    context: str | None = None


class AudioResponse(BaseModel):
    audio_url: str
    context_used: str
    voice_profile: str


class VoiceProfileInfo(BaseModel):
    name: str
    voice_id: str
    stability: float
    similarity_boost: float
    style: float
    speed: float
    description: str


class VoicesResponse(BaseModel):
    profiles: dict[str, VoiceProfileInfo]
    inference_keywords: dict[str, list[str]]
