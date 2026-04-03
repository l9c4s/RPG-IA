"""Concrete GeneratedImageRepository — implements IGeneratedImageRepository."""
from __future__ import annotations

from datetime import timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.image.entity import GeneratedImage
from domain.image.value_objects import ImageSize, ImageType, ImageUrl, Prompt
from infrastructure.database.orm_models import GeneratedImageDB


class GeneratedImageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # ORM ↔ Domain conversion
    # ------------------------------------------------------------------

    def _to_domain(self, orm: GeneratedImageDB) -> GeneratedImage:
        created_at = orm.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return GeneratedImage(
            id=orm.id if isinstance(orm.id, UUID) else UUID(str(orm.id)),
            image_type=ImageType(orm.image_type),
            description=orm.description,
            prompt_used=Prompt(orm.prompt_used),
            minio_path=orm.minio_path,
            image_url=ImageUrl(orm.image_url),
            character_id=orm.character_id,
            campaign_id=orm.campaign_id,
            location_id=orm.location_id,
            created_at=created_at,
        )

    def _apply_to_orm(self, image: GeneratedImage, orm: GeneratedImageDB) -> None:
        orm.image_type = image.image_type.value
        orm.description = image.description
        orm.prompt_used = str(image.prompt_used)
        orm.minio_path = image.minio_path
        orm.image_url = str(image.image_url)
        orm.character_id = image.character_id
        orm.campaign_id = image.campaign_id
        orm.location_id = image.location_id

    # ------------------------------------------------------------------
    # IGeneratedImageRepository implementation
    # ------------------------------------------------------------------

    async def save(self, image: GeneratedImage) -> GeneratedImage:
        result = await self._session.execute(
            select(GeneratedImageDB).where(GeneratedImageDB.id == image.id)
        )
        orm = result.scalar_one_or_none()

        if orm is None:
            orm = GeneratedImageDB(id=image.id)
            self._apply_to_orm(image, orm)
            self._session.add(orm)
        else:
            self._apply_to_orm(image, orm)

        await self._session.flush()
        await self._session.refresh(orm)
        return self._to_domain(orm)

    async def get_by_id(self, image_id: UUID) -> GeneratedImage | None:
        result = await self._session.execute(
            select(GeneratedImageDB).where(GeneratedImageDB.id == image_id)
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def list_by_campaign(self, campaign_id: UUID) -> list[GeneratedImage]:
        result = await self._session.execute(
            select(GeneratedImageDB).where(GeneratedImageDB.campaign_id == campaign_id)
        )
        return [self._to_domain(row) for row in result.scalars().all()]
