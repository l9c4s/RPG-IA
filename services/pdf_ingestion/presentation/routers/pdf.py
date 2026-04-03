"""PDF and knowledge routers."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from application.pdf_source.dtos import UploadPdfDTO
from application.pdf_source.use_cases import (
    DeleteSourceUseCase,
    GetKnowledgeStatsUseCase,
    GetSourceStatusUseCase,
    ListSourcesUseCase,
    RetrySourceUseCase,
    UploadPdfUseCase,
)
from infrastructure.database.connection import get_db
from infrastructure.repositories.knowledge_chunk_repository import AsyncKnowledgeChunkRepository
from infrastructure.repositories.pdf_source_repository import PdfSourceRepository
from presentation.dependencies import get_minio, get_task_queue
from presentation.schemas.pdf import (
    KnowledgeStatsResponse,
    PdfSourceListResponse,
    PdfSourceResponse,
    PdfUploadResponse,
    ProcessingStatusResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {"status": "ok", "service": "pdf_ingestion"}


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------


@router.post(
    "/upload",
    response_model=PdfUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["PDF"],
    summary="Faz upload de um PDF e inicia o processamento em background",
)
async def upload_pdf(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    rpg_system: str | None = Form(default=None),
    source_type: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    minio=Depends(get_minio),
    task_queue=Depends(get_task_queue),
) -> PdfUploadResponse:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")

    file_data = await file.read()

    derived_title = title or (
        (file.filename or "documento").rsplit(".", 1)[0]
        .replace("_", " ")
        .replace("-", " ")
        .strip()
    )

    dto = UploadPdfDTO(
        title=derived_title,
        filename=file.filename or "documento.pdf",
        file_data=file_data,
        rpg_system=rpg_system,
        source_type=source_type,
    )

    use_case = UploadPdfUseCase(
        repo=PdfSourceRepository(db),
        storage=minio,
        task_queue=task_queue,
    )

    try:
        result = await use_case.execute(dto)
    except ValueError as exc:
        code = str(exc)
        if code == "empty_file":
            raise HTTPException(status_code=400, detail="O arquivo enviado está vazio.")
        raise HTTPException(status_code=500, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return PdfUploadResponse(
        source_id=result.id,
        title=result.title,
        filename=result.filename,
        minio_path=result.minio_path,
        status="enqueued",
    )


# ---------------------------------------------------------------------------
# GET /sources
# ---------------------------------------------------------------------------


@router.get(
    "/sources",
    response_model=PdfSourceListResponse,
    tags=["PDF"],
    summary="Lista todos os PDFs enviados para a plataforma",
)
async def list_sources(db: AsyncSession = Depends(get_db)) -> PdfSourceListResponse:
    sources = await ListSourcesUseCase(PdfSourceRepository(db)).execute()
    items = [
        PdfSourceResponse(
            id=s.id,
            title=s.title,
            rpg_system=s.rpg_system,
            source_type=s.source_type,
            filename=s.filename,
            minio_path=s.minio_path,
            uploaded_by=s.uploaded_by,
            processed=s.processed,
            chunk_count=s.chunk_count,
            error_msg=s.error_msg,
            status=s.status,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sources
    ]
    return PdfSourceListResponse(total=len(items), sources=items)


# ---------------------------------------------------------------------------
# GET /sources/{source_id}/status
# ---------------------------------------------------------------------------


@router.get(
    "/sources/{source_id}/status",
    response_model=ProcessingStatusResponse,
    tags=["PDF"],
    summary="Verifica o status de processamento de um PDF (polling)",
)
async def get_source_status(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProcessingStatusResponse:
    try:
        result = await GetSourceStatusUseCase(PdfSourceRepository(db)).execute(source_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Fonte PDF '{source_id}' não encontrada.")
    return ProcessingStatusResponse(
        source_id=result.source_id,
        title=result.title,
        processed=result.processed,
        chunk_count=result.chunk_count,
        status=result.status,
        error_msg=result.error_msg,
    )


# ---------------------------------------------------------------------------
# DELETE /sources/{source_id}
# ---------------------------------------------------------------------------


@router.delete(
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
    try:
        await DeleteSourceUseCase(
            repo=PdfSourceRepository(db),
            chunk_repo=AsyncKnowledgeChunkRepository(db),
        ).execute(source_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Fonte PDF '{source_id}' não encontrada.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# POST /sources/{source_id}/retry
# ---------------------------------------------------------------------------


@router.post(
    "/sources/{source_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["PDF"],
    summary="Reenfileira o processamento de um PDF que falhou",
)
async def retry_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    task_queue=Depends(get_task_queue),
) -> dict:
    try:
        return await RetrySourceUseCase(
            repo=PdfSourceRepository(db),
            task_queue=task_queue,
        ).execute(source_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Fonte PDF '{source_id}' não encontrada.")


# ---------------------------------------------------------------------------
# GET /knowledge/stats
# ---------------------------------------------------------------------------


@router.get(
    "/knowledge/stats",
    response_model=KnowledgeStatsResponse,
    tags=["Conhecimento"],
    summary="Retorna estatísticas do banco global de conhecimento",
)
async def knowledge_stats(db: AsyncSession = Depends(get_db)) -> KnowledgeStatsResponse:
    result = await GetKnowledgeStatsUseCase(
        repo=PdfSourceRepository(db),
        chunk_repo=AsyncKnowledgeChunkRepository(db),
    ).execute()
    return KnowledgeStatsResponse(
        total_chunks=result.total_chunks,
        gm_is_ready=result.gm_is_ready,
        total_systems=result.total_systems,
        systems_covered=result.systems_covered,
        total_sources=result.total_sources,
        processing_count=result.processing_count,
    )
