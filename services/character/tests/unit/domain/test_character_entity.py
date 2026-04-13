"""Unit tests for domain entities — no DB, no HTTP, no frameworks."""
import pytest
from uuid import uuid4

from domain.character.entity import (
    Ability,
    Character,
    CharacterAttributes,
    CharacterStatus,
    InventoryItem,
    calc_proficiency_bonus,
)
from domain.character.value_objects import AbilityType, CharacterType


# ---------------------------------------------------------------------------
# calc_proficiency_bonus
# ---------------------------------------------------------------------------


class TestCalcProficiencyBonus:
    @pytest.mark.parametrize(
        "level, expected",
        [
            (1, 2), (2, 2), (3, 2), (4, 2),
            (5, 3), (6, 3), (7, 3), (8, 3),
            (9, 4), (10, 4), (11, 4), (12, 4),
            (13, 5), (14, 5), (15, 5), (16, 5),
            (17, 6), (18, 6), (19, 6), (20, 6),
        ],
    )
    def test_proficiency_table(self, level, expected):
        assert calc_proficiency_bonus(level) == expected


# ---------------------------------------------------------------------------
# Character entity
# ---------------------------------------------------------------------------


class TestCharacterCreate:
    def test_create_defaults(self):
        char = Character.create(name="Aragorn", race="Human", class_="Ranger")
        assert char.name == "Aragorn"
        assert char.race == "Human"
        assert char.class_ == "Ranger"
        assert char.level == 1
        assert char.proficiency_bonus == 2
        assert char.char_type == CharacterType.PLAYER
        assert char.is_alive is True
        assert char.id is not None

    def test_create_calculates_proficiency_for_level(self):
        char = Character.create(name="X", race="Elf", class_="Wizard", level=5)
        assert char.proficiency_bonus == 3

    def test_create_with_all_fields(self):
        campaign_id = uuid4()
        owner_id = uuid4()
        char = Character.create(
            name="Legolas",
            race="Elf",
            class_="Ranger",
            level=10,
            subclass="Hunter",
            background="Outlander",
            alignment="Chaotic Good",
            char_type=CharacterType.NPC,
            backstory="Born in Mirkwood.",
            appearance="Tall and fair.",
            campaign_id=campaign_id,
            owner_id=owner_id,
        )
        assert char.subclass == "Hunter"
        assert char.campaign_id == campaign_id
        assert char.char_type == CharacterType.NPC


class TestCharacterSoftDelete:
    def test_soft_delete_sets_is_alive_false(self):
        char = Character.create(name="X", race="Y", class_="Z")
        assert char.is_alive is True
        char.soft_delete()
        assert char.is_alive is False


class TestCharacterLevelUp:
    def test_level_up_increments_level(self):
        char = Character.create(name="X", race="Y", class_="Z", level=1)
        char.level_up()
        assert char.level == 2

    def test_level_up_recalculates_proficiency(self):
        char = Character.create(name="X", race="Y", class_="Z", level=4)
        char.level_up()
        assert char.level == 5
        assert char.proficiency_bonus == 3

    def test_level_up_at_20_raises(self):
        char = Character.create(name="X", race="Y", class_="Z", level=20)
        with pytest.raises(ValueError, match="nível máximo"):
            char.level_up()

    def test_level_up_chain_to_20(self):
        char = Character.create(name="X", race="Y", class_="Z", level=1)
        for _ in range(19):
            char.level_up()
        assert char.level == 20
        assert char.proficiency_bonus == 6


class TestCharacterApplyUpdate:
    def test_apply_update_name(self):
        char = Character.create(name="Old", race="Human", class_="Fighter")
        char.apply_update({"name": "New"})
        assert char.name == "New"

    def test_apply_update_ignores_unknown_fields(self):
        char = Character.create(name="X", race="Y", class_="Z")
        char.apply_update({"nonexistent_field": "value"})  # should not raise


# ---------------------------------------------------------------------------
# CharacterStatus
# ---------------------------------------------------------------------------


class TestCharacterStatus:
    def test_create_default(self):
        char_id = uuid4()
        s = CharacterStatus.create_default(char_id)
        assert s.character_id == char_id
        assert s.hp_max == 0
        assert s.hp_current == 0
        assert s.conditions == []
        assert s.spell_slots == {}
        assert s.exhaustion == 0

    def test_apply_update(self):
        char_id = uuid4()
        s = CharacterStatus.create_default(char_id)
        s.apply_update({"hp_current": 10, "exhaustion": 2})
        assert s.hp_current == 10
        assert s.exhaustion == 2

    def test_apply_update_conditions(self):
        char_id = uuid4()
        s = CharacterStatus.create_default(char_id)
        s.apply_update({"conditions": ["poisoned", "prone"]})
        assert "poisoned" in s.conditions


# ---------------------------------------------------------------------------
# CharacterAttributes
# ---------------------------------------------------------------------------


class TestCharacterAttributes:
    def test_create_default(self):
        char_id = uuid4()
        a = CharacterAttributes.create_default(char_id)
        assert a.strength == 10
        assert a.dexterity == 10
        assert a.armor_class == 10
        assert a.speed == 30

    def test_create_with_overrides(self):
        char_id = uuid4()
        a = CharacterAttributes.create_default(char_id, strength=18, dexterity=16)
        assert a.strength == 18
        assert a.dexterity == 16
        assert a.constitution == 10  # default


# ---------------------------------------------------------------------------
# InventoryItem
# ---------------------------------------------------------------------------


class TestInventoryItem:
    def test_create_defaults(self):
        char_id = uuid4()
        item = InventoryItem.create(char_id, "Longsword")
        assert item.item_name == "Longsword"
        assert item.item_type == "misc"
        assert item.quantity == 1
        assert item.weight == 0.0
        assert item.equipped is False
        assert item.properties == {}

    def test_create_with_fields(self):
        char_id = uuid4()
        item = InventoryItem.create(
            char_id,
            "Shield",
            item_type="armor",
            quantity=1,
            weight=6.0,
            value_gp=10.0,
            properties={"ac_bonus": 2},
            equipped=True,
        )
        assert item.item_type == "armor"
        assert item.properties["ac_bonus"] == 2
        assert item.equipped is True

    # ── Novos campos (Sprint 1: inventário inicial com stats) ──────────────────

    def test_create_defaults_new_fields(self):
        """Campos novos têm defaults corretos quando omitidos."""
        char_id = uuid4()
        item = InventoryItem.create(char_id, "Longsword")
        assert item.stat_bonuses == {}
        assert item.special_effects == []
        assert item.rarity == "common"
        assert item.is_starting_item is False
        assert item.description is None

    def test_create_with_stat_bonuses(self):
        char_id = uuid4()
        bonuses = {"strength": 2, "armor_class": 1}
        item = InventoryItem.create(
            char_id, "Mace of Power", stat_bonuses=bonuses
        )
        assert item.stat_bonuses == bonuses

    def test_create_with_special_effects(self):
        char_id = uuid4()
        fx = [{"trigger": "on_hit", "effect": "1d6 fire damage"}]
        item = InventoryItem.create(
            char_id, "Flaming Sword", special_effects=fx
        )
        assert item.special_effects == fx

    def test_create_with_rarity(self):
        char_id = uuid4()
        item = InventoryItem.create(char_id, "Rare Ring", rarity="rare")
        assert item.rarity == "rare"

    def test_create_as_starting_item(self):
        char_id = uuid4()
        item = InventoryItem.create(
            char_id, "Starting Sword", is_starting_item=True
        )
        assert item.is_starting_item is True

    def test_create_with_description(self):
        char_id = uuid4()
        desc = "Uma espada forjada pelos anões da Montanha Solitária."
        item = InventoryItem.create(char_id, "Dwarven Sword", description=desc)
        assert item.description == desc

    def test_create_full_starting_item(self):
        """Simula um item gerado pelo LLM para o inventário inicial."""
        char_id = uuid4()
        item = InventoryItem.create(
            char_id,
            "Arco Élfico de Aço",
            item_type="weapon",
            quantity=1,
            weight=1.5,
            value_gp=25.0,
            equipped=True,
            stat_bonuses={"attack_bonus": 1},
            special_effects=[{"trigger": "on_critical", "effect": "+1d6 piercing"}],
            rarity="common",
            is_starting_item=True,
            description="Um arco leve adornado com runas élficas.",
        )
        assert item.item_name == "Arco Élfico de Aço"
        assert item.stat_bonuses["attack_bonus"] == 1
        assert item.is_starting_item is True
        assert item.rarity == "common"
        assert "runas" in item.description


# ---------------------------------------------------------------------------
# Ability
# ---------------------------------------------------------------------------


class TestAbility:
    def test_create_defaults(self):
        char_id = uuid4()
        ability = Ability.create(char_id, "Second Wind")
        assert ability.ability_name == "Second Wind"
        assert ability.ability_type == AbilityType.FEATURE
        assert ability.uses_current is None

    def test_create_with_uses_initializes_remaining(self):
        char_id = uuid4()
        ability = Ability.create(char_id, "Action Surge", uses_max=1)
        assert ability.uses_max == 1
        assert ability.uses_current == 1

    def test_spell_without_level_raises(self):
        char_id = uuid4()
        with pytest.raises(ValueError, match="spell_level"):
            Ability.create(char_id, "Fireball", ability_type=AbilityType.SPELL)

    def test_spell_with_level_ok(self):
        char_id = uuid4()
        ability = Ability.create(
            char_id, "Fireball", ability_type=AbilityType.SPELL, spell_level=3
        )
        assert ability.spell_level == 3
