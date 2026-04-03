"""FastAPI dependency providers for the pdf_ingestion service."""
from __future__ import annotations

from infrastructure.ai.embedding_service import AsyncEmbeddingService
from infrastructure.storage.minio_service import MinioService

# ---------------------------------------------------------------------------
# Singletons (expensive to instantiate — created once per process)
# ---------------------------------------------------------------------------

_minio = MinioService()
_async_embedding = AsyncEmbeddingService()


def get_minio() -> MinioService:
    return _minio


def get_async_embedding() -> AsyncEmbeddingService:
    return _async_embedding


# ---------------------------------------------------------------------------
# Task queue adapter (wraps Celery send_task)
# ---------------------------------------------------------------------------


class CeleryTaskQueue:
    def enqueue_pdf_processing(self, source_id: str) -> None:
        from infrastructure.worker.tasks import process_pdf
        process_pdf.apply_async(args=[source_id], queue="pdf_processing")


_task_queue = CeleryTaskQueue()


def get_task_queue() -> CeleryTaskQueue:
    return _task_queue
