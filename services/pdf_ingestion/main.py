"""
PDF Ingestion Service — FastAPI app na porta 8001.

Rotas:
  POST /upload                        — recebe PDF, salva no MinIO, cria registro em
                                        pdf_sources, enfileira task Celery e retorna
                                        source_id imediatamente.
  GET  /sources                       — lista todos os pdf_sources.
  GET  /sources/{source_id}/status    — polling do status de processamento.
  GET  /knowledge/stats               — dados da view v_knowledge_status.
  GET  /health                        — health-check interno.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from minio import Minio
from minio.error import S3Error
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import PdfSource, get_db
from models import (
    KnowledgeStatsResponse,
    PdfSourceListResponse,
    PdfSourceResponse,
    PdfUploadResponse,
    ProcessingStatusResponse,
)
from worker import process_pdf

load_dotenv()

# ─── Configurações MinIO ──────────────────────────────────────────────────────

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "rpg-pdfs")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# ─── Cliente MinIO (singleton) ────────────────────────────────────────────────

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE,
)


def _ensure_bucket() -> None:
    """Cria o bucket no MinIO caso ainda não exista."""
    try:
        if not minio_client.bucket_exists(MINIO_BUCKET):
            minio_client.make_bucket(MINIO_BUCKET)
    except S3Error as exc:
        # Falha não-fatal na inicialização — o erro será capturado no upload.
        print(f"[MinIO] Aviso ao verificar bucket: {exc}")


# ─── Aplicação FastAPI ────────────────────────────────────────────────────────

app = FastAPI(
    title="RPG-IA — PDF Ingestion Service",
    description=(
        "Serviço de ingestão de PDFs: upload para MinIO, extração de texto, "
        "geração de embeddings e armazenamento no banco global de conhecimento."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    _ensure_bucket()


# ─── Health-check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "pdf_ingestion"}


# ─── POST /upload ─────────────────────────────────────────────────────────────

@app.post(
    "/upload",
    response_model=PdfUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["PDF"],
    summary="Faz upload de um PDF e inicia o processamento em background",
)
async def upload_pdf(
    file: UploadFile = File(..., description="Arquivo PDF a ser enviado"),
    title: str | None = Form(default=None, description="Título do documento (opcional, usa nome do arquivo)"),
    rpg_system: str | None = Form(default=None, description="Sistema de RPG"),
    source_type: str | None = Form(default=None, description="Tipo de fonte"),
    db: AsyncSession = Depends(get_db),
) -> PdfUploadResponse:
    """
    1. Valida o arquivo (apenas PDF).
    2. Faz upload para o MinIO com nome único.
    3. Cria registro em pdf_sources com processed=False.
    4. Enfileira task Celery `process_pdf`.
    5. Retorna source_id imediatamente — cliente faz polling em /sources/{id}/status.
    """

    # Validação de tipo de arquivo
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Apenas arquivos PDF são aceitos.",
            )

    # Deriva título do nome do arquivo se não informado
    if not title:
        title = (file.filename or "documento").rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()

    # Gera nome único no MinIO para evitar colisões
    unique_prefix = uuid.uuid4().hex
    safe_filename = (file.filename or "documento.pdf").replace(" ", "_")
    minio_object_name = f"pdfs/{unique_prefix}_{safe_filename}"

    # Upload para MinIO
    file_data = await file.read()
    file_size = len(file_data)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo enviado está vazio.",
        )

    try:
        import io

        minio_client.put_object(
            bucket_name=MINIO_BUCKET,
            object_name=minio_object_name,
            data=io.BytesIO(file_data),
            length=file_size,
            content_type="application/pdf",
        )
    except S3Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Falha ao salvar o arquivo no armazenamento: {exc}",
        )

    # Cria registro em pdf_sources
    source = PdfSource(
        title=title,
        rpg_system=rpg_system,
        source_type=source_type,
        filename=safe_filename,
        minio_path=minio_object_name,
        processed=False,
        chunk_count=0,
    )

    try:
        db.add(source)
        await db.commit()
        await db.refresh(source)
    except Exception as exc:
        await db.rollback()
        # Tenta remover o objeto já enviado para manter consistência
        try:
            minio_client.remove_object(MINIO_BUCKET, minio_object_name)
        except S3Error:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao registrar o PDF no banco de dados: {exc}",
        )

    # Enfileira task Celery (fire-and-forget)
    process_pdf.apply_async(
        args=[str(source.id)],
        queue="pdf_processing",
    )

    return PdfUploadResponse(
        source_id=source.id,
        title=source.title,
        filename=source.filename,
        minio_path=source.minio_path,
        status="enqueued",
        message="PDF enviado com sucesso. Processamento iniciado em background.",
    )


# ─── GET /sources ─────────────────────────────────────────────────────────────

@app.get(
    "/sources",
    response_model=PdfSourceListResponse,
    tags=["PDF"],
    summary="Lista todos os PDFs enviados para a plataforma",
)
async def list_sources(
    db: AsyncSession = Depends(get_db),
) -> PdfSourceListResponse:
    """Retorna todos os registros de pdf_sources ordenados por data de criação (mais recente primeiro)."""

    try:
        result = await db.execute(
            text("SELECT * FROM pdf_sources ORDER BY created_at DESC")
        )
        rows = result.mappings().all()
        sources = [PdfSourceResponse(**dict(row)) for row in rows]
        return PdfSourceListResponse(total=len(sources), sources=sources)
    except Exception as exc:
        print(f"[list_sources] ERRO: {exc}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar fontes: {exc}",
        )


# ─── DELETE /sources/{source_id} ─────────────────────────────────────────────

@app.delete(
    "/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["PDF"],
    summary="Remove um PDF do banco de conhecimento",
)
async def delete_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(
        text("SELECT id FROM pdf_sources WHERE id = :id"),
        {"id": str(source_id)},
    )
    if result.one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fonte PDF com id '{source_id}' não encontrada.",
        )

    await db.execute(
        text("DELETE FROM knowledge_chunks WHERE source_id = :id"),
        {"id": str(source_id)},
    )
    await db.execute(
        text("DELETE FROM pdf_sources WHERE id = :id"),
        {"id": str(source_id)},
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── GET /sources/{source_id}/status ─────────────────────────────────────────

@app.get(
    "/sources/{source_id}/status",
    response_model=ProcessingStatusResponse,
    tags=["PDF"],
    summary="Verifica o status de processamento de um PDF (polling)",
)
async def get_source_status(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProcessingStatusResponse:
    """
    Endpoint de polling.
    Retorna status: 'pending' | 'completed' | 'error'.
    O cliente deve consultar a cada 2–5 segundos até receber 'completed' ou 'error'.
    """

    result = await db.execute(
        text("SELECT * FROM pdf_sources WHERE id = :id"),
        {"id": str(source_id)},
    )
    row = result.mappings().one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fonte PDF com id '{source_id}' não encontrada.",
        )

    # Constrói objeto ORM-like a partir do mapping para reutilizar o factory method
    class _Row:
        def __init__(self, data: dict[str, Any]) -> None:
            self.__dict__.update(data)

    return ProcessingStatusResponse.from_orm_source(_Row(dict(row)))


# ─── POST /sources/{source_id}/retry ─────────────────────────────────────────

@app.post(
    "/sources/{source_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["PDF"],
    summary="Reenfileira o processamento de um PDF que falhou",
)
async def retry_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Reseta o estado do pdf_source (processed=False, error_msg=None, chunk_count=0)
    e reenfileira a task Celery para reprocessamento.
    """
    result = await db.execute(
        text("SELECT * FROM pdf_sources WHERE id = :id"),
        {"id": str(source_id)},
    )
    row = result.mappings().one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fonte PDF com id '{source_id}' não encontrada.",
        )

    await db.execute(
        text(
            "UPDATE pdf_sources SET processed = false, error_msg = null, chunk_count = 0, "
            "updated_at = now() WHERE id = :id"
        ),
        {"id": str(source_id)},
    )
    await db.commit()

    process_pdf.apply_async(
        args=[str(source_id)],
        queue="pdf_processing",
    )

    return {"source_id": str(source_id), "status": "enqueued", "message": "Reprocessamento iniciado."}


# ─── GET /knowledge/stats ─────────────────────────────────────────────────────

@app.get(
    "/knowledge/stats",
    response_model=KnowledgeStatsResponse,
    tags=["Conhecimento"],
    summary="Retorna estatísticas do banco global de conhecimento",
)
async def knowledge_stats(
    db: AsyncSession = Depends(get_db),
) -> KnowledgeStatsResponse:
    """
    Consulta a view v_knowledge_status e retorna:
    - total_chunks, gm_is_ready, total_systems, sistemas_cobertos, total_sources
    """

    result = await db.execute(text("SELECT * FROM v_knowledge_status LIMIT 1"))
    row = result.mappings().one_or_none()

    processing_result = await db.execute(
        text("SELECT COUNT(*) FROM pdf_sources WHERE processed = false AND error_msg IS NULL")
    )
    processing_count = int(processing_result.scalar() or 0)

    if row is None:
        return KnowledgeStatsResponse(
            total_chunks=0,
            gm_is_ready=False,
            total_systems=0,
            systems_covered=[],
            total_sources=0,
            processing_count=processing_count,
        )

    data = dict(row)
    systems_covered = [s for s in (data.get("sistemas_cobertos") or []) if s]

    return KnowledgeStatsResponse(
        total_chunks=int(data.get("total_chunks", 0)),
        gm_is_ready=bool(data.get("gm_is_ready", False)),
        total_systems=int(data.get("total_systems", 0)),
        systems_covered=systems_covered,
        total_sources=int(data.get("total_sources", 0)),
        processing_count=processing_count,
    )
