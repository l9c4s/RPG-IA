"""Concrete GeneratedImageRepository — implements IGeneratedImageRepository."""
from __future__ import annotations

from datetime import timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.image.entity import GeneratedImage
from domain.image.value_objects import ImageSize, ImageStatus, ImageType, ImageUrl, Prompt
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
            status=ImageStatus(orm.status) if orm.status else ImageStatus.completed,
            prompt_used=Prompt(orm.prompt_used) if orm.prompt_used else None,
            minio_path=orm.minio_path,
            image_url=ImageUrl(orm.image_url) if orm.image_url else None,
            character_id=orm.character_id,
            campaign_id=orm.campaign_id,
            location_id=orm.location_id,
            created_at=created_at,
        )

    def _apply_to_orm(self, image: GeneratedImage, orm: GeneratedImageDB) -> None:
        orm.image_type = image.image_type.value
        orm.description = image.description
        orm.status = image.status.value
        orm.prompt_used = str(image.prompt_used) if image.prompt_used else None
        orm.minio_path = image.minio_path
        orm.image_url = str(image.image_url) if image.image_url else None
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

    async def get_latest_by_character(self, character_id: UUID) -> GeneratedImage | None:
        result = await self._session.execute(
            select(GeneratedImageDB)
            .where(GeneratedImageDB.character_id == character_id)
            .order_by(GeneratedImageDB.created_at.desc())
            .limit(1)
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_latest_map_by_campaign(self, campaign_id: UUID) -> GeneratedImage | None:
        result = await self._session.execute(
            select(GeneratedImageDB)
            .where(
                GeneratedImageDB.campaign_id == campaign_id,
                GeneratedImageDB.image_type == "map",
                GeneratedImageDB.status == "completed",
            )
            .order_by(GeneratedImageDB.created_at.desc())
            .limit(1)
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None
