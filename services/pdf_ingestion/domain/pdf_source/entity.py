"""PdfSource aggregate root."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class PdfSource:
    id: UUID
    title: str
    filename: str
    minio_path: str
    processed: bool
    chunk_count: int
    rpg_system: str | None = None
    source_type: str | None = None
    uploaded_by: UUID | None = None
    error_msg: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        title: str,
        filename: str,
        minio_path: str,
        rpg_system: str | None = None,
        source_type: str | None = None,
        uploaded_by: UUID | None = None,
    ) -> "PdfSource":
        return cls(
            id=uuid4(),
            title=title,
            filename=filename,
            minio_path=minio_path,
            processed=False,
            chunk_count=0,
            rpg_system=rpg_system,
            source_type=source_type,
            uploaded_by=uploaded_by,
        )

    @property
    def status(self) -> str:
        if self.error_msg:
            return "error"
        if self.processed:
            return "completed"
        return "pending"

    def mark_processed(self, chunk_count: int) -> None:
        self.processed = True
        self.chunk_count = chunk_count
        self.error_msg = None

    def mark_error(self, message: str) -> None:
        self.error_msg = message[:1024]

    def reset_for_retry(self) -> None:
        self.processed = False
        self.error_msg = None
        self.chunk_count = 0
