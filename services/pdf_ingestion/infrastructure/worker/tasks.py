"""
Celery tasks for PDF processing.

The task delegates all business logic to ProcessPdfUseCase.
Infrastructure (DB session, MinIO, OpenAI) is wired here.
"""
from __future__ import annotations

import logging

from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, acks_late=True)
def process_pdf(self, source_id: str) -> dict:
    """
    Celery task — processes a PDF from storage, generates embeddings, persists chunks.

    Args:
        source_id: UUID string of the pdf_sources row.

    Returns:
        dict with source_id, chunk_count, and status.
    """
    from application.knowledge.use_cases import ProcessPdfUseCase
    from infrastructure.ai.embedding_service import EmbeddingService
    from infrastructure.database.connection import get_sync_session
    from infrastructure.repositories.knowledge_chunk_repository import (
        SyncKnowledgeChunkRepository,
        SyncPdfSourceRepository,
    )
    from infrastructure.storage.minio_service import MinioService

    logger.info("[process_pdf] Iniciando — source_id=%s", source_id)
    db = get_sync_session()

    try:
        use_case = ProcessPdfUseCase(
            source_repo=SyncPdfSourceRepository(db),
            chunk_repo=SyncKnowledgeChunkRepository(db),
            storage=MinioService(),
            embedding=EmbeddingService(),
        )
        result = use_case.execute(source_id)
        return {"source_id": result.source_id, "chunk_count": result.chunk_count, "status": result.status}

    except Exception as exc:
        logger.exception("[process_pdf] Erro — source_id=%s: %s", source_id, exc)
        # Persist error message for polling
        try:
            from infrastructure.repositories.knowledge_chunk_repository import SyncPdfSourceRepository as _R
            _R(db).mark_error_sync(source_id, str(exc)[:1024])
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))

    finally:
        db.close()
