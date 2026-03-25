"""
Celery Worker — processamento de PDFs em background.

Pipeline:
  1. Baixa o PDF do MinIO.
  2. Extrai texto com PyMuPDF (fitz).
  3. Divide em chunks com RecursiveCharacterTextSplitter(chunk_size=512, overlap=64).
  4. Gera embeddings em batches de 50 via OpenAI text-embedding-3-small.
  5. Insere em bulk na tabela knowledge_chunks.
  6. Atualiza pdf_sources.processed=True e chunk_count=N.
"""
from __future__ import annotations

import io
import logging
import os
import uuid
from typing import Any

import fitz  # PyMuPDF
from celery import Celery
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from minio import Minio
from minio.error import S3Error
from openai import OpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

# ─── Configurações ────────────────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

POSTGRES_USER = os.getenv("POSTGRES_USER", "rpg_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "rpg_platform")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL_SYNC = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "rpg-pdfs")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_BATCH_SIZE = 50
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

# ─── Clientes (inicializados na primeira task) ────────────────────────────────

_minio_client: Minio | None = None
_openai_client: OpenAI | None = None
_sync_engine: Any = None
_SyncSession: Any = None


def _get_minio() -> Minio:
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
    return _minio_client


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _get_db_session():  # type: ignore[return]
    global _sync_engine, _SyncSession
    if _sync_engine is None:
        _sync_engine = create_engine(
            DATABASE_URL_SYNC,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        _SyncSession = sessionmaker(bind=_sync_engine, autoflush=False, autocommit=False)
    return _SyncSession()


# ─── Celery app ───────────────────────────────────────────────────────────────

celery_app = Celery("pdf_worker", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # Um PDF por vez por worker — operação pesada
)

celery_app.conf.task_routes = {
    "worker.process_pdf": {"queue": "pdf_processing"},
}


# ─── Task principal ───────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, acks_late=True)
def process_pdf(self, source_id: str) -> dict[str, Any]:  # type: ignore[override]
    """
    Processa um PDF completo: extração → chunking → embeddings → persistência.

    Args:
        source_id: UUID (string) da linha em pdf_sources.

    Returns:
        Dicionário com source_id e chunk_count ao final do processamento.
    """
    logger.info("[process_pdf] Iniciando processamento — source_id=%s", source_id)

    db = _get_db_session()

    try:
        # ── 1. Busca metadados do source ──────────────────────────────────────
        row = db.execute(
            text("SELECT * FROM pdf_sources WHERE id = :id"),
            {"id": source_id},
        ).mappings().one_or_none()

        if row is None:
            raise ValueError(f"pdf_sources id={source_id} não encontrado.")

        minio_path: str = row["minio_path"]
        rpg_system: str | None = row["rpg_system"]

        logger.info("[process_pdf] Baixando PDF do MinIO — path=%s", minio_path)

        # ── 2. Download do PDF via MinIO ──────────────────────────────────────
        minio = _get_minio()
        try:
            response = minio.get_object(MINIO_BUCKET, minio_path)
            pdf_bytes = response.read()
        except S3Error as exc:
            raise RuntimeError(f"Falha ao baixar PDF do MinIO: {exc}") from exc
        finally:
            try:
                response.close()
                response.release_conn()
            except Exception:
                pass

        # ── 3. Extração de texto com PyMuPDF ──────────────────────────────────
        logger.info("[process_pdf] Extraindo texto do PDF (%d bytes)...", len(pdf_bytes))

        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text_parts: list[str] = []

        for page_num in range(len(pdf_doc)):
            page = pdf_doc[page_num]
            page_text = page.get_text("text")
            if page_text.strip():
                full_text_parts.append(page_text)

        pdf_doc.close()

        full_text = "\n\n".join(full_text_parts)

        if not full_text.strip():
            _mark_error(db, source_id, "O PDF não contém texto extraível (pode ser escaneado).")
            return {"source_id": source_id, "chunk_count": 0, "status": "error"}

        logger.info(
            "[process_pdf] Texto extraído: %d caracteres em %d páginas.",
            len(full_text),
            len(full_text_parts),
        )

        # ── 4. Divisão em chunks ──────────────────────────────────────────────
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks: list[str] = splitter.split_text(full_text)

        total_chunks = len(chunks)
        logger.info("[process_pdf] Total de chunks gerados: %d", total_chunks)

        if total_chunks == 0:
            _mark_error(db, source_id, "Nenhum chunk gerado — texto insuficiente.")
            return {"source_id": source_id, "chunk_count": 0, "status": "error"}

        # ── 5. Geração de embeddings em batches de 50 ─────────────────────────
        openai_client = _get_openai()
        all_embeddings: list[list[float]] = []

        for batch_start in range(0, total_chunks, EMBEDDING_BATCH_SIZE):
            batch = chunks[batch_start : batch_start + EMBEDDING_BATCH_SIZE]
            batch_num = (batch_start // EMBEDDING_BATCH_SIZE) + 1
            total_batches = (total_chunks + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE

            logger.info(
                "[process_pdf] Gerando embeddings — batch %d/%d (%d chunks)...",
                batch_num,
                total_batches,
                len(batch),
            )

            response = openai_client.embeddings.create(
                input=batch,
                model=EMBEDDING_MODEL,
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

            logger.info(
                "[process_pdf] Batch %d/%d concluído — %d embeddings gerados.",
                batch_num,
                total_batches,
                len(batch_embeddings),
            )

        # ── 6. Bulk insert em knowledge_chunks ───────────────────────────────
        logger.info("[process_pdf] Inserindo %d chunks no banco de dados...", total_chunks)

        insert_rows: list[dict[str, Any]] = []
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, all_embeddings)):
            insert_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "source_id": source_id,
                    "chunk_index": idx,
                    "content": chunk_text,
                    "rpg_system": rpg_system,
                    "embedding": _embedding_to_pg_literal(embedding),
                    "token_count": len(chunk_text.split()),
                }
            )

        # Insere em sub-batches para não sobrecarregar o executor de parâmetros
        SUB_BATCH = 200
        for sub_start in range(0, len(insert_rows), SUB_BATCH):
            sub_batch = insert_rows[sub_start : sub_start + SUB_BATCH]
            db.execute(
                text(
                    """
                    INSERT INTO knowledge_chunks
                        (id, source_id, chunk_index, content, rpg_system, embedding, token_count)
                    VALUES
                        (:id, :source_id, :chunk_index, :content, :rpg_system,
                         :embedding::vector, :token_count)
                    """
                ),
                sub_batch,
            )

        # ── 7. Marca como processado ──────────────────────────────────────────
        db.execute(
            text(
                """
                UPDATE pdf_sources
                   SET processed = TRUE,
                       chunk_count = :chunk_count,
                       updated_at = NOW()
                 WHERE id = :id
                """
            ),
            {"chunk_count": total_chunks, "id": source_id},
        )
        db.commit()

        logger.info(
            "[process_pdf] Concluído com sucesso — source_id=%s, chunks=%d",
            source_id,
            total_chunks,
        )
        return {"source_id": source_id, "chunk_count": total_chunks, "status": "completed"}

    except Exception as exc:
        db.rollback()
        logger.exception("[process_pdf] Erro ao processar source_id=%s: %s", source_id, exc)

        # Persiste mensagem de erro para exibição no polling
        try:
            _mark_error(db, source_id, str(exc)[:1024])
        except Exception:
            pass

        # Reexecuta com backoff exponencial (jitter natural do Celery)
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))

    finally:
        db.close()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _embedding_to_pg_literal(embedding: list[float]) -> str:
    """Converte lista de floats para o literal de array do PostgreSQL/pgvector."""
    return "[" + ",".join(map(str, embedding)) + "]"


def _mark_error(db: Any, source_id: str, message: str) -> None:
    """Registra uma falha em pdf_sources e faz commit."""
    db.execute(
        text(
            """
            UPDATE pdf_sources
               SET error_msg = :msg,
                   updated_at = NOW()
             WHERE id = :id
            """
        ),
        {"msg": message, "id": source_id},
    )
    db.commit()
