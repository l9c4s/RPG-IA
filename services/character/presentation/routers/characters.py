from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse

from application.character.dtos import (
    AddAbilityDTO,
    AddInventoryItemDTO,
    AttributesInputDTO,
    CreateCharacterDTO,
    UpdateCharacterDTO,
    UpdateCharacterStatusDTO,
)
from application.character.use_cases import (
    AddAbilityUseCase,
    AddInventoryItemUseCase,
    CreateCharacterUseCase,
    DeleteCharacterUseCase,
    GetCharacterUseCase,
    LevelUpUseCase,
    ListCampaignCharactersUseCase,
    RemoveInventoryItemUseCase,
    UpdateCharacterStatusUseCase,
    UpdateCharacterUseCase,
)
from presentation.dependencies import (
    get_add_ability_uc,
    get_add_inventory_item_uc,
    get_create_character_uc,
    get_delete_character_uc,
    get_get_character_uc,
    get_level_up_uc,
    get_list_campaign_characters_uc,
    get_remove_inventory_item_uc,
    get_update_character_status_uc,
    get_update_character_uc,
)
from presentation.schemas.character import (
    AbilityCreateRequest,
    AbilityResponse,
    CharacterCreateRequest,
    CharacterResponse,
    CharacterStatusUpdateRequest,
    InventoryItemCreateRequest,
    InventoryItemResponse,
    LevelUpResponse,
    CharacterUpdateRequest,
)

router = APIRouter()


def _map_character_dto_to_response(dto) -> CharacterResponse:
    return CharacterResponse(
        id=dto.id,
        name=dto.name,
        class_=dto.class_,
        race=dto.race,
        subclass=dto.subclass,
        level=dto.level,
        proficiency_bonus=dto.proficiency_bonus,
        background=dto.background,
        alignment=dto.alignment,
        char_type=dto.char_type,
        backstory=dto.backstory,
        appearance=dto.appearance,
        campaign_id=dto.campaign_id,
        owner_id=dto.owner_id,
        is_alive=dto.is_alive,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
        status=dto.status,
        attributes=dto.attributes,
        inventory=dto.inventory,
        abilities=dto.abilities,
    )


# ---------------------------------------------------------------------------
# Characters CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/characters",
    response_model=CharacterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar personagem",
)
async def create_character(
    payload: CharacterCreateRequest,
    uc: CreateCharacterUseCase = Depends(get_create_character_uc),
) -> CharacterResponse:
    attrs_dto = None
    if payload.attributes:
        attrs_dto = AttributesInputDTO(**payload.attributes.model_dump())

    dto = CreateCharacterDTO(
        name=payload.name,
        race=payload.race,
        class_=payload.class_,
        level=payload.level,
        subclass=payload.subclass,
        background=payload.background,
        alignment=payload.alignment,
        char_type=payload.char_type,
        backstory=payload.backstory,
        appearance=payload.appearance,
        campaign_id=payload.campaign_id,
        owner_id=payload.owner_id,
        attributes=attrs_dto,
    )
    result = await uc.execute(dto)
    return _map_character_dto_to_response(result)


@router.get(
    "/characters/{character_id}",
    response_model=CharacterResponse,
    summary="Obter personagem completo",
)
async def get_character(
    character_id: UUID = Path(description="ID do personagem"),
    uc: GetCharacterUseCase = Depends(get_get_character_uc),
) -> CharacterResponse:
    try:
        result = await uc.execute(character_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _map_character_dto_to_response(result)


@router.patch(
    "/characters/{character_id}",
    response_model=CharacterResponse,
    summary="Atualizar campos do personagem",
)
async def update_character(
    payload: CharacterUpdateRequest,
    character_id: UUID = Path(description="ID do personagem"),
    uc: UpdateCharacterUseCase = Depends(get_update_character_uc),
) -> CharacterResponse:
    dto = UpdateCharacterDTO(
        name=payload.name,
        race=payload.race,
        class_=payload.class_,
        subclass=payload.subclass,
        background=payload.background,
        alignment=payload.alignment,
        char_type=payload.char_type,
        backstory=payload.backstory,
        appearance=payload.appearance,
        campaign_id=payload.campaign_id,
        owner_id=payload.owner_id,
    )
    try:
        result = await uc.execute(character_id, dto)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _map_character_dto_to_response(result)


@router.delete(
    "/characters/{character_id}",
    status_code=status.HTTP_200_OK,
    summary="Remover personagem (soft delete)",
)
async def delete_character(
    character_id: UUID = Path(description="ID do personagem"),
    uc: DeleteCharacterUseCase = Depends(get_delete_character_uc),
) -> JSONResponse:
    try:
        await uc.execute(character_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return JSONResponse(
        content={"mensagem": "Personagem removido com sucesso.", "id": str(character_id)}
    )


# ---------------------------------------------------------------------------
# Campaign characters
# ---------------------------------------------------------------------------


@router.get(
    "/campaigns/{campaign_id}/characters",
    response_model=list[CharacterResponse],
    summary="Listar personagens de uma campanha",
)
async def list_campaign_characters(
    campaign_id: UUID = Path(description="ID da campanha"),
    uc: ListCampaignCharactersUseCase = Depends(get_list_campaign_characters_uc),
) -> list[CharacterResponse]:
    results = await uc.execute(campaign_id)
    return [_map_character_dto_to_response(r) for r in results]


# ---------------------------------------------------------------------------
# Combat status
# ---------------------------------------------------------------------------


@router.patch(
    "/characters/{character_id}/status",
    response_model=CharacterResponse,
    summary="Atualizar status de combate",
)
async def update_character_status(
    payload: CharacterStatusUpdateRequest,
    character_id: UUID = Path(description="ID do personagem"),
    uc: UpdateCharacterStatusUseCase = Depends(get_update_character_status_uc),
) -> CharacterResponse:
    dto = UpdateCharacterStatusDTO(
        hp_current=payload.hp_current,
        hp_temp=payload.hp_temp,
        hp_max=payload.hp_max,
        conditions=payload.conditions,
        spell_slots=payload.spell_slots,
        exhaustion=payload.exhaustion,
        death_saves_success=payload.death_saves_success,
        death_saves_failure=payload.death_saves_failure,
    )
    try:
        result = await uc.execute(character_id, dto)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _map_character_dto_to_response(result)


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


@router.post(
    "/characters/{character_id}/inventory",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar item ao inventário",
)
async def add_inventory_item(
    payload: InventoryItemCreateRequest,
    character_id: UUID = Path(description="ID do personagem"),
    uc: AddInventoryItemUseCase = Depends(get_add_inventory_item_uc),
) -> InventoryItemResponse:
    dto = AddInventoryItemDTO(
        character_id=character_id,
        item_name=payload.item_name,
        item_type=payload.item_type,
        quantity=payload.quantity,
        weight=payload.weight,
        value_gp=payload.value_gp,
        properties=payload.properties,
        equipped=payload.equipped,
    )
    try:
        result = await uc.execute(dto)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return InventoryItemResponse(**result.__dict__)


@router.delete(
    "/characters/{character_id}/inventory/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Remover item do inventário",
)
async def remove_inventory_item(
    character_id: UUID = Path(description="ID do personagem"),
    item_id: UUID = Path(description="ID do item"),
    uc: RemoveInventoryItemUseCase = Depends(get_remove_inventory_item_uc),
) -> JSONResponse:
    try:
        await uc.execute(character_id, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return JSONResponse(
        content={"mensagem": "Item removido do inventário com sucesso.", "item_id": str(item_id)}
    )


# ---------------------------------------------------------------------------
# Abilities
# ---------------------------------------------------------------------------


@router.post(
    "/characters/{character_id}/abilities",
    response_model=AbilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar habilidade ou magia",
)
async def add_ability(
    payload: AbilityCreateRequest,
    character_id: UUID = Path(description="ID do personagem"),
    uc: AddAbilityUseCase = Depends(get_add_ability_uc),
) -> AbilityResponse:
    dto = AddAbilityDTO(
        character_id=character_id,
        ability_name=payload.ability_name,
        ability_type=payload.ability_type,
        description=payload.description,
        spell_level=payload.spell_level,
        uses_max=payload.uses_max,
        recharge=payload.recharge,
    )
    try:
        result = await uc.execute(dto)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return AbilityResponse(**result.__dict__)


# ---------------------------------------------------------------------------
# Level up
# ---------------------------------------------------------------------------


@router.post(
    "/characters/{character_id}/levelup",
    response_model=LevelUpResponse,
    summary="Subir de nível",
)
async def level_up(
    character_id: UUID = Path(description="ID do personagem"),
    uc: LevelUpUseCase = Depends(get_level_up_uc),
) -> LevelUpResponse:
    try:
        result = await uc.execute(character_id)
    except ValueError as exc:
        detail = str(exc)
        if "não encontrado" in detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    return LevelUpResponse(**result.__dict__)
