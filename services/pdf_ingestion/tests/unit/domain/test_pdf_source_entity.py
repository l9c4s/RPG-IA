"""Unit tests for the PdfSource aggregate root."""
import pytest
from uuid import UUID

from domain.pdf_source.entity import PdfSource


class TestPdfSourceCreate:
    def test_create_sets_defaults(self):
        s = PdfSource.create(title="PHB", filename="phb.pdf", minio_path="pdfs/phb.pdf")
        assert isinstance(s.id, UUID)
        assert s.processed is False
        assert s.chunk_count == 0
        assert s.error_msg is None
        assert s.rpg_system is None

    def test_create_with_optional_fields(self):
        s = PdfSource.create(
            title="PHB",
            filename="phb.pdf",
            minio_path="pdfs/phb.pdf",
            rpg_system="D&D 5e",
            source_type="rulebook",
        )
        assert s.rpg_system == "D&D 5e"
        assert s.source_type == "rulebook"

    def test_status_pending_on_create(self):
        s = PdfSource.create(title="T", filename="f.pdf", minio_path="m")
        assert s.status == "pending"


class TestPdfSourceStatus:
    def test_status_completed_when_processed(self):
        s = PdfSource.create(title="T", filename="f.pdf", minio_path="m")
        s.mark_processed(100)
        assert s.status == "completed"

    def test_status_error_when_error_msg_set(self):
        s = PdfSource.create(title="T", filename="f.pdf", minio_path="m")
        s.mark_error("scan only")
        assert s.status == "error"

    def test_error_takes_priority_over_processed(self):
        s = PdfSource.create(title="T", filename="f.pdf", minio_path="m")
        s.processed = True
        s.error_msg = "oops"
        assert s.status == "error"


class TestPdfSourceMarkProcessed:
    def test_mark_processed_sets_fields(self):
        s = PdfSource.create(title="T", filename="f.pdf", minio_path="m")
        s.mark_processed(42)
        assert s.processed is True
        assert s.chunk_count == 42
        assert s.error_msg is None

    def test_mark_processed_clears_error(self):
        s = PdfSource.create(title="T", filename="f.pdf", minio_path="m")
        s.error_msg = "previous error"
        s.mark_processed(10)
        assert s.error_msg is None


class TestPdfSourceMarkError:
    def test_mark_error_sets_message(self):
        s = PdfSource.create(title="T", filename="f.pdf", minio_path="m")
        s.mark_error("failed to extract text")
        assert s.error_msg == "failed to extract text"

    def test_mark_error_truncates_to_1024(self):
        s = PdfSource.create(title="T", filename="f.pdf", minio_path="m")
        s.mark_error("x" * 2000)
        assert len(s.error_msg) == 1024


class TestPdfSourceResetForRetry:
    def test_reset_clears_all_fields(self):
        s = PdfSource.create(title="T", filename="f.pdf", minio_path="m")
        s.processed = True
        s.chunk_count = 50
        s.error_msg = "timeout"
        s.reset_for_retry()
        assert s.processed is False
        assert s.chunk_count == 0
        assert s.error_msg is None
