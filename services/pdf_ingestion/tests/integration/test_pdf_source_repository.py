"""Integration tests for PdfSourceRepository against a real PostgreSQL DB."""
import pytest
from uuid import uuid4

from domain.pdf_source.entity import PdfSource
from infrastructure.repositories.pdf_source_repository import PdfSourceRepository


class TestSave:
    async def test_save_persists_and_returns_domain_object(self, db_session):
        repo = PdfSourceRepository(db_session)
        source = PdfSource.create(title="PHB", filename="phb.pdf", minio_path="pdfs/phb.pdf")
        saved = await repo.save(source)
        assert saved.id == source.id
        assert saved.title == "PHB"
        assert saved.processed is False

    async def test_save_with_optional_fields(self, db_session):
        repo = PdfSourceRepository(db_session)
        source = PdfSource.create(
            title="Bestiary",
            filename="bestiary.pdf",
            minio_path="pdfs/bestiary.pdf",
            rpg_system="Pathfinder",
            source_type="bestiary",
        )
        saved = await repo.save(source)
        assert saved.rpg_system == "Pathfinder"
        assert saved.source_type == "bestiary"


class TestGetById:
    async def test_get_by_id_returns_source(self, db_session):
        repo = PdfSourceRepository(db_session)
        source = PdfSource.create(title="T", filename="f.pdf", minio_path="m")
        await repo.save(source)
        found = await repo.get_by_id(source.id)
        assert found is not None
        assert found.id == source.id

    async def test_get_by_id_missing_returns_none(self, db_session):
        repo = PdfSourceRepository(db_session)
        assert await repo.get_by_id(uuid4()) is None


class TestListAll:
    async def test_list_all_empty(self, db_session):
        repo = PdfSourceRepository(db_session)
        assert await repo.list_all() == []

    async def test_list_all_returns_all(self, db_session):
        repo = PdfSourceRepository(db_session)
        await repo.save(PdfSource.create(title="A", filename="a.pdf", minio_path="a"))
        await repo.save(PdfSource.create(title="B", filename="b.pdf", minio_path="b"))
        sources = await repo.list_all()
        assert len(sources) == 2


class TestUpdate:
    async def test_update_persists_changes(self, db_session):
        repo = PdfSourceRepository(db_session)
        source = PdfSource.create(title="T", filename="f.pdf", minio_path="m")
        await repo.save(source)
        source.mark_processed(42)
        updated = await repo.update(source)
        assert updated.processed is True
        assert updated.chunk_count == 42


class TestDelete:
    async def test_delete_removes_source(self, db_session):
        repo = PdfSourceRepository(db_session)
        source = PdfSource.create(title="T", filename="f.pdf", minio_path="m")
        await repo.save(source)
        await repo.delete(source.id)
        assert await repo.get_by_id(source.id) is None


class TestCountPending:
    async def test_count_pending_empty(self, db_session):
        repo = PdfSourceRepository(db_session)
        assert await repo.count_pending() == 0

    async def test_counts_only_unprocessed_without_error(self, db_session):
        repo = PdfSourceRepository(db_session)
        pending = PdfSource.create(title="A", filename="a.pdf", minio_path="a")
        done = PdfSource.create(title="B", filename="b.pdf", minio_path="b")
        done.mark_processed(10)
        error = PdfSource.create(title="C", filename="c.pdf", minio_path="c")
        error.mark_error("timeout")
        for s in [pending, done, error]:
            await repo.save(s)
            if s is not pending:
                await repo.update(s)
        count = await repo.count_pending()
        assert count == 1
