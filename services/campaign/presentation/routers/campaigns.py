"""
Rotas HTTP de Campanha — borda da aplicação.
Apenas traduz HTTP ↔ use cases. Zero lógica de negócio aqui.
"""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from application.campaign.dtos import (
    AddAIPlayerDTO,
    CreateCampaignDTO,
    GenerateMapDTO,
    UpdateCampaignStatusDTO,
)
from application.campaign.use_cases import (
    AddAIPlayerUseCase,
    CreateCampaignUseCase,
    DeleteCampaignUseCase,
    GenerateMapUseCase,
    GetCampaignLocationsUseCase,
    GetCampaignUseCase,
    GetLobbyUseCase,
    ListCampaignsUseCase,
    UpdateCampaignStatusUseCase,
)
from presentation.dependencies import (
    get_add_ai_player_uc,
    get_campaign_uc,
    get_campaign_locations_uc,
    get_create_campaign_uc,
    get_delete_campaign_uc,
    get_generate_map_uc,
    get_lobby_uc,
    get_list_campaigns_uc,
    get_update_status_uc,
)
from presentation.schemas.campaign import (
    CampaignCreateRequest,
    CampaignResponse,
    CampaignStatusUpdateRequest,
    LobbyResponse,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", status_code=status.HTTP_200_OK)
async def list_campaigns(
    uc: ListCampaignsUseCase = Depends(get_list_campaigns_uc),
) -> list[CampaignResponse]:
    items = await uc.execute()
    return [CampaignResponse(**vars(item)) for item in items]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CampaignCreateRequest,
    uc: CreateCampaignUseCase = Depends(get_create_campaign_uc),
) -> CampaignResponse:
    dto = CreateCampaignDTO(
        title=body.title,
        rpg_system=body.rpg_system,
        difficulty=body.difficulty,
        tone=body.tone,
        description=body.description,
    )
    result = await uc.execute(dto)
    return CampaignResponse(**vars(result))


@router.get("/{campaign_id}", status_code=status.HTTP_200_OK)
async def get_campaign(
    campaign_id: UUID,
    uc: GetCampaignUseCase = Depends(get_campaign_uc),
) -> CampaignResponse:
    try:
        result = await uc.execute(campaign_id)
        return CampaignResponse(**vars(result))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{campaign_id}/lobby", status_code=status.HTTP_200_OK)
async def get_lobby(
    campaign_id: UUID,
    uc: GetLobbyUseCase = Depends(get_lobby_uc),
) -> LobbyResponse:
    try:
        result = await uc.execute(campaign_id)
        return LobbyResponse(
            campaign=CampaignResponse(**vars(result.campaign)),
            characters=result.characters,
            can_start=result.can_start,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{campaign_id}/status", status_code=status.HTTP_200_OK)
async def update_campaign_status(
    campaign_id: UUID,
    body: CampaignStatusUpdateRequest,
    uc: UpdateCampaignStatusUseCase = Depends(get_update_status_uc),
) -> dict:
    try:
        result = await uc.execute(
            UpdateCampaignStatusDTO(campaign_id=campaign_id, new_status=body.status)
        )
        return {"id": result.id, "status": result.status}
    except ValueError as exc:
        code = (
            status.HTTP_404_NOT_FOUND
            if "não encontrada" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=str(exc))


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: UUID,
    uc: DeleteCampaignUseCase = Depends(get_delete_campaign_uc),
) -> None:
    try:
        await uc.execute(campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{campaign_id}/ai-player", status_code=status.HTTP_201_CREATED)
async def add_ai_player(
    campaign_id: UUID,
    uc: AddAIPlayerUseCase = Depends(get_add_ai_player_uc),
) -> dict:
    try:
        return await uc.execute(AddAIPlayerDTO(campaign_id=campaign_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao adicionar IA: {exc}",
        )


@router.post("/{campaign_id}/generate-map", status_code=status.HTTP_200_OK)
async def generate_map(
    campaign_id: UUID,
    uc: GenerateMapUseCase = Depends(get_generate_map_uc),
) -> dict:
    try:
        locations = await uc.execute(GenerateMapDTO(campaign_id=campaign_id))
        return {"locations": locations}
    except ValueError as exc:
        code = (
            status.HTTP_400_BAD_REQUEST
            if "personagem" in str(exc).lower()
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=code, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar o mapa da campanha. Tente novamente.",
        )


@router.get("/{campaign_id}/locations", status_code=status.HTTP_200_OK)
async def get_locations(
    campaign_id: UUID,
    uc: GetCampaignLocationsUseCase = Depends(get_campaign_locations_uc),
) -> list:
    try:
        return await uc.execute(campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
