"""
Cliente HTTP para o serviço de geração de imagens (DALL·E 3 via image_service).
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

IMAGE_SERVICE_URL: str = os.getenv("IMAGE_SERVICE_URL", "http://image_service:8004")
CHARACTER_SERVICE_URL: str = os.getenv("CHARACTER_SERVICE_URL", "http://character_service:8003")


class ImageClient:
    """Envia prompt de cena para geração de imagem e retorna a URL."""

    async def generate_scene(self, description: str, session_id: str) -> str | None:
        """
        Solicita geração de imagem de cena via DALL·E 3.
        Retorna a URL da imagem ou None em caso de falha.
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{IMAGE_SERVICE_URL}/images/generate",
                    json={"description": description, "session_id": session_id},
                )
                if resp.status_code == 200:
                    return resp.json().get("image_url")
        except Exception as exc:
            logger.warning("Image generation dispatch falhou: %s", exc)
        return None

    async def generate_character_image(
        self,
        description: str,
        character_id: str,
        campaign_id: str,
        style: str = "pixel_art",
    ) -> str | None:
        """
        Solicita geração de imagem de personagem via DALL·E 3 (retorna 202 imediatamente).
        Retorna o image_id (pending) ou None em caso de falha.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{IMAGE_SERVICE_URL}/generate/character",
                    json={
                        "description": description,
                        "character_id": character_id,
                        "campaign_id": campaign_id,
                        "style": style,
                    },
                )
                if resp.status_code in (200, 201, 202):
                    return resp.json().get("image_id")
        except Exception as exc:
            logger.warning("Character image generation falhou: %s", exc)
        return None


class CharacterServiceClient:
    """Cliente HTTP para o serviço de personagens."""

    async def list_campaign_characters(self, campaign_id: str) -> list[dict]:
        """
        Retorna a lista de personagens de uma campanha.
        Lança exceção em caso de falha crítica.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{CHARACTER_SERVICE_URL}/campaigns/{campaign_id}/characters"
            )
            resp.raise_for_status()
            return resp.json()

    async def create_character(self, payload: dict) -> dict:
        """Cria um personagem via serviço de personagens."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{CHARACTER_SERVICE_URL}/characters",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def apply_state_update(
        self, character_id: str, field: str, value: str
    ) -> None:
        """
        Aplica uma mudança de estado [ESTADO:campo=valor] a um personagem.
        Suporta: hp_current (absoluto), hp (delta +/-), condition, exhaustion.
        Falhas são logadas mas nunca propagadas — nunca bloqueiam o round.
        """
        try:
            field = field.strip().lower()
            value = value.strip()
            payload: dict | None = None

            # hp como delta (+5 / -3) — busca HP atual primeiro
            if field == "hp":
                try:
                    delta = int(value)
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        r = await client.get(
                            f"{CHARACTER_SERVICE_URL}/characters/{character_id}"
                        )
                        if r.status_code == 200:
                            status_data = (r.json().get("status") or {})
                            current_hp = status_data.get("hp_current", 0)
                            payload = {"hp_current": max(0, current_hp + delta)}
                except (ValueError, Exception):
                    pass

            # hp_current absoluto
            elif field == "hp_current":
                try:
                    payload = {"hp_current": int(value)}
                except ValueError:
                    pass

            # condition
            elif field in ("condition", "conditions"):
                if value.lower() in ("none", "clear", ""):
                    payload = {"conditions": []}
                else:
                    payload = {"conditions": [value]}

            # exhaustion
            elif field == "exhaustion":
                try:
                    payload = {"exhaustion": int(value)}
                except ValueError:
                    pass

            if payload:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.patch(
                        f"{CHARACTER_SERVICE_URL}/characters/{character_id}/status",
                        json=payload,
                    )
        except Exception as exc:
            logger.warning(
                "Falha ao aplicar [ESTADO:%s=%s] em %s: %s", field, value, character_id, exc
            )
