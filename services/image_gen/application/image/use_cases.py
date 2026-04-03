"""Application use cases for the image generation bounded context."""
from __future__ import annotations

from uuid import uuid4

from application.image.dtos import (
    GenerateCharacterImageDTO,
    GenerateMapDTO,
    GenerateNpcImageDTO,
    GenerateSceneDTO,
    GeneratedImageDTO,
)
from domain.image.entity import GeneratedImage
from domain.image.repository import IGeneratedImageRepository, IImageGeneratorPort, IStoragePort
from domain.image.value_objects import ImageSize, ImageType, ImageUrl, Prompt


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _to_dto(image: GeneratedImage) -> GeneratedImageDTO:
    return GeneratedImageDTO(
        id=image.id,
        image_type=image.image_type.value,
        description=image.description,
        image_url=str(image.image_url),
        minio_path=image.minio_path,
        character_id=image.character_id,
        campaign_id=image.campaign_id,
        location_id=image.location_id,
        created_at=image.created_at,
    )


async def _generate_store_save(
    *,
    image_type: ImageType,
    description: str,
    prompt: Prompt,
    size: ImageSize,
    character_id=None,
    campaign_id=None,
    location_id=None,
    generator: IImageGeneratorPort,
    storage: IStoragePort,
    repo: IGeneratedImageRepository,
) -> GeneratedImageDTO:
    image_bytes = await generator.generate(prompt, size)
    object_name = f"images/{uuid4()}.png"
    public_url = await storage.upload(image_bytes, object_name)

    image = GeneratedImage.create(
        image_type=image_type,
        description=description,
        prompt=prompt,
        minio_path=object_name,
        image_url=ImageUrl(public_url),
        character_id=character_id,
        campaign_id=campaign_id,
        location_id=location_id,
    )
    saved = await repo.save(image)
    return _to_dto(saved)


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------


class GenerateCharacterImageUseCase:
    def __init__(
        self,
        repo: IGeneratedImageRepository,
        generator: IImageGeneratorPort,
        storage: IStoragePort,
    ) -> None:
        self._repo = repo
        self._generator = generator
        self._storage = storage

    async def execute(self, dto: GenerateCharacterImageDTO) -> GeneratedImageDTO:
        return await _generate_store_save(
            image_type=ImageType.character,
            description=dto.description,
            prompt=Prompt.build_character(dto.description),
            size=ImageSize.square,
            character_id=dto.character_id,
            campaign_id=dto.campaign_id,
            generator=self._generator,
            storage=self._storage,
            repo=self._repo,
        )


class GenerateNpcImageUseCase:
    def __init__(
        self,
        repo: IGeneratedImageRepository,
        generator: IImageGeneratorPort,
        storage: IStoragePort,
    ) -> None:
        self._repo = repo
        self._generator = generator
        self._storage = storage

    async def execute(self, dto: GenerateNpcImageDTO) -> GeneratedImageDTO:
        return await _generate_store_save(
            image_type=ImageType.npc,
            description=dto.description,
            prompt=Prompt.build_npc(dto.description),
            size=ImageSize.square,
            character_id=dto.character_id,
            campaign_id=dto.campaign_id,
            generator=self._generator,
            storage=self._storage,
            repo=self._repo,
        )


class GenerateSceneUseCase:
    def __init__(
        self,
        repo: IGeneratedImageRepository,
        generator: IImageGeneratorPort,
        storage: IStoragePort,
    ) -> None:
        self._repo = repo
        self._generator = generator
        self._storage = storage

    async def execute(self, dto: GenerateSceneDTO) -> GeneratedImageDTO:
        return await _generate_store_save(
            image_type=ImageType.scene,
            description=dto.description,
            prompt=Prompt.build_scene(dto.description),
            size=ImageSize.wide,
            campaign_id=dto.campaign_id,
            generator=self._generator,
            storage=self._storage,
            repo=self._repo,
        )


class GenerateMapUseCase:
    def __init__(
        self,
        repo: IGeneratedImageRepository,
        generator: IImageGeneratorPort,
        storage: IStoragePort,
    ) -> None:
        self._repo = repo
        self._generator = generator
        self._storage = storage

    async def execute(self, dto: GenerateMapDTO) -> GeneratedImageDTO:
        return await _generate_store_save(
            image_type=ImageType.map,
            description=dto.description,
            prompt=Prompt.build_map(dto.description),
            size=ImageSize.square,
            location_id=dto.location_id,
            campaign_id=dto.campaign_id,
            generator=self._generator,
            storage=self._storage,
            repo=self._repo,
        )
