"""Integration tests for CharacterRepository — hits a real PostgreSQL test database."""
import pytest
import pytest_asyncio
from uuid import uuid4

from domain.character.entity import (
    Ability,
    Character,
    CharacterAttributes,
    CharacterStatus,
    InventoryItem,
)
from domain.character.value_objects import AbilityType
from infrastructure.repositories.character_repository import CharacterRepository

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


class TestGetById:
    async def test_returns_none_for_unknown_id(self, db_session):
        repo = CharacterRepository(db_session)
        result = await repo.get_by_id(uuid4())
        assert result is None

    async def test_returns_character_after_save(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)
        found = await repo.get_by_id(saved.id)
        assert found is not None
        assert found.name == sample_character.name

    async def test_returns_none_after_soft_delete(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)
        saved.soft_delete()
        await repo.save(saved)
        found = await repo.get_by_id(saved.id)
        assert found is None


# ---------------------------------------------------------------------------
# list_by_campaign
# ---------------------------------------------------------------------------


class TestListByCampaign:
    async def test_returns_characters_for_campaign(self, db_session):
        campaign_id = uuid4()
        repo = CharacterRepository(db_session)

        c1 = Character.create(name="Frodo", race="Hobbit", class_="Rogue", campaign_id=campaign_id)
        c2 = Character.create(name="Sam", race="Hobbit", class_="Fighter", campaign_id=campaign_id)
        c2.attributes = CharacterAttributes.create_default(c2.id)

        await repo.save(c1)
        await repo.save(c2)

        result = await repo.list_by_campaign(campaign_id)
        names = {c.name for c in result}
        assert "Frodo" in names
        assert "Sam" in names

    async def test_excludes_other_campaigns(self, db_session):
        campaign_id = uuid4()
        other_campaign_id = uuid4()
        repo = CharacterRepository(db_session)

        c = Character.create(name="Sauron", race="Maia", class_="Warlock", campaign_id=other_campaign_id)
        await repo.save(c)

        result = await repo.list_by_campaign(campaign_id)
        assert all(r.campaign_id == campaign_id for r in result)

    async def test_excludes_soft_deleted(self, db_session):
        campaign_id = uuid4()
        repo = CharacterRepository(db_session)

        c = Character.create(name="Gandalf", race="Maia", class_="Wizard", campaign_id=campaign_id)
        saved = await repo.save(c)
        saved.soft_delete()
        await repo.save(saved)

        result = await repo.list_by_campaign(campaign_id)
        assert not any(r.name == "Gandalf" for r in result)

    async def test_empty_campaign_returns_empty(self, db_session):
        repo = CharacterRepository(db_session)
        result = await repo.list_by_campaign(uuid4())
        assert result == []


# ---------------------------------------------------------------------------
# save (create)
# ---------------------------------------------------------------------------


class TestSaveCreate:
    async def test_creates_character_with_status(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)

        assert saved.id == sample_character.id
        assert saved.name == sample_character.name
        assert saved.status is not None
        assert saved.status.hp_current == 0

    async def test_creates_character_with_attributes(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)
        assert saved.attributes is not None
        assert saved.attributes.strength == 15

    async def test_proficiency_bonus_persisted(self, db_session):
        repo = CharacterRepository(db_session)
        char = Character.create(name="X", race="Y", class_="Z", level=5)
        saved = await repo.save(char)
        assert saved.proficiency_bonus == 3


# ---------------------------------------------------------------------------
# save (update)
# ---------------------------------------------------------------------------


class TestSaveUpdate:
    async def test_updates_name(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)
        saved.apply_update({"name": "Strider"})
        updated = await repo.save(saved)
        assert updated.name == "Strider"

    async def test_updates_level_and_proficiency(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)
        saved.level_up()
        updated = await repo.save(saved)
        assert updated.level == 2
        assert updated.proficiency_bonus == 2

    async def test_soft_delete_persists(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)
        saved.soft_delete()
        updated = await repo.save(saved)
        assert updated.is_alive is False


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


class TestInventory:
    async def test_add_and_retrieve_item(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)

        item = InventoryItem.create(saved.id, "Longsword", item_type="weapon")
        added = await repo.add_inventory_item(item)

        assert added.item_name == "Longsword"
        assert added.character_id == saved.id

    async def test_get_inventory_item(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)

        item = InventoryItem.create(saved.id, "Shield", item_type="armor")
        added = await repo.add_inventory_item(item)

        found = await repo.get_inventory_item(saved.id, added.id)
        assert found is not None
        assert found.item_name == "Shield"

    async def test_get_inventory_item_wrong_character_returns_none(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)

        item = InventoryItem.create(saved.id, "Torch")
        added = await repo.add_inventory_item(item)

        found = await repo.get_inventory_item(uuid4(), added.id)
        assert found is None

    async def test_remove_inventory_item(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)

        item = InventoryItem.create(saved.id, "Dagger")
        added = await repo.add_inventory_item(item)

        await repo.remove_inventory_item(added.id)
        found = await repo.get_inventory_item(saved.id, added.id)
        assert found is None


# ---------------------------------------------------------------------------
# Abilities
# ---------------------------------------------------------------------------


class TestAbilities:
    async def test_add_ability(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)

        ability = Ability.create(saved.id, "Second Wind", uses_max=1)
        added = await repo.add_ability(ability)

        assert added.ability_name == "Second Wind"
        assert added.uses_remaining == 1

    async def test_add_spell(self, db_session, sample_character):
        repo = CharacterRepository(db_session)
        saved = await repo.save(sample_character)

        spell = Ability.create(
            saved.id, "Fireball", ability_type=AbilityType.SPELL, spell_level=3
        )
        added = await repo.add_ability(spell)

        assert added.spell_level == 3
        assert added.ability_type == AbilityType.SPELL
