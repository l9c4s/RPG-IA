"""ElevenLabs TTS adapter."""
from __future__ import annotations

import os

import httpx

from domain.voice.entity import VoiceProfile

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
MODEL_ID = "eleven_multilingual_v2"


class ElevenLabsService:
    """Calls the ElevenLabs v1 TTS API and returns raw MP3 bytes."""

    def __init__(self) -> None:
        self._api_key = os.getenv("ELEVENLABS_API_KEY", "")

    async def synthesize(self, text: str, profile: VoiceProfile) -> bytes:
        if not self._api_key:
            raise RuntimeError("Chave ELEVENLABS_API_KEY não configurada.")
        if not profile.voice_id:
            raise RuntimeError("voice_id não configurado para este perfil.")

        url = ELEVENLABS_TTS_URL.format(voice_id=profile.voice_id)
        body = {
            "text": text,
            "model_id": MODEL_ID,
            "voice_settings": {
                "stability": profile.stability,
                "similarity_boost": profile.similarity_boost,
                "style": profile.style,
                "use_speaker_boost": True,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                headers={
                    "xi-api-key": self._api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json=body,
            )

        if resp.status_code == 401:
            raise RuntimeError("Autenticação ElevenLabs falhou. Verifique ELEVENLABS_API_KEY.")
        if resp.status_code != 200:
            raise RuntimeError(f"Erro ElevenLabs: status {resp.status_code}.")

        return resp.content
