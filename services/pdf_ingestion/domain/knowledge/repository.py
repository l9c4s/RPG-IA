"""Port interfaces for the knowledge domain."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entity import ChunkResult, KnowledgeChunk


class IKnowledgeChunkRepository(Protocol):
    """Sync interface — used by the Celery worker."""

    def bulk_save(self, chunks: list[KnowledgeChunk], embeddings: list[list[float]]) -> None: ...
    def delete_by_source(self, source_id: UUID) -> None: ...
    def count(self) -> int: ...


class IAsyncKnowledgeChunkRepository(Protocol):
    """Async interface — used by FastAPI endpoints."""

    async def count(self) -> int: ...
    async def delete_by_source(self, source_id: UUID) -> None: ...
    async def semantic_search(self, query_vector: list[float], top_k: int) -> list[ChunkResult]: ...


class IPdfStoragePort(Protocol):
    """Sync storage port — used by the Celery worker."""

    def upload(self, data: bytes, object_name: str) -> str: ...
    def download(self, object_name: str) -> bytes: ...
    def ensure_bucket(self) -> None: ...


class ISyncEmbeddingPort(Protocol):
    """Sync embedding port — used by the Celery worker."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class IAsyncEmbeddingPort(Protocol):
    """Async embedding port — used by FastAPI for semantic search."""

    async def embed_query(self, query: str) -> list[float]: ...
