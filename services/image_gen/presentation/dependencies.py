"""FastAPI dependency injection wiring."""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.image.use_cases import (
    GenerateCharacterImageUseCase,
    GenerateMapUseCase,
    GenerateNpcImageUseCase,
    GenerateSceneUseCase,
)
from infrastructure.ai.dalle_service import DalleService
from infrastructure.database.connection import get_db
from infrastructure.repositories.image_repository import GeneratedImageRepository
from infrastructure.storage.minio_service import MinioService

# Singletons — instanciados uma vez na inicialização do módulo
_dalle = DalleService()
_minio = MinioService()


def get_dalle() -> DalleService:
    return _dalle


def get_minio() -> MinioService:
    return _minio


def get_image_repo(session: AsyncSession = Depends(get_db)) -> GeneratedImageRepository:
    return GeneratedImageRepository(session)


def get_generate_character_uc(
    repo: GeneratedImageRepository = Depends(get_image_repo),
    dalle: DalleService = Depends(get_dalle),
    minio: MinioService = Depends(get_minio),
) -> GenerateCharacterImageUseCase:
    return GenerateCharacterImageUseCase(repo=repo, generator=dalle, storage=minio)


def get_generate_npc_uc(
    repo: GeneratedImageRepository = Depends(get_image_repo),
    dalle: DalleService = Depends(get_dalle),
    minio: MinioService = Depends(get_minio),
) -> GenerateNpcImageUseCase:
    return GenerateNpcImageUseCase(repo=repo, generator=dalle, storage=minio)


def get_generate_scene_uc(
    repo: GeneratedImageRepository = Depends(get_image_repo),
    dalle: DalleService = Depends(get_dalle),
    minio: MinioService = Depends(get_minio),
) -> GenerateSceneUseCase:
    return GenerateSceneUseCase(repo=repo, generator=dalle, storage=minio)


def get_generate_map_uc(
    repo: GeneratedImageRepository = Depends(get_image_repo),
    dalle: DalleService = Depends(get_dalle),
    minio: MinioService = Depends(get_minio),
) -> GenerateMapUseCase:
    return GenerateMapUseCase(repo=repo, generator=dalle, storage=minio)
