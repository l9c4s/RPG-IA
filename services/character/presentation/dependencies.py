from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

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
from infrastructure.database.connection import get_db
from infrastructure.repositories.character_repository import CharacterRepository


def get_character_repo(db: AsyncSession = Depends(get_db)) -> CharacterRepository:
    return CharacterRepository(db)


def get_create_character_uc(
    repo: CharacterRepository = Depends(get_character_repo),
) -> CreateCharacterUseCase:
    return CreateCharacterUseCase(repo)


def get_get_character_uc(
    repo: CharacterRepository = Depends(get_character_repo),
) -> GetCharacterUseCase:
    return GetCharacterUseCase(repo)


def get_update_character_uc(
    repo: CharacterRepository = Depends(get_character_repo),
) -> UpdateCharacterUseCase:
    return UpdateCharacterUseCase(repo)


def get_delete_character_uc(
    repo: CharacterRepository = Depends(get_character_repo),
) -> DeleteCharacterUseCase:
    return DeleteCharacterUseCase(repo)


def get_list_campaign_characters_uc(
    repo: CharacterRepository = Depends(get_character_repo),
) -> ListCampaignCharactersUseCase:
    return ListCampaignCharactersUseCase(repo)


def get_update_character_status_uc(
    repo: CharacterRepository = Depends(get_character_repo),
) -> UpdateCharacterStatusUseCase:
    return UpdateCharacterStatusUseCase(repo)


def get_add_inventory_item_uc(
    repo: CharacterRepository = Depends(get_character_repo),
) -> AddInventoryItemUseCase:
    return AddInventoryItemUseCase(repo)


def get_remove_inventory_item_uc(
    repo: CharacterRepository = Depends(get_character_repo),
) -> RemoveInventoryItemUseCase:
    return RemoveInventoryItemUseCase(repo)


def get_add_ability_uc(
    repo: CharacterRepository = Depends(get_character_repo),
) -> AddAbilityUseCase:
    return AddAbilityUseCase(repo)


def get_level_up_uc(
    repo: CharacterRepository = Depends(get_character_repo),
) -> LevelUpUseCase:
    return LevelUpUseCase(repo)
