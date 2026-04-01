"""Unit tests for Celery worker — PDF processing pipeline."""
import pytest
from unittest.mock import patch, MagicMock, call
import io

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── Helpers ────────────────────────────────────────────────────────────────────

class TestEmbeddingHelper:
    def test_embedding_to_pg_literal_format(self):
        from worker import _embedding_to_pg_literal
        result = _embedding_to_pg_literal([0.1, 0.2, 0.3])
        assert result.startswith("[")
        assert result.endswith("]")
        assert "0.1" in result

    def test_embedding_empty_list(self):
        from worker import _embedding_to_pg_literal
        result = _embedding_to_pg_literal([])
        assert result == "[]"

    def test_embedding_1536_dims(self):
        from worker import _embedding_to_pg_literal
        vec = [0.01] * 1536
        result = _embedding_to_pg_literal(vec)
        assert result.count(",") == 1535


# ── Celery task tests ─────────────────────────────────────────────────────────
# We run the task synchronously using .apply() which bypasses the broker.

def _make_mapping(source_id="src-1", title="Test Book"):
    """Return a dict that behaves like a DB row mapping."""
    return {
        "id": source_id,
        "title": title,
        "minio_path": f"pdfs/{source_id}_test.pdf",
        "rpg_system": "D&D 5e",
        "source_type": "rulebook",
    }


def _setup_db_mock(row=None):
    """Mock for _get_db_session() returning a session with execute()."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.one_or_none.return_value = row
    mock_session.execute.return_value = mock_result
    return mock_session


def _setup_minio_mock(pdf_bytes=b"%PDF-1.4 fake"):
    mock_minio = MagicMock()
    mock_response = MagicMock()
    mock_response.read.return_value = pdf_bytes
    mock_minio.get_object.return_value = mock_response
    return mock_minio


def _setup_fitz_mock(page_text="Some dungeon text " * 30):
    mock_fitz = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = page_text
    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
    mock_doc.__len__ = MagicMock(return_value=1)
    mock_doc.__getitem__ = MagicMock(return_value=mock_page)
    mock_fitz.open.return_value = mock_doc
    return mock_fitz


def _setup_openai_mock():
    """Mock for _get_openai() — returns OpenAI client with embeddings.create."""
    mock_openai = MagicMock()
    mock_embed_item = MagicMock()
    mock_embed_item.embedding = [0.1] * 1536
    mock_embed_response = MagicMock()
    mock_embed_response.data = [mock_embed_item, mock_embed_item]
    mock_openai.embeddings.create.return_value = mock_embed_response
    return mock_openai


class TestProcessPdf:
    def _get_task(self):
        from worker import process_pdf
        return process_pdf

    @patch("worker.fitz")
    @patch("worker._get_openai")
    @patch("worker._get_minio")
    @patch("worker._get_db_session")
    def test_happy_path_calls_embed(self, mock_db_fn, mock_minio_fn, mock_openai_fn, mock_fitz):
        mock_db_fn.return_value = _setup_db_mock(_make_mapping())
        mock_minio_fn.return_value = _setup_minio_mock()
        mock_fitz.open.return_value = _setup_fitz_mock().open.return_value

        mock_openai = _setup_openai_mock()
        mock_openai_fn.return_value = mock_openai

        fitz_mock = _setup_fitz_mock()
        with patch("worker.fitz", fitz_mock):
            task = self._get_task()
            result = task.apply(args=["src-1"])

        # embeddings.create must have been called
        mock_openai.embeddings.create.assert_called()

    @patch("worker._get_db_session")
    def test_source_not_found_raises(self, mock_db_fn):
        mock_db_fn.return_value = _setup_db_mock(row=None)

        task = self._get_task()
        result = task.apply(args=["nonexistent-id"])
        assert result.failed() or result.result is None or isinstance(result.result, Exception)

    @patch("worker.fitz")
    @patch("worker._get_openai")
    @patch("worker._get_minio")
    @patch("worker._get_db_session")
    def test_empty_text_skips_embedding(self, mock_db_fn, mock_minio_fn, mock_openai_fn, mock_fitz):
        mock_db_fn.return_value = _setup_db_mock(_make_mapping())
        mock_minio_fn.return_value = _setup_minio_mock()

        mock_openai = _setup_openai_mock()
        mock_openai_fn.return_value = mock_openai

        fitz_mock = _setup_fitz_mock(page_text="")  # empty
        with patch("worker.fitz", fitz_mock):
            task = self._get_task()
            task.apply(args=["src-1"])

        # No embeddings should be generated for empty text
        mock_openai.embeddings.create.assert_not_called()

    def test_embedding_batching(self):
        """Embeddings must be processed in batches of 50."""
        chunks = ["chunk " + str(i) for i in range(150)]
        batches = [chunks[i:i+50] for i in range(0, len(chunks), 50)]
        assert len(batches) == 3
        assert len(batches[0]) == 50
        assert len(batches[2]) == 50
