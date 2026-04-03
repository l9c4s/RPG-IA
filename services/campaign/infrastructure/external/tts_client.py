"""
Cliente HTTP para o serviço de síntese de voz (ElevenLabs via tts_service).
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

TTS_SERVICE_URL: str = os.getenv("TTS_SERVICE_URL", "http://tts_service:8005")


class TTSClient:
    """Envia texto para geração de áudio e retorna a URL do arquivo gerado."""

    async def synthesize(self, text: str, session_id: str) -> str | None:
        """
        Solicita síntese de voz para o texto fornecido.
        Retorna a URL do áudio ou None em caso de falha.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{TTS_SERVICE_URL}/tts/generate",
                    json={"text": text, "session_id": session_id},
                )
                if resp.status_code == 200:
                    return resp.json().get("audio_url")
        except Exception as exc:
            logger.warning("TTS dispatch falhou: %s", exc)
        return None
