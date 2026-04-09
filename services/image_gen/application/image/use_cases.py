"""Application use cases for the image generation bounded context."""
from __future__ import annotations

from uuid import UUID, uuid4

from application.image.dtos import (
    GenerateCharacterImageDTO,
    GenerateMapDTO,
    GenerateNpcImageDTO,
    GenerateSceneDTO,
    GeneratedImageDTO,
)
from domain.image.entity import GeneratedImage
from domain.image.repository import IGeneratedImageRepository, IImageGeneratorPort, IStoragePort
from domain.image.value_objects import ImageSize, ImageStatus, ImageType, ImageUrl, Prompt


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _to_dto(image: GeneratedImage) -> GeneratedImageDTO:
    return GeneratedImageDTO(
        id=image.id,
        image_type=image.image_type.value,
        description=image.description,
        status=image.status.value,
        image_url=str(image.image_url) if image.image_url else None,
        minio_path=image.minio_path,
        character_id=image.character_id,
        campaign_id=image.campaign_id,
        location_id=image.location_id,
        created_at=image.created_at,
    )


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------


class CreatePendingImageUseCase:
    """Cria um registro pending e retorna imediatamente. A geração ocorre em background."""

    def __init__(self, repo: IGeneratedImageRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        image_type: ImageType,
        description: str,
        character_id: UUID | None = None,
        campaign_id: UUID | None = None,
        location_id: UUID | None = None,
    ) -> GeneratedImageDTO:
        image = GeneratedImage.create_pending(
            image_type=image_type,
            description=description,
            character_id=character_id,
            campaign_id=campaign_id,
            location_id=location_id,
        )
        saved = await self._repo.save(image)
        return _to_dto(saved)


class FinalizeImageUseCase:
    """Gera a imagem, faz upload e atualiza o registro de pending → completed/failed."""

    def __init__(
        self,
        repo: IGeneratedImageRepository,
        generator: IImageGeneratorPort,
        storage: IStoragePort,
    ) -> None:
        self._repo = repo
        self._generator = generator
        self._storage = storage

    async def execute(
        self,
        image_id: UUID,
        prompt: Prompt,
        size: ImageSize,
    ) -> GeneratedImageDTO:
        image = await self._repo.get_by_id(image_id)
        if image is None:
            raise ValueError(f"Image {image_id} não encontrada.")
        try:
            image_bytes = await self._generator.generate(prompt, size)
            object_name = f"images/{uuid4()}.png"
            public_url = await self._storage.upload(image_bytes, object_name)
            image.complete(prompt, object_name, ImageUrl(public_url))
        except Exception:
            image.fail()
            await self._repo.save(image)
            raise
        saved = await self._repo.save(image)
        return _to_dto(saved)


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
        self._pending = CreatePendingImageUseCase(repo)
        self._finalize = FinalizeImageUseCase(repo, generator, storage)

    async def create_pending(self, dto: GenerateCharacterImageDTO) -> GeneratedImageDTO:
        return await self._pending.execute(
            image_type=ImageType.character,
            description=dto.description,
            character_id=dto.character_id,
            campaign_id=dto.campaign_id,
        )

    async def finalize(self, image_id: UUID, description: str) -> GeneratedImageDTO:
        return await self._finalize.execute(
            image_id=image_id,
            prompt=Prompt.build_character(description),
            size=ImageSize.square,
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
        self._pending = CreatePendingImageUseCase(repo)
        self._finalize = FinalizeImageUseCase(repo, generator, storage)

    async def create_pending(self, dto: GenerateNpcImageDTO) -> GeneratedImageDTO:
        return await self._pending.execute(
            image_type=ImageType.npc,
            description=dto.description,
            character_id=dto.character_id,
            campaign_id=dto.campaign_id,
        )

    async def finalize(self, image_id: UUID, description: str) -> GeneratedImageDTO:
        return await self._finalize.execute(
            image_id=image_id,
            prompt=Prompt.build_npc(description),
            size=ImageSize.square,
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
        self._pending = CreatePendingImageUseCase(repo)
        self._finalize = FinalizeImageUseCase(repo, generator, storage)

    async def create_pending(self, dto: GenerateSceneDTO) -> GeneratedImageDTO:
        return await self._pending.execute(
            image_type=ImageType.scene,
            description=dto.description,
            campaign_id=dto.campaign_id,
        )

    async def finalize(self, image_id: UUID, description: str) -> GeneratedImageDTO:
        return await self._finalize.execute(
            image_id=image_id,
            prompt=Prompt.build_scene(description),
            size=ImageSize.wide,
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
        self._pending = CreatePendingImageUseCase(repo)
        self._finalize = FinalizeImageUseCase(repo, generator, storage)

    async def create_pending(self, dto: GenerateMapDTO) -> GeneratedImageDTO:
        return await self._pending.execute(
            image_type=ImageType.map,
            description=dto.description,
            location_id=dto.location_id,
            campaign_id=dto.campaign_id,
        )

    async def finalize(self, image_id: UUID, description: str) -> GeneratedImageDTO:
        return await self._finalize.execute(
            image_id=image_id,
            prompt=Prompt.build_map(description),
            size=ImageSize.square,
        )
