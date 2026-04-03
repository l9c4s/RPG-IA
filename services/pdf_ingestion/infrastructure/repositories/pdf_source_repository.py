"""Async PdfSource repository (FastAPI)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.pdf_source.entity import PdfSource
from infrastructure.database.orm_models import PdfSourceDB


class PdfSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Domain ↔ ORM conversion
    # ------------------------------------------------------------------

    def _to_domain(self, row: PdfSourceDB) -> PdfSource:
        return PdfSource(
            id=row.id,
            title=row.title,
            filename=row.filename,
            minio_path=row.minio_path,
            processed=row.processed,
            chunk_count=row.chunk_count,
            rpg_system=row.rpg_system,
            source_type=row.source_type,
            uploaded_by=row.uploaded_by,
            error_msg=row.error_msg,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _apply_to_orm(self, source: PdfSource, row: PdfSourceDB) -> None:
        row.title = source.title
        row.filename = source.filename
        row.minio_path = source.minio_path
        row.processed = source.processed
        row.chunk_count = source.chunk_count
        row.rpg_system = source.rpg_system
        row.source_type = source.source_type
        row.uploaded_by = source.uploaded_by
        row.error_msg = source.error_msg

    # ------------------------------------------------------------------
    # IPdfSourceRepository implementation
    # ------------------------------------------------------------------

    async def save(self, source: PdfSource) -> PdfSource:
        row = PdfSourceDB(id=source.id)
        self._apply_to_orm(source, row)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_domain(row)

    async def get_by_id(self, source_id: UUID) -> PdfSource | None:
        result = await self._session.execute(
            select(PdfSourceDB).where(PdfSourceDB.id == source_id)
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def list_all(self) -> list[PdfSource]:
        result = await self._session.execute(
            select(PdfSourceDB).order_by(PdfSourceDB.created_at.desc())
        )
        return [self._to_domain(r) for r in result.scalars().all()]

    async def update(self, source: PdfSource) -> PdfSource:
        result = await self._session.execute(
            select(PdfSourceDB).where(PdfSourceDB.id == source.id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"PdfSource {source.id} not found")
        self._apply_to_orm(source, row)
        await self._session.execute(
            text("UPDATE pdf_sources SET updated_at = NOW() WHERE id = :id"),
            {"id": str(source.id)},
        )
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_domain(row)

    async def delete(self, source_id: UUID) -> None:
        await self._session.execute(
            text("DELETE FROM pdf_sources WHERE id = :id"),
            {"id": str(source_id)},
        )
        await self._session.commit()

    async def count_pending(self) -> int:
        result = await self._session.execute(
            text(
                "SELECT COUNT(*) FROM pdf_sources "
                "WHERE processed = false AND error_msg IS NULL"
            )
        )
        return int(result.scalar() or 0)
