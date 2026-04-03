"""Unit tests for pdf_source and knowledge use cases."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from application.pdf_source.dtos import UploadPdfDTO
from application.pdf_source.use_cases import (
    DeleteSourceUseCase,
    GetKnowledgeStatsUseCase,
    GetSourceStatusUseCase,
    ListSourcesUseCase,
    RetrySourceUseCase,
    UploadPdfUseCase,
)
from domain.pdf_source.entity import PdfSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source(**kwargs) -> PdfSource:
    defaults = dict(
        title="PHB",
        filename="phb.pdf",
        minio_path="pdfs/phb.pdf",
        rpg_system="D&D 5e",
    )
    defaults.update(kwargs)
    return PdfSource.create(**defaults)


# ---------------------------------------------------------------------------
# UploadPdfUseCase
# ---------------------------------------------------------------------------


class TestUploadPdfUseCase:
    @pytest.fixture
    def mocks(self):
        repo = AsyncMock()
        storage = MagicMock()
        task_queue = MagicMock()
        source = _make_source()
        repo.save.return_value = source
        storage.upload.return_value = "pdfs/abc_phb.pdf"
        return repo, storage, task_queue, source

    async def test_success_returns_dto(self, mocks):
        repo, storage, task_queue, source = mocks
        use_case = UploadPdfUseCase(repo=repo, storage=storage, task_queue=task_queue)
        dto = UploadPdfDTO(title="PHB", filename="phb.pdf", file_data=b"%PDF")
        result = await use_case.execute(dto)
        assert result.id == source.id
        assert result.title == source.title
        storage.upload.assert_called_once()
        task_queue.enqueue_pdf_processing.assert_called_once_with(str(source.id))

    async def test_empty_file_raises(self, mocks):
        repo, storage, task_queue, _ = mocks
        use_case = UploadPdfUseCase(repo=repo, storage=storage, task_queue=task_queue)
        dto = UploadPdfDTO(title="PHB", filename="phb.pdf", file_data=b"")
        with pytest.raises(ValueError, match="empty_file"):
            await use_case.execute(dto)

    async def test_storage_error_propagates(self, mocks):
        repo, storage, task_queue, _ = mocks
        storage.upload.side_effect = RuntimeError("MinIO down")
        use_case = UploadPdfUseCase(repo=repo, storage=storage, task_queue=task_queue)
        dto = UploadPdfDTO(title="PHB", filename="phb.pdf", file_data=b"%PDF")
        with pytest.raises(RuntimeError, match="MinIO down"):
            await use_case.execute(dto)


# ---------------------------------------------------------------------------
# ListSourcesUseCase
# ---------------------------------------------------------------------------


class TestListSourcesUseCase:
    async def test_returns_dtos(self):
        repo = AsyncMock()
        repo.list_all.return_value = [_make_source(), _make_source()]
        result = await ListSourcesUseCase(repo).execute()
        assert len(result) == 2

    async def test_empty_list(self):
        repo = AsyncMock()
        repo.list_all.return_value = []
        result = await ListSourcesUseCase(repo).execute()
        assert result == []


# ---------------------------------------------------------------------------
# GetSourceStatusUseCase
# ---------------------------------------------------------------------------


class TestGetSourceStatusUseCase:
    async def test_returns_status_dto(self):
        repo = AsyncMock()
        source = _make_source()
        repo.get_by_id.return_value = source
        result = await GetSourceStatusUseCase(repo).execute(source.id)
        assert result.source_id == source.id
        assert result.status == "pending"

    async def test_not_found_raises(self):
        repo = AsyncMock()
        repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not_found"):
            await GetSourceStatusUseCase(repo).execute(uuid4())


# ---------------------------------------------------------------------------
# DeleteSourceUseCase
# ---------------------------------------------------------------------------


class TestDeleteSourceUseCase:
    async def test_deletes_chunks_then_source(self):
        repo = AsyncMock()
        chunk_repo = AsyncMock()
        source = _make_source()
        repo.get_by_id.return_value = source
        await DeleteSourceUseCase(repo=repo, chunk_repo=chunk_repo).execute(source.id)
        chunk_repo.delete_by_source.assert_awaited_once_with(source.id)
        repo.delete.assert_awaited_once_with(source.id)

    async def test_not_found_raises(self):
        repo = AsyncMock()
        chunk_repo = AsyncMock()
        repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not_found"):
            await DeleteSourceUseCase(repo=repo, chunk_repo=chunk_repo).execute(uuid4())


# ---------------------------------------------------------------------------
# RetrySourceUseCase
# ---------------------------------------------------------------------------


class TestRetrySourceUseCase:
    async def test_resets_and_enqueues(self):
        repo = AsyncMock()
        task_queue = MagicMock()
        source = _make_source()
        source.mark_error("timeout")
        repo.get_by_id.return_value = source
        repo.update.return_value = source
        result = await RetrySourceUseCase(repo=repo, task_queue=task_queue).execute(source.id)
        assert result["status"] == "enqueued"
        task_queue.enqueue_pdf_processing.assert_called_once_with(str(source.id))
        assert source.status == "pending"

    async def test_not_found_raises(self):
        repo = AsyncMock()
        repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not_found"):
            await RetrySourceUseCase(repo=repo, task_queue=MagicMock()).execute(uuid4())


# ---------------------------------------------------------------------------
# GetKnowledgeStatsUseCase
# ---------------------------------------------------------------------------


class TestGetKnowledgeStatsUseCase:
    async def test_returns_stats(self):
        repo = AsyncMock()
        chunk_repo = AsyncMock()
        repo.count_pending.return_value = 1
        chunk_repo.count.return_value = 50
        sources = [_make_source(rpg_system="D&D 5e"), _make_source(rpg_system="Pathfinder")]
        repo.list_all.return_value = sources
        result = await GetKnowledgeStatsUseCase(repo=repo, chunk_repo=chunk_repo).execute()
        assert result.total_chunks == 50
        assert result.gm_is_ready is True
        assert result.total_sources == 2
        assert result.total_systems == 2
        assert result.processing_count == 1

    async def test_empty_db_not_ready(self):
        repo = AsyncMock()
        chunk_repo = AsyncMock()
        repo.count_pending.return_value = 0
        chunk_repo.count.return_value = 0
        repo.list_all.return_value = []
        result = await GetKnowledgeStatsUseCase(repo=repo, chunk_repo=chunk_repo).execute()
        assert result.gm_is_ready is False
        assert result.total_chunks == 0
