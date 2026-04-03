"""Use cases for the knowledge context."""
from __future__ import annotations

import logging

from domain.knowledge.entity import KnowledgeChunk
from domain.knowledge.repository import (
    IAsyncEmbeddingPort,
    IAsyncKnowledgeChunkRepository,
    IKnowledgeChunkRepository,
    IPdfSourceRepository as _ISync,
    ISyncEmbeddingPort,
    IPdfStoragePort,
)
from domain.pdf_source.repository import IPdfSourceRepository

from .dtos import ChunkResultDTO, ProcessingResultDTO

logger = logging.getLogger(__name__)

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64
EMBEDDING_BATCH_SIZE = 50


class ProcessPdfUseCase:
    """
    Sync use case — called by the Celery worker.

    Pipeline:
      1. Fetch source metadata from DB.
      2. Download PDF bytes from storage.
      3. Extract text with PyMuPDF.
      4. Split into chunks.
      5. Generate embeddings in batches of 50.
      6. Bulk-insert into knowledge_chunks.
      7. Mark source as processed.
    """

    def __init__(
        self,
        source_repo: "ISyncPdfSourceRepository",
        chunk_repo: IKnowledgeChunkRepository,
        storage: IPdfStoragePort,
        embedding: ISyncEmbeddingPort,
    ) -> None:
        self._source_repo = source_repo
        self._chunk_repo = chunk_repo
        self._storage = storage
        self._embedding = embedding

    def execute(self, source_id: str) -> ProcessingResultDTO:
        import fitz  # PyMuPDF — only imported when needed
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        logger.info("[ProcessPdfUseCase] source_id=%s", source_id)

        source = self._source_repo.get_by_id_sync(source_id)
        if source is None:
            raise ValueError(f"pdf_sources id={source_id} não encontrado.")

        pdf_bytes = self._storage.download(source.minio_path)

        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = [pdf_doc[i].get_text("text") for i in range(len(pdf_doc))]
        pdf_doc.close()
        full_text = "\n\n".join(p for p in pages if p.strip())

        if not full_text.strip():
            self._source_repo.mark_error_sync(source_id, "O PDF não contém texto extraível (pode ser escaneado).")
            return ProcessingResultDTO(source_id=source_id, chunk_count=0, status="error")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        texts = splitter.split_text(full_text)

        if not texts:
            self._source_repo.mark_error_sync(source_id, "Nenhum chunk gerado — texto insuficiente.")
            return ProcessingResultDTO(source_id=source_id, chunk_count=0, status="error")

        import uuid as _uuid
        from uuid import UUID

        source_uuid = UUID(source_id)
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[i : i + EMBEDDING_BATCH_SIZE]
            batch_num = (i // EMBEDDING_BATCH_SIZE) + 1
            total_batches = (len(texts) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE
            logger.info("[ProcessPdfUseCase] Embeddings batch %d/%d (%d chunks)...", batch_num, total_batches, len(batch))
            all_embeddings.extend(self._embedding.embed_texts(batch))

        chunks = [
            KnowledgeChunk.create(
                source_id=source_uuid,
                chunk_index=idx,
                content=text,
                rpg_system=source.rpg_system,
            )
            for idx, text in enumerate(texts)
        ]

        self._chunk_repo.bulk_save(chunks, all_embeddings)
        self._source_repo.mark_processed_sync(source_id, len(chunks))

        logger.info("[ProcessPdfUseCase] Done — source_id=%s chunks=%d", source_id, len(chunks))
        return ProcessingResultDTO(source_id=source_id, chunk_count=len(chunks), status="completed")


class ISyncPdfSourceRepository:
    """Sync subset used only by ProcessPdfUseCase (implemented in infrastructure)."""

    def get_by_id_sync(self, source_id: str): ...
    def mark_processed_sync(self, source_id: str, chunk_count: int) -> None: ...
    def mark_error_sync(self, source_id: str, message: str) -> None: ...


class SemanticSearchUseCase:
    """
    Async use case — called by FastAPI endpoints (or the campaign service).

    Embeds the query with text-embedding-3-small and returns the top_k
    most relevant chunks via cosine distance.
    """

    def __init__(
        self,
        chunk_repo: IAsyncKnowledgeChunkRepository,
        embedding: IAsyncEmbeddingPort,
    ) -> None:
        self._chunk_repo = chunk_repo
        self._embedding = embedding

    async def execute(self, query: str, top_k: int = 8) -> list[ChunkResultDTO]:
        if not query.strip():
            return []
        vector = await self._embedding.embed_query(query)
        results = await self._chunk_repo.semantic_search(vector, top_k)
        return [
            ChunkResultDTO(
                content=r.content,
                source_id=r.source_id,
                rpg_system=r.rpg_system,
                score=r.score,
            )
            for r in results
        ]
