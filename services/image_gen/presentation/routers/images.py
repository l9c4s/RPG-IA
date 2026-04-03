"""Image generation router — /generate/*."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from application.image.dtos import (
    GenerateCharacterImageDTO,
    GenerateMapDTO,
    GenerateNpcImageDTO,
    GenerateSceneDTO,
)
from application.image.use_cases import (
    GenerateCharacterImageUseCase,
    GenerateMapUseCase,
    GenerateNpcImageUseCase,
    GenerateSceneUseCase,
)
from presentation.dependencies import (
    get_generate_character_uc,
    get_generate_map_uc,
    get_generate_npc_uc,
    get_generate_scene_uc,
)
from presentation.schemas.image import (
    GenerateCharacterRequest,
    GenerateMapRequest,
    GenerateSceneRequest,
    ImageResponse,
)

router = APIRouter(tags=["Image Generation"])


def _dto_to_response(dto) -> ImageResponse:
    return ImageResponse(
        image_id=str(dto.id),
        image_url=dto.image_url,
        image_type=dto.image_type,
    )


@router.post("/generate/character", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
async def generate_character(
    body: GenerateCharacterRequest,
    uc: GenerateCharacterImageUseCase = Depends(get_generate_character_uc),
):
    try:
        dto = await uc.execute(GenerateCharacterImageDTO(
            description=body.description,
            character_id=body.character_id,
            campaign_id=body.campaign_id,
        ))
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    return _dto_to_response(dto)


@router.post("/generate/npc", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
async def generate_npc(
    body: GenerateCharacterRequest,
    uc: GenerateNpcImageUseCase = Depends(get_generate_npc_uc),
):
    try:
        dto = await uc.execute(GenerateNpcImageDTO(
            description=body.description,
            character_id=body.character_id,
            campaign_id=body.campaign_id,
        ))
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    return _dto_to_response(dto)


@router.post("/generate/scene", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
async def generate_scene(
    body: GenerateSceneRequest,
    uc: GenerateSceneUseCase = Depends(get_generate_scene_uc),
):
    try:
        dto = await uc.execute(GenerateSceneDTO(
            description=body.description,
            campaign_id=body.campaign_id,
        ))
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    return _dto_to_response(dto)


@router.post("/generate/map", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
async def generate_map(
    body: GenerateMapRequest,
    uc: GenerateMapUseCase = Depends(get_generate_map_uc),
):
    try:
        dto = await uc.execute(GenerateMapDTO(
            description=body.description,
            location_id=body.location_id,
            campaign_id=body.campaign_id,
        ))
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    return _dto_to_response(dto)
