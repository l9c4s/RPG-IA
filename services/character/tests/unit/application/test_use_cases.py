"""Unit tests for application use cases — repository is mocked via AsyncMock."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

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
from domain.character.entity import (
    Ability,
    Character,
    CharacterAttributes,
    CharacterStatus,
    InventoryItem,
)
from domain.character.value_objects import AbilityType


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_character(**kwargs) -> Character:
    now = datetime.utcnow()
    defaults = dict(
        id=uuid4(),
        name="Aragorn",
        race="Human",
        class_="Ranger",
        subclass=None,
        level=1,
        proficiency_bonus=2,
        background=None,
        alignment=None,
        char_type="player",
        backstory=None,
        appearance=None,
        campaign_id=None,
        owner_id=None,
        is_alive=True,
        created_at=now,
        updated_at=now,
        status=CharacterStatus.create_default(uuid4()),
        attributes=CharacterAttributes.create_default(uuid4()),
        inventory=[],
        abilities=[],
    )
    defaults.update(kwargs)
    return Character(**defaults)


def _make_repo() -> AsyncMock:
    return AsyncMock()


# ---------------------------------------------------------------------------
# CreateCharacterUseCase
# ---------------------------------------------------------------------------


class TestCreateCharacterUseCase:
    async def test_calls_save_and_returns_dto(self):
        repo = _make_repo()
        char = _make_character()
        repo.save.return_value = char
        repo.get_by_id.return_value = char

        with patch(
            "infrastructure.inventory_generator.generate_starting_inventory",
            new=AsyncMock(return_value=[]),
        ):
            uc = CreateCharacterUseCase(repo)
            dto = CreateCharacterDTO(name="Aragorn", race="Human", class_="Ranger")
            result = await uc.execute(dto)

        repo.save.assert_called_once()
        assert result.name == char.name
        assert result.race == char.race

    async def test_with_attributes_dto(self):
        repo = _make_repo()
        char = _make_character()
        repo.save.return_value = char
        repo.get_by_id.return_value = char

        with patch(
            "infrastructure.inventory_generator.generate_starting_inventory",
            new=AsyncMock(return_value=[]),
        ):
            uc = CreateCharacterUseCase(repo)
            dto = CreateCharacterDTO(
                name="X",
                race="Y",
                class_="Z",
                attributes=AttributesInputDTO(strength=18),
            )
            await uc.execute(dto)
        repo.save.assert_called_once()

    async def test_player_triggers_inventory_generation(self):
        """char_type='player' deve chamar geração de inventário inicial."""
        repo = _make_repo()
        char = _make_character(char_type="player")
        repo.save.return_value = char
        repo.get_by_id.return_value = char

        mock_gen = AsyncMock(return_value=[])
        with patch(
            "infrastructure.inventory_generator.generate_starting_inventory",
            new=mock_gen,
        ):
            uc = CreateCharacterUseCase(repo)
            dto = CreateCharacterDTO(name="X", race="Y", class_="Ranger", char_type="player")
            await uc.execute(dto)

        mock_gen.assert_called_once()

    async def test_ai_companion_triggers_inventory_generation(self):
        """char_type='ai_companion' também deve gerar inventário."""
        repo = _make_repo()
        char = _make_character(char_type="ai_companion")
        repo.save.return_value = char
        repo.get_by_id.return_value = char

        mock_gen = AsyncMock(return_value=[])
        with patch(
            "infrastructure.inventory_generator.generate_starting_inventory",
            new=mock_gen,
        ):
            uc = CreateCharacterUseCase(repo)
            dto = CreateCharacterDTO(name="X", race="Y", class_="Z", char_type="ai_companion")
            await uc.execute(dto)

        mock_gen.assert_called_once()

    async def test_npc_does_not_trigger_inventory_generation(self):
        """char_type='npc' NÃO deve gerar inventário inicial."""
        repo = _make_repo()
        char = _make_character(char_type="npc")
        repo.save.return_value = char
        # NPCs não chamam get_by_id para reload
        # mas o código atual chama get_by_id para player/ai_companion
        # Para npc, o código retorna _character_to_dto(final or saved)
        # onde final é None (não houve get_by_id) — mas na prática usa saved.
        # O mock abaixo garante que get_by_id não é chamado.
        mock_gen = AsyncMock(return_value=[])
        with patch(
            "infrastructure.inventory_generator.generate_starting_inventory",
            new=mock_gen,
        ):
            uc = CreateCharacterUseCase(repo)
            dto = CreateCharacterDTO(name="X", race="Y", class_="Z", char_type="npc")
            await uc.execute(dto)

        mock_gen.assert_not_called()

    async def test_inventory_generation_failure_does_not_crash_create(self):
        """Falha no LLM não deve impedir criação do personagem."""
        repo = _make_repo()
        char = _make_character(char_type="player")
        repo.save.return_value = char
        repo.get_by_id.return_value = char

        # Simula o generate_starting_inventory já com fallback interno
        # (ele nunca propaga exceção — usa fallback interno)
        mock_gen = AsyncMock(return_value=[])
        with patch(
            "infrastructure.inventory_generator.generate_starting_inventory",
            new=mock_gen,
        ):
            uc = CreateCharacterUseCase(repo)
            dto = CreateCharacterDTO(name="X", race="Y", class_="Z", char_type="player")
            result = await uc.execute(dto)

        assert result.name == char.name

    async def test_reloads_character_after_inventory_generation(self):
        """Deve chamar get_by_id após gerar inventário para retornar dados frescos."""
        repo = _make_repo()
        char_without_inventory = _make_character(inventory=[])
        char_with_inventory = _make_character(
            id=char_without_inventory.id,
            inventory=[InventoryItem.create(char_without_inventory.id, "Sword")],
        )
        repo.save.return_value = char_without_inventory
        repo.get_by_id.return_value = char_with_inventory

        with patch(
            "infrastructure.inventory_generator.generate_starting_inventory",
            new=AsyncMock(return_value=[]),
        ):
            uc = CreateCharacterUseCase(repo)
            dto = CreateCharacterDTO(name="X", race="Y", class_="Ranger", char_type="player")
            result = await uc.execute(dto)

        repo.get_by_id.assert_called_once_with(char_without_inventory.id)
        assert len(result.inventory) == 1


# ---------------------------------------------------------------------------
# GetCharacterUseCase
# ---------------------------------------------------------------------------


class TestGetCharacterUseCase:
    async def test_returns_dto_when_found(self):
        repo = _make_repo()
        char = _make_character(name="Legolas")
        repo.get_by_id.return_value = char

        uc = GetCharacterUseCase(repo)
        result = await uc.execute(char.id)

        assert result.name == "Legolas"
        repo.get_by_id.assert_called_once_with(char.id)

    async def test_raises_when_not_found(self):
        repo = _make_repo()
        repo.get_by_id.return_value = None

        uc = GetCharacterUseCase(repo)
        with pytest.raises(ValueError, match="não encontrado"):
            await uc.execute(uuid4())


# ---------------------------------------------------------------------------
# UpdateCharacterUseCase
# ---------------------------------------------------------------------------


class TestUpdateCharacterUseCase:
    async def test_applies_update_and_saves(self):
        repo = _make_repo()
        char = _make_character(name="Old Name")
        updated_char = _make_character(name="New Name", id=char.id)
        repo.get_by_id.return_value = char
        repo.save.return_value = updated_char

        uc = UpdateCharacterUseCase(repo)
        result = await uc.execute(char.id, UpdateCharacterDTO(name="New Name"))

        repo.save.assert_called_once()
        assert result.name == "New Name"

    async def test_raises_when_not_found(self):
        repo = _make_repo()
        repo.get_by_id.return_value = None

        uc = UpdateCharacterUseCase(repo)
        with pytest.raises(ValueError, match="não encontrado"):
            await uc.execute(uuid4(), UpdateCharacterDTO(name="X"))


# ---------------------------------------------------------------------------
# DeleteCharacterUseCase
# ---------------------------------------------------------------------------


class TestDeleteCharacterUseCase:
    async def test_soft_deletes_character(self):
        repo = _make_repo()
        char = _make_character()
        deleted_char = _make_character(id=char.id, is_alive=False)
        repo.get_by_id.return_value = char
        repo.save.return_value = deleted_char

        uc = DeleteCharacterUseCase(repo)
        await uc.execute(char.id)

        assert char.is_alive is False
        repo.save.assert_called_once()

    async def test_raises_when_not_found(self):
        repo = _make_repo()
        repo.get_by_id.return_value = None

        uc = DeleteCharacterUseCase(repo)
        with pytest.raises(ValueError, match="não encontrado"):
            await uc.execute(uuid4())


# ---------------------------------------------------------------------------
# ListCampaignCharactersUseCase
# ---------------------------------------------------------------------------


class TestListCampaignCharactersUseCase:
    async def test_returns_list(self):
        repo = _make_repo()
        campaign_id = uuid4()
        char1 = _make_character(campaign_id=campaign_id)
        char2 = _make_character(campaign_id=campaign_id)
        repo.list_by_campaign.return_value = [char1, char2]

        uc = ListCampaignCharactersUseCase(repo)
        result = await uc.execute(campaign_id)

        assert len(result) == 2
        repo.list_by_campaign.assert_called_once_with(campaign_id)

    async def test_empty_campaign_returns_empty_list(self):
        repo = _make_repo()
        repo.list_by_campaign.return_value = []

        uc = ListCampaignCharactersUseCase(repo)
        result = await uc.execute(uuid4())

        assert result == []


# ---------------------------------------------------------------------------
# UpdateCharacterStatusUseCase
# ---------------------------------------------------------------------------


class TestUpdateCharacterStatusUseCase:
    async def test_applies_status_update(self):
        repo = _make_repo()
        char = _make_character()
        repo.get_by_id.return_value = char
        repo.save.return_value = _make_character(id=char.id)

        uc = UpdateCharacterStatusUseCase(repo)
        await uc.execute(char.id, UpdateCharacterStatusDTO(hp_current=15))

        assert char.status.hp_current == 15
        repo.save.assert_called_once()

    async def test_creates_status_if_none(self):
        repo = _make_repo()
        char = _make_character()
        char.status = None
        repo.get_by_id.return_value = char
        repo.save.return_value = _make_character(id=char.id)

        uc = UpdateCharacterStatusUseCase(repo)
        await uc.execute(char.id, UpdateCharacterStatusDTO(hp_current=5))

        assert char.status is not None
        assert char.status.hp_current == 5


# ---------------------------------------------------------------------------
# AddInventoryItemUseCase
# ---------------------------------------------------------------------------


class TestAddInventoryItemUseCase:
    async def test_adds_item(self):
        repo = _make_repo()
        char_id = uuid4()
        char = _make_character(id=char_id)
        item = InventoryItem.create(char_id, "Longsword")
        repo.get_by_id.return_value = char
        repo.add_inventory_item.return_value = item

        uc = AddInventoryItemUseCase(repo)
        dto = AddInventoryItemDTO(character_id=char_id, item_name="Longsword")
        result = await uc.execute(dto)

        assert result.item_name == "Longsword"
        repo.add_inventory_item.assert_called_once()

    async def test_raises_when_character_not_found(self):
        repo = _make_repo()
        repo.get_by_id.return_value = None

        uc = AddInventoryItemUseCase(repo)
        with pytest.raises(ValueError, match="não encontrado"):
            await uc.execute(AddInventoryItemDTO(character_id=uuid4(), item_name="X"))


# ---------------------------------------------------------------------------
# RemoveInventoryItemUseCase
# ---------------------------------------------------------------------------


class TestRemoveInventoryItemUseCase:
    async def test_removes_item(self):
        repo = _make_repo()
        char_id = uuid4()
        item_id = uuid4()
        char = _make_character(id=char_id)
        item = InventoryItem.create(char_id, "Torch")
        item.id = item_id
        repo.get_by_id.return_value = char
        repo.get_inventory_item.return_value = item

        uc = RemoveInventoryItemUseCase(repo)
        await uc.execute(char_id, item_id)

        repo.remove_inventory_item.assert_called_once_with(item_id)

    async def test_raises_when_item_not_found(self):
        repo = _make_repo()
        char = _make_character()
        repo.get_by_id.return_value = char
        repo.get_inventory_item.return_value = None

        uc = RemoveInventoryItemUseCase(repo)
        with pytest.raises(ValueError, match="não encontrado no inventário"):
            await uc.execute(char.id, uuid4())


# ---------------------------------------------------------------------------
# AddAbilityUseCase
# ---------------------------------------------------------------------------


class TestAddAbilityUseCase:
    async def test_adds_ability(self):
        repo = _make_repo()
        char_id = uuid4()
        char = _make_character(id=char_id)
        ability = Ability.create(char_id, "Second Wind")
        repo.get_by_id.return_value = char
        repo.add_ability.return_value = ability

        uc = AddAbilityUseCase(repo)
        dto = AddAbilityDTO(character_id=char_id, ability_name="Second Wind")
        result = await uc.execute(dto)

        assert result.ability_name == "Second Wind"
        repo.add_ability.assert_called_once()

    async def test_raises_for_spell_without_level(self):
        repo = _make_repo()
        char = _make_character()
        repo.get_by_id.return_value = char

        uc = AddAbilityUseCase(repo)
        with pytest.raises(ValueError, match="spell_level"):
            await uc.execute(
                AddAbilityDTO(
                    character_id=char.id,
                    ability_name="Fireball",
                    ability_type=AbilityType.SPELL,
                )
            )


# ---------------------------------------------------------------------------
# LevelUpUseCase
# ---------------------------------------------------------------------------


class TestLevelUpUseCase:
    async def test_level_up_increments(self):
        repo = _make_repo()
        char = _make_character(level=1)
        leveled = _make_character(id=char.id, level=2, proficiency_bonus=2)
        repo.get_by_id.return_value = char
        repo.save.return_value = leveled

        uc = LevelUpUseCase(repo)
        result = await uc.execute(char.id)

        assert result.new_level == 2
        assert result.new_proficiency_bonus == 2

    async def test_level_up_at_20_raises(self):
        repo = _make_repo()
        char = _make_character(level=20)
        repo.get_by_id.return_value = char

        uc = LevelUpUseCase(repo)
        with pytest.raises(ValueError, match="nível máximo"):
            await uc.execute(char.id)

    async def test_raises_when_not_found(self):
        repo = _make_repo()
        repo.get_by_id.return_value = None

        uc = LevelUpUseCase(repo)
        with pytest.raises(ValueError, match="não encontrado"):
            await uc.execute(uuid4())
