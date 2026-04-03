from __future__ import annotations

from uuid import UUID

from application.character.dtos import (
    AbilityDTO,
    AddAbilityDTO,
    AddInventoryItemDTO,
    CharacterAttributesDTO,
    CharacterDTO,
    CharacterStatusDTO,
    CreateCharacterDTO,
    InventoryItemDTO,
    LevelUpDTO,
    UpdateCharacterDTO,
    UpdateCharacterStatusDTO,
)
from domain.character.entity import Ability, Character, CharacterAttributes, InventoryItem
from domain.character.repository import ICharacterRepository


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _status_to_dto(s) -> CharacterStatusDTO | None:
    if s is None:
        return None
    return CharacterStatusDTO(
        id=s.id,
        character_id=s.character_id,
        hp_max=s.hp_max,
        hp_current=s.hp_current,
        hp_temp=s.hp_temp,
        conditions=s.conditions,
        spell_slots=s.spell_slots,
        exhaustion=s.exhaustion,
        death_saves_success=s.death_saves_success,
        death_saves_failure=s.death_saves_failure,
        updated_at=s.updated_at,
    )


def _attrs_to_dto(a) -> CharacterAttributesDTO | None:
    if a is None:
        return None
    return CharacterAttributesDTO(
        id=a.id,
        character_id=a.character_id,
        strength=a.strength,
        dexterity=a.dexterity,
        constitution=a.constitution,
        intelligence=a.intelligence,
        wisdom=a.wisdom,
        charisma=a.charisma,
        armor_class=a.armor_class,
        initiative=a.initiative,
        speed=a.speed,
    )


def _item_to_dto(i) -> InventoryItemDTO:
    return InventoryItemDTO(
        id=i.id,
        character_id=i.character_id,
        item_name=i.item_name,
        item_type=i.item_type,
        quantity=i.quantity,
        weight=i.weight,
        value_gp=i.value_gp,
        properties=i.properties,
        equipped=i.equipped,
        created_at=i.created_at,
    )


def _ability_to_dto(a) -> AbilityDTO:
    return AbilityDTO(
        id=a.id,
        character_id=a.character_id,
        ability_name=a.ability_name,
        ability_type=a.ability_type,
        description=a.description,
        spell_level=a.spell_level,
        uses_max=a.uses_max,
        uses_remaining=a.uses_remaining,
        recharge=a.recharge,
    )


def _character_to_dto(c: Character) -> CharacterDTO:
    return CharacterDTO(
        id=c.id,
        name=c.name,
        race=c.race,
        class_=c.class_,
        subclass=c.subclass,
        level=c.level,
        proficiency_bonus=c.proficiency_bonus,
        background=c.background,
        alignment=c.alignment,
        char_type=c.char_type,
        backstory=c.backstory,
        appearance=c.appearance,
        campaign_id=c.campaign_id,
        owner_id=c.owner_id,
        is_alive=c.is_alive,
        created_at=c.created_at,
        updated_at=c.updated_at,
        status=_status_to_dto(c.status),
        attributes=_attrs_to_dto(c.attributes),
        inventory=[_item_to_dto(i) for i in c.inventory],
        abilities=[_ability_to_dto(a) for a in c.abilities],
    )


# ---------------------------------------------------------------------------
# Use Cases
# ---------------------------------------------------------------------------


class CreateCharacterUseCase:
    def __init__(self, repo: ICharacterRepository) -> None:
        self._repo = repo

    async def execute(self, dto: CreateCharacterDTO) -> CharacterDTO:
        attrs_overrides = {}
        if dto.attributes:
            attrs_overrides = {
                k: v
                for k, v in dto.attributes.__dict__.items()
                if v is not None
            }

        character = Character.create(
            name=dto.name,
            race=dto.race,
            class_=dto.class_,
            level=dto.level,
            subclass=dto.subclass,
            background=dto.background,
            alignment=dto.alignment,
            char_type=dto.char_type,
            backstory=dto.backstory,
            appearance=dto.appearance,
            campaign_id=dto.campaign_id,
            owner_id=dto.owner_id,
        )
        character.status = None  # repo will initialize
        character.attributes = CharacterAttributes.create_default(
            character.id, **attrs_overrides
        )

        saved = await self._repo.save(character)
        return _character_to_dto(saved)


class GetCharacterUseCase:
    def __init__(self, repo: ICharacterRepository) -> None:
        self._repo = repo

    async def execute(self, character_id: UUID) -> CharacterDTO:
        character = await self._repo.get_by_id(character_id)
        if character is None:
            raise ValueError(f"Personagem {character_id} não encontrado ou foi removido.")
        return _character_to_dto(character)


class UpdateCharacterUseCase:
    def __init__(self, repo: ICharacterRepository) -> None:
        self._repo = repo

    async def execute(self, character_id: UUID, dto: UpdateCharacterDTO) -> CharacterDTO:
        character = await self._repo.get_by_id(character_id)
        if character is None:
            raise ValueError(f"Personagem {character_id} não encontrado ou foi removido.")

        updates = {k: v for k, v in dto.__dict__.items() if v is not None}
        character.apply_update(updates)

        saved = await self._repo.save(character)
        return _character_to_dto(saved)


class DeleteCharacterUseCase:
    def __init__(self, repo: ICharacterRepository) -> None:
        self._repo = repo

    async def execute(self, character_id: UUID) -> None:
        character = await self._repo.get_by_id(character_id)
        if character is None:
            raise ValueError(f"Personagem {character_id} não encontrado ou foi removido.")
        character.soft_delete()
        await self._repo.save(character)


class ListCampaignCharactersUseCase:
    def __init__(self, repo: ICharacterRepository) -> None:
        self._repo = repo

    async def execute(self, campaign_id: UUID) -> list[CharacterDTO]:
        characters = await self._repo.list_by_campaign(campaign_id)
        return [_character_to_dto(c) for c in characters]


class UpdateCharacterStatusUseCase:
    def __init__(self, repo: ICharacterRepository) -> None:
        self._repo = repo

    async def execute(self, character_id: UUID, dto: UpdateCharacterStatusDTO) -> CharacterDTO:
        character = await self._repo.get_by_id(character_id)
        if character is None:
            raise ValueError(f"Personagem {character_id} não encontrado ou foi removido.")

        if character.status is None:
            from domain.character.entity import CharacterStatus
            character.status = CharacterStatus.create_default(character_id)

        updates = {k: v for k, v in dto.__dict__.items() if v is not None}
        character.status.apply_update(updates)

        saved = await self._repo.save(character)
        return _character_to_dto(saved)


class AddInventoryItemUseCase:
    def __init__(self, repo: ICharacterRepository) -> None:
        self._repo = repo

    async def execute(self, dto: AddInventoryItemDTO) -> InventoryItemDTO:
        character = await self._repo.get_by_id(dto.character_id)
        if character is None:
            raise ValueError(f"Personagem {dto.character_id} não encontrado ou foi removido.")

        item = InventoryItem.create(
            character_id=dto.character_id,
            item_name=dto.item_name,
            item_type=dto.item_type,
            quantity=dto.quantity,
            weight=dto.weight,
            value_gp=dto.value_gp,
            properties=dto.properties,
            equipped=dto.equipped,
        )
        saved = await self._repo.add_inventory_item(item)
        return _item_to_dto(saved)


class RemoveInventoryItemUseCase:
    def __init__(self, repo: ICharacterRepository) -> None:
        self._repo = repo

    async def execute(self, character_id: UUID, item_id: UUID) -> None:
        character = await self._repo.get_by_id(character_id)
        if character is None:
            raise ValueError(f"Personagem {character_id} não encontrado ou foi removido.")

        item = await self._repo.get_inventory_item(character_id, item_id)
        if item is None:
            raise ValueError(f"Item {item_id} não encontrado no inventário do personagem.")

        await self._repo.remove_inventory_item(item_id)


class AddAbilityUseCase:
    def __init__(self, repo: ICharacterRepository) -> None:
        self._repo = repo

    async def execute(self, dto: AddAbilityDTO) -> AbilityDTO:
        character = await self._repo.get_by_id(dto.character_id)
        if character is None:
            raise ValueError(f"Personagem {dto.character_id} não encontrado ou foi removido.")

        ability = Ability.create(
            character_id=dto.character_id,
            ability_name=dto.ability_name,
            ability_type=dto.ability_type,
            description=dto.description,
            spell_level=dto.spell_level,
            uses_max=dto.uses_max,
            recharge=dto.recharge,
        )
        saved = await self._repo.add_ability(ability)
        return _ability_to_dto(saved)


class LevelUpUseCase:
    def __init__(self, repo: ICharacterRepository) -> None:
        self._repo = repo

    async def execute(self, character_id: UUID) -> LevelUpDTO:
        character = await self._repo.get_by_id(character_id)
        if character is None:
            raise ValueError(f"Personagem {character_id} não encontrado ou foi removido.")

        character.level_up()  # raises ValueError if level >= 20
        saved = await self._repo.save(character)

        return LevelUpDTO(
            character_id=saved.id,
            new_level=saved.level,
            new_proficiency_bonus=saved.proficiency_bonus,
            message=(
                f"{saved.name} avançou para o nível {saved.level}! "
                f"Bônus de proficiência atualizado para +{saved.proficiency_bonus}."
            ),
        )
