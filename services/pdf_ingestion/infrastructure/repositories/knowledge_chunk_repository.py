"""
Knowledge chunk repositories.

SyncKnowledgeChunkRepository  — used by the Celery worker (psycopg2 session).
AsyncKnowledgeChunkRepository — used by FastAPI for stats and semantic search.
SyncPdfSourceRepository       — minimal sync interface for the Celery worker.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.knowledge.entity import ChunkResult, KnowledgeChunk
from domain.pdf_source.entity import PdfSource

logger = logging.getLogger(__name__)

_SUB_BATCH = 200


def _embedding_to_pg_literal(embedding: list[float]) -> str:
    return "[" + ",".join(map(str, embedding)) + "]"


# ---------------------------------------------------------------------------
# Sync repository — Celery worker
# ---------------------------------------------------------------------------


class SyncKnowledgeChunkRepository:
    """Sync implementation backed by a SQLAlchemy sync session."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def bulk_save(self, chunks: list[KnowledgeChunk], embeddings: list[list[float]]) -> None:
        rows = [
            {
                "id": str(chunk.id),
                "source_id": str(chunk.source_id),
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "rpg_system": chunk.rpg_system,
                "embedding": _embedding_to_pg_literal(emb),
                "token_count": chunk.token_count,
            }
            for chunk, emb in zip(chunks, embeddings)
        ]
        for start in range(0, len(rows), _SUB_BATCH):
            sub = rows[start : start + _SUB_BATCH]
            self._session.execute(
                text(
                    """
                    INSERT INTO knowledge_chunks
                        (id, source_id, chunk_index, content, rpg_system, embedding, token_count)
                    VALUES
                        (:id, :source_id, :chunk_index, :content, :rpg_system,
                         CAST(:embedding AS vector), :token_count)
                    """
                ),
                sub,
            )
        self._session.commit()

    def delete_by_source(self, source_id: UUID) -> None:
        self._session.execute(
            text("DELETE FROM knowledge_chunks WHERE source_id = :id"),
            {"id": str(source_id)},
        )
        self._session.commit()

    def count(self) -> int:
        result = self._session.execute(
            text("SELECT COUNT(*) FROM knowledge_chunks")
        )
        return int(result.scalar() or 0)


# ---------------------------------------------------------------------------
# Async repository — FastAPI
# ---------------------------------------------------------------------------


class AsyncKnowledgeChunkRepository:
    """Async implementation backed by a SQLAlchemy async session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count(self) -> int:
        result = await self._session.execute(
            text("SELECT COUNT(*) FROM knowledge_chunks")
        )
        return int(result.scalar() or 0)

    async def delete_by_source(self, source_id: UUID) -> None:
        await self._session.execute(
            text("DELETE FROM knowledge_chunks WHERE source_id = :id"),
            {"id": str(source_id)},
        )
        await self._session.commit()

    async def semantic_search(self, query_vector: list[float], top_k: int) -> list[ChunkResult]:
        vec_literal = _embedding_to_pg_literal(query_vector)
        result = await self._session.execute(
            text(
                """
                SELECT
                    kc.content,
                    kc.source_id::text            AS source_id,
                    kc.rpg_system,
                    kc.embedding <=> :vec::vector AS score
                FROM knowledge_chunks kc
                ORDER BY kc.embedding <=> :vec::vector
                LIMIT :top_k
                """
            ),
            {"vec": vec_literal, "top_k": top_k},
        )
        rows = result.mappings().all()
        return [
            ChunkResult(
                content=row["content"],
                source_id=row["source_id"],
                rpg_system=row["rpg_system"],
                score=float(row["score"]),
            )
            for row in rows
        ]


# ---------------------------------------------------------------------------
# Sync PdfSource subset — Celery worker
# ---------------------------------------------------------------------------


class SyncPdfSourceRepository:
    """
    Minimal sync repository used by ProcessPdfUseCase in the Celery worker.
    Operates on a psycopg2-backed session.
    """

    def __init__(self, session: Any) -> None:
        self._session = session

    def get_by_id_sync(self, source_id: str) -> PdfSource | None:
        row = (
            self._session.execute(
                text("SELECT * FROM pdf_sources WHERE id = :id"),
                {"id": source_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return PdfSource(
            id=row["id"],
            title=row["title"],
            filename=row["filename"],
            minio_path=row["minio_path"],
            processed=row["processed"],
            chunk_count=row["chunk_count"],
            rpg_system=row.get("rpg_system"),
            source_type=row.get("source_type"),
            uploaded_by=row.get("uploaded_by"),
            error_msg=row.get("error_msg"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def mark_processed_sync(self, source_id: str, chunk_count: int) -> None:
        self._session.execute(
            text(
                "UPDATE pdf_sources SET processed = TRUE, chunk_count = :n, "
                "updated_at = NOW() WHERE id = :id"
            ),
            {"n": chunk_count, "id": source_id},
        )
        self._session.commit()

    def mark_error_sync(self, source_id: str, message: str) -> None:
        self._session.execute(
            text(
                "UPDATE pdf_sources SET error_msg = :msg, updated_at = NOW() WHERE id = :id"
            ),
            {"msg": message[:1024], "id": source_id},
        )
        self._session.commit()
