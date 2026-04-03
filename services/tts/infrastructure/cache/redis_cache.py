"""Redis cache adapter."""
from __future__ import annotations

import os

import redis.asyncio as redis


class RedisCache:
    """Async Redis adapter for audio URL caching."""

    def __init__(self) -> None:
        self._url = os.getenv("REDIS_URL", "redis://localhost:6379")

    def _client(self) -> redis.Redis:
        return redis.from_url(self._url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        client = self._client()
        try:
            return await client.get(key)
        finally:
            await client.aclose()

    async def set(self, key: str, value: str, ttl: int) -> None:
        client = self._client()
        try:
            await client.set(key, value, ex=ttl)
        finally:
            await client.aclose()
