"""Use cases for the pdf_source context."""
from __future__ import annotations

import io
import uuid
from typing import Protocol

from domain.pdf_source.entity import PdfSource
from domain.pdf_source.repository import IPdfSourceRepository
from domain.knowledge.repository import IAsyncKnowledgeChunkRepository, IPdfStoragePort

from .dtos import KnowledgeStatsDTO, PdfSourceDTO, ProcessingStatusDTO, UploadPdfDTO


class ITaskQueuePort(Protocol):
    """Enqueues background PDF processing tasks."""

    def enqueue_pdf_processing(self, source_id: str) -> None: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_dto(source: PdfSource) -> PdfSourceDTO:
    return PdfSourceDTO(
        id=source.id,
        title=source.title,
        filename=source.filename,
        minio_path=source.minio_path,
        processed=source.processed,
        chunk_count=source.chunk_count,
        status=source.status,
        rpg_system=source.rpg_system,
        source_type=source.source_type,
        uploaded_by=source.uploaded_by,
        error_msg=source.error_msg,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------


class UploadPdfUseCase:
    def __init__(
        self,
        repo: IPdfSourceRepository,
        storage: IPdfStoragePort,
        task_queue: ITaskQueuePort,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._task_queue = task_queue

    async def execute(self, dto: UploadPdfDTO) -> PdfSourceDTO:
        if len(dto.file_data) == 0:
            raise ValueError("empty_file")

        unique_prefix = uuid.uuid4().hex
        safe_filename = dto.filename.replace(" ", "_")
        object_name = f"pdfs/{unique_prefix}_{safe_filename}"

        self._storage.upload(dto.file_data, object_name)

        source = PdfSource.create(
            title=dto.title,
            filename=safe_filename,
            minio_path=object_name,
            rpg_system=dto.rpg_system,
            source_type=dto.source_type,
        )
        saved = await self._repo.save(source)
        self._task_queue.enqueue_pdf_processing(str(saved.id))
        return _to_dto(saved)


class ListSourcesUseCase:
    def __init__(self, repo: IPdfSourceRepository) -> None:
        self._repo = repo

    async def execute(self) -> list[PdfSourceDTO]:
        sources = await self._repo.list_all()
        return [_to_dto(s) for s in sources]


class GetSourceStatusUseCase:
    def __init__(self, repo: IPdfSourceRepository) -> None:
        self._repo = repo

    async def execute(self, source_id: uuid.UUID) -> ProcessingStatusDTO:
        source = await self._repo.get_by_id(source_id)
        if source is None:
            raise ValueError("not_found")
        return ProcessingStatusDTO(
            source_id=source.id,
            title=source.title,
            processed=source.processed,
            chunk_count=source.chunk_count,
            status=source.status,
            error_msg=source.error_msg,
        )


class DeleteSourceUseCase:
    def __init__(
        self,
        repo: IPdfSourceRepository,
        chunk_repo: IAsyncKnowledgeChunkRepository,
    ) -> None:
        self._repo = repo
        self._chunk_repo = chunk_repo

    async def execute(self, source_id: uuid.UUID) -> None:
        source = await self._repo.get_by_id(source_id)
        if source is None:
            raise ValueError("not_found")
        await self._chunk_repo.delete_by_source(source_id)
        await self._repo.delete(source_id)


class RetrySourceUseCase:
    def __init__(
        self,
        repo: IPdfSourceRepository,
        task_queue: ITaskQueuePort,
    ) -> None:
        self._repo = repo
        self._task_queue = task_queue

    async def execute(self, source_id: uuid.UUID) -> dict:
        source = await self._repo.get_by_id(source_id)
        if source is None:
            raise ValueError("not_found")
        source.reset_for_retry()
        await self._repo.update(source)
        self._task_queue.enqueue_pdf_processing(str(source_id))
        return {"source_id": str(source_id), "status": "enqueued", "message": "Reprocessamento iniciado."}


class GetKnowledgeStatsUseCase:
    def __init__(
        self,
        repo: IPdfSourceRepository,
        chunk_repo: IAsyncKnowledgeChunkRepository,
    ) -> None:
        self._repo = repo
        self._chunk_repo = chunk_repo

    async def execute(self) -> KnowledgeStatsDTO:
        total_chunks = await self._chunk_repo.count()
        pending_count = await self._repo.count_pending()
        sources = await self._repo.list_all()
        systems = list({s.rpg_system for s in sources if s.rpg_system})
        return KnowledgeStatsDTO(
            total_chunks=total_chunks,
            gm_is_ready=total_chunks > 0,
            total_systems=len(systems),
            systems_covered=systems,
            total_sources=len(sources),
            processing_count=pending_count,
        )
