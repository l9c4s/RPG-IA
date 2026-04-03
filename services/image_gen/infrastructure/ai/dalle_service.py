"""DALL-E 3 adapter — implements IImageGeneratorPort."""
from __future__ import annotations

import logging
import os

import httpx
from openai import AsyncOpenAI

from domain.image.value_objects import ImageSize, Prompt

logger = logging.getLogger(__name__)


class DalleService:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "dall-e-3",
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY", ""))
        self._model = model

    async def generate(self, prompt: Prompt, size: ImageSize) -> bytes:
        try:
            response = await self._client.images.generate(
                model=self._model,
                prompt=str(prompt),
                size=size.value,  # type: ignore[arg-type]
                quality="standard",
                n=1,
                response_format="url",
            )
        except Exception as exc:
            logger.error("Erro ao chamar DALL-E 3: %s", exc)
            raise RuntimeError(f"Falha na geração de imagem: {exc}") from exc

        openai_url: str = response.data[0].url  # type: ignore[index]

        try:
            async with httpx.AsyncClient(timeout=60.0) as http:
                img_response = await http.get(openai_url)
                img_response.raise_for_status()
                return img_response.content
        except Exception as exc:
            logger.error("Erro ao baixar imagem da OpenAI: %s", exc)
            raise RuntimeError(f"Falha ao baixar imagem gerada: {exc}") from exc
