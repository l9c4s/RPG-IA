"""Application DTOs for the pdf_source context."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class UploadPdfDTO:
    title: str
    filename: str
    file_data: bytes
    rpg_system: str | None = None
    source_type: str | None = None


@dataclass(frozen=True)
class PdfSourceDTO:
    id: UUID
    title: str
    filename: str
    minio_path: str
    processed: bool
    chunk_count: int
    status: str
    rpg_system: str | None = None
    source_type: str | None = None
    uploaded_by: UUID | None = None
    error_msg: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ProcessingStatusDTO:
    source_id: UUID
    title: str
    processed: bool
    chunk_count: int
    status: str
    error_msg: str | None = None


@dataclass
class KnowledgeStatsDTO:
    total_chunks: int
    gm_is_ready: bool
    total_systems: int
    systems_covered: list[str]
    total_sources: int
    processing_count: int
