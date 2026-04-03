"""Pydantic v2 HTTP schemas for the pdf_ingestion service."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PdfUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_id: uuid.UUID
    title: str
    filename: str
    minio_path: str
    status: str = "enqueued"
    message: str = "PDF enviado com sucesso. Processamento iniciado em background."


class PdfSourceResponse(BaseModel):
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
    status: str
    created_at: datetime | None
    updated_at: datetime | None


class PdfSourceListResponse(BaseModel):
    total: int
    sources: list[PdfSourceResponse]


class ProcessingStatusResponse(BaseModel):
    source_id: uuid.UUID
    title: str
    processed: bool
    chunk_count: int
    status: str
    error_msg: str | None = None


class KnowledgeStatsResponse(BaseModel):
    total_chunks: int
    gm_is_ready: bool
    total_systems: int
    systems_covered: list[str]
    total_sources: int
    processing_count: int
