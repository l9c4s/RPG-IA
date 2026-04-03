"""
Modelos Pydantic v2 para o serviço de ingestão de PDFs.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ─── Requisição de upload ─────────────────────────────────────────────────────

class PdfUploadMetadata(BaseModel):
    """Metadados enviados junto com o arquivo PDF no formulário multipart."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=512, description="Título do documento")
    rpg_system: str | None = Field(
        default=None,
        max_length=128,
        description="Sistema de RPG (ex.: 'D&D 5e', 'Pathfinder', 'homebrew')",
    )
    source_type: str | None = Field(
        default=None,
        max_length=64,
        description="Tipo de fonte: rulebook, adventure, bestiary, lore, supplement",
    )


# ─── Resposta de upload ───────────────────────────────────────────────────────

class PdfUploadResponse(BaseModel):
    """Retornado imediatamente após o upload — o processamento ocorre em background."""

    model_config = ConfigDict(from_attributes=True)

    source_id: uuid.UUID = Field(..., description="ID único da fonte PDF")
    title: str
    filename: str
    minio_path: str
    status: str = Field(default="enqueued", description="Estado inicial da tarefa")
    message: str = Field(
        default="PDF enviado com sucesso. Processamento iniciado em background.",
    )


# ─── Resposta de listagem ─────────────────────────────────────────────────────

class PdfSourceResponse(BaseModel):
    """Representação completa de uma entrada em pdf_sources."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    rpg_system: str | None
    source_type: str | None
    filename: str
    minio_path: str
    uploaded_by: uuid.UUID | None
    processed: bool
    chunk_count: int
    error_msg: str | None
    created_at: datetime | None
    updated_at: datetime | None


class PdfSourceListResponse(BaseModel):
    """Lista paginada de fontes PDF."""

    total: int
    sources: list[PdfSourceResponse]


# ─── Resposta de status ───────────────────────────────────────────────────────

class ProcessingStatusResponse(BaseModel):
    """Resposta do endpoint de polling /sources/{source_id}/status."""

    model_config = ConfigDict(from_attributes=True)

    source_id: uuid.UUID
    title: str
    processed: bool
    chunk_count: int
    error_msg: str | None
    status: str = Field(description="'pending' | 'completed' | 'error'")

    @classmethod
    def from_orm_source(cls, source: Any) -> "ProcessingStatusResponse":
        if source.error_msg:
            status = "error"
        elif source.processed:
            status = "completed"
        else:
            status = "pending"

        return cls(
            source_id=source.id,
            title=source.title,
            processed=source.processed,
            chunk_count=source.chunk_count,
            error_msg=source.error_msg,
            status=status,
        )


# ─── Resposta de estatísticas do banco de conhecimento ───────────────────────

class KnowledgeStatsResponse(BaseModel):
    """Dados da view v_knowledge_status."""

    total_chunks: int
    gm_is_ready: bool
    total_systems: int
    systems_covered: list[str]
    total_sources: int
    processing_count: int
