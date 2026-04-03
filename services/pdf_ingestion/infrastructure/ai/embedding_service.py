"""OpenAI embedding adapters — sync (Celery) and async (FastAPI)."""
from __future__ import annotations

import os

from openai import AsyncOpenAI, OpenAI

EMBEDDING_MODEL = "text-embedding-3-small"


class EmbeddingService:
    """Sync adapter — used by the Celery worker."""

    def __init__(self) -> None:
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
        return [item.embedding for item in response.data]


class AsyncEmbeddingService:
    """Async adapter — used by FastAPI semantic search."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

    async def embed_query(self, query: str) -> list[float]:
        response = await self._client.embeddings.create(input=[query], model=EMBEDDING_MODEL)
        return response.data[0].embedding
