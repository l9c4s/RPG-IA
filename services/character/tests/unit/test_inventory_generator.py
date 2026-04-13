"""Unit tests for inventory_generator.py — sem DB, sem OpenAI (funções puras + mocks)."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import json
import pytest
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from infrastructure.inventory_generator import (
    _DEFAULT_SLOTS,
    _SLOT_TO_TYPE,
    _STARTING_SLOTS,
    _attach_character_id,
    _fallback_inventory,
    generate_starting_inventory,
)


# ---------------------------------------------------------------------------
# _STARTING_SLOTS — lookup estático
# ---------------------------------------------------------------------------


class TestStartingSlots:
    def test_all_classes_have_6_slots(self):
        for class_, slots in _STARTING_SLOTS.items():
            assert len(slots) == 6, f"Classe '{class_}' tem {len(slots)} slots, esperado 6"

    def test_portuguese_classes_present(self):
        pt_classes = ["bárbaro", "bardo", "clérigo", "druida", "guerreiro",
                      "monge", "paladino", "patrulheiro", "ladino",
                      "feiticeiro", "bruxo", "mago"]
        for c in pt_classes:
            assert c in _STARTING_SLOTS, f"Classe '{c}' não encontrada em _STARTING_SLOTS"

    def test_english_classes_present(self):
        en_classes = ["barbarian", "bard", "cleric", "druid", "fighter",
                      "monk", "paladin", "ranger", "rogue",
                      "sorcerer", "warlock", "wizard"]
        for c in en_classes:
            assert c in _STARTING_SLOTS, f"Class '{c}' not found in _STARTING_SLOTS"

    def test_default_slots_has_6(self):
        assert len(_DEFAULT_SLOTS) == 6

    def test_wizard_has_livro_de_magias(self):
        assert "livro_de_magias" in _STARTING_SLOTS["mago"]
        assert "livro_de_magias" in _STARTING_SLOTS["wizard"]

    def test_barbarian_has_heavy_weapon(self):
        assert "arma_pesada_corpo_a_corpo" in _STARTING_SLOTS["bárbaro"]
        assert "arma_pesada_corpo_a_corpo" in _STARTING_SLOTS["barbarian"]


# ---------------------------------------------------------------------------
# _SLOT_TO_TYPE — mapeamento de slot → item_type
# ---------------------------------------------------------------------------


class TestSlotToType:
    def test_weapon_slots_map_to_weapon(self):
        weapon_slots = [
            "arma_pesada_corpo_a_corpo",
            "arma_marcial",
            "arma_simples",
            "cajado",
        ]
        for slot in weapon_slots:
            assert _SLOT_TO_TYPE[slot] == "weapon", f"Slot '{slot}' deveria mapear para 'weapon'"

    def test_armor_slots_map_to_armor(self):
        armor_slots = ["armadura_leve", "armadura_media", "escudo"]
        for slot in armor_slots:
            assert _SLOT_TO_TYPE[slot] == "armor"

    def test_consumible_slot(self):
        assert _SLOT_TO_TYPE["consumível"] == "consumable"

    def test_misc_slots(self):
        misc_slots = ["utensílio", "misc", "foco_arcano", "grimório"]
        for slot in misc_slots:
            assert _SLOT_TO_TYPE[slot] == "misc"


# ---------------------------------------------------------------------------
# _fallback_inventory — função pura, sem I/O
# ---------------------------------------------------------------------------


class TestFallbackInventory:
    def test_returns_exactly_n_items_for_n_slots(self):
        char_id = uuid4()
        slots = ["arma_simples", "armadura_leve", "consumível"]
        result = _fallback_inventory(slots, char_id)
        assert len(result) == 3

    def test_all_items_have_required_keys(self):
        char_id = uuid4()
        result = _fallback_inventory(_DEFAULT_SLOTS, char_id)
        required_keys = {
            "character_id", "item_name", "item_type", "quantity",
            "weight", "value_gp", "properties", "equipped",
            "stat_bonuses", "special_effects", "rarity", "is_starting_item",
        }
        for item in result:
            assert required_keys.issubset(item.keys()), f"Item faltando chaves: {item}"

    def test_all_items_have_is_starting_item_true(self):
        char_id = uuid4()
        result = _fallback_inventory(_DEFAULT_SLOTS, char_id)
        assert all(item["is_starting_item"] is True for item in result)

    def test_all_items_have_rarity_common(self):
        char_id = uuid4()
        result = _fallback_inventory(_DEFAULT_SLOTS, char_id)
        assert all(item["rarity"] == "common" for item in result)

    def test_all_items_have_empty_stat_bonuses(self):
        char_id = uuid4()
        result = _fallback_inventory(_DEFAULT_SLOTS, char_id)
        assert all(item["stat_bonuses"] == {} for item in result)

    def test_character_id_injected(self):
        char_id = uuid4()
        result = _fallback_inventory(_DEFAULT_SLOTS, char_id)
        assert all(item["character_id"] == char_id for item in result)

    def test_weapon_slots_produce_weapon_type(self):
        char_id = uuid4()
        result = _fallback_inventory(["arma_marcial"], char_id)
        assert result[0]["item_type"] == "weapon"

    def test_armor_slot_produces_armor_type(self):
        char_id = uuid4()
        result = _fallback_inventory(["armadura_leve"], char_id)
        assert result[0]["item_type"] == "armor"

    def test_consumible_slot_produces_consumable_type(self):
        char_id = uuid4()
        result = _fallback_inventory(["consumível"], char_id)
        assert result[0]["item_type"] == "consumable"

    def test_weapon_is_equipped(self):
        char_id = uuid4()
        result = _fallback_inventory(["arma_simples"], char_id)
        assert result[0]["equipped"] is True

    def test_misc_is_not_equipped(self):
        char_id = uuid4()
        result = _fallback_inventory(["misc"], char_id)
        assert result[0]["equipped"] is False

    def test_unknown_slot_uses_generic_fallback(self):
        char_id = uuid4()
        result = _fallback_inventory(["slot_desconhecido_xyz"], char_id)
        assert len(result) == 1
        assert result[0]["item_name"] == "Utensílio"

    def test_empty_slots_returns_empty(self):
        char_id = uuid4()
        result = _fallback_inventory([], char_id)
        assert result == []

    def test_six_slots_ranger(self):
        char_id = uuid4()
        slots = _STARTING_SLOTS["ranger"]
        result = _fallback_inventory(slots, char_id)
        assert len(result) == 6
        # Ranger tem arma de longo alcance
        types = [r["item_type"] for r in result]
        assert "weapon" in types


# ---------------------------------------------------------------------------
# _attach_character_id — função pura
# ---------------------------------------------------------------------------


class TestAttachCharacterId:
    def _make_llm_item(self, **kwargs) -> dict:
        defaults = {
            "item_name": "Espada Longa",
            "item_type": "weapon",
            "slot": "arma_marcial",
            "rarity": "common",
            "quantity": 1,
            "weight": 3.0,
            "value_gp": 15.0,
            "equipped": True,
            "stat_bonuses": {"attack_bonus": 1},
            "special_effects": [],
            "description": "Uma espada forjada com maestria.",
            "properties": {},
        }
        defaults.update(kwargs)
        return defaults

    def test_injects_character_id(self):
        char_id = uuid4()
        items = [self._make_llm_item()]
        result = _attach_character_id(items, char_id, ["arma_marcial"])
        assert result[0]["character_id"] == char_id

    def test_sets_is_starting_item_true(self):
        char_id = uuid4()
        items = [self._make_llm_item()]
        result = _attach_character_id(items, char_id, ["arma_marcial"])
        assert result[0]["is_starting_item"] is True

    def test_preserves_stat_bonuses(self):
        char_id = uuid4()
        items = [self._make_llm_item(stat_bonuses={"armor_class": 1})]
        result = _attach_character_id(items, char_id, ["armadura_leve"])
        assert result[0]["stat_bonuses"] == {"armor_class": 1}

    def test_normalizes_item_type_from_slot(self):
        char_id = uuid4()
        # LLM não informou item_type — deve inferir do slot via _SLOT_TO_TYPE
        item = self._make_llm_item(slot="armadura_media")
        del item["item_type"]
        result = _attach_character_id([item], char_id, ["armadura_media"])
        assert result[0]["item_type"] == "armor"

    def test_empty_special_effects(self):
        char_id = uuid4()
        items = [self._make_llm_item(special_effects=[])]
        result = _attach_character_id(items, char_id, ["arma_simples"])
        assert result[0]["special_effects"] == []

    def test_special_effects_preserved(self):
        char_id = uuid4()
        fx = [{"trigger": "on_hit", "effect": "1d6 fire damage"}]
        items = [self._make_llm_item(special_effects=fx)]
        result = _attach_character_id(items, char_id, ["arma_marcial"])
        assert result[0]["special_effects"] == fx

    def test_missing_item_name_uses_fallback(self):
        char_id = uuid4()
        item = self._make_llm_item()
        del item["item_name"]
        result = _attach_character_id([item], char_id, ["misc"])
        assert result[0]["item_name"] == "Item 1"

    def test_weight_cast_to_float(self):
        char_id = uuid4()
        items = [self._make_llm_item(weight=3)]  # int
        result = _attach_character_id(items, char_id, ["arma_marcial"])
        assert isinstance(result[0]["weight"], float)

    def test_six_items_all_attached(self):
        char_id = uuid4()
        slots = _STARTING_SLOTS["fighter"]
        items = [self._make_llm_item(slot=s) for s in slots]
        result = _attach_character_id(items, char_id, slots)
        assert len(result) == 6
        assert all(r["character_id"] == char_id for r in result)


# ---------------------------------------------------------------------------
# generate_starting_inventory — async, mock LLM
# ---------------------------------------------------------------------------


class TestGenerateStartingInventory:
    @pytest.mark.asyncio
    async def test_returns_6_items_on_success(self):
        char_id = uuid4()
        fake_llm_items = [
            {
                "item_name": f"Item {i}",
                "item_type": "weapon",
                "slot": "arma_simples",
                "rarity": "common",
                "quantity": 1,
                "weight": 1.0,
                "value_gp": 5.0,
                "equipped": True,
                "stat_bonuses": {},
                "special_effects": [],
                "description": "Um item genérico.",
                "properties": {},
            }
            for i in range(6)
        ]

        with patch(
            "infrastructure.inventory_generator._call_llm",
            new=AsyncMock(return_value=fake_llm_items),
        ):
            result = await generate_starting_inventory(
                class_="fighter",
                race="Human",
                background="Soldier",
                level=1,
                character_id=char_id,
            )

        assert len(result) == 6
        assert all(r["is_starting_item"] is True for r in result)
        assert all(r["character_id"] == char_id for r in result)

    @pytest.mark.asyncio
    async def test_falls_back_when_llm_fails(self):
        char_id = uuid4()

        with patch(
            "infrastructure.inventory_generator._call_llm",
            new=AsyncMock(side_effect=RuntimeError("OpenAI indisponível")),
        ):
            result = await generate_starting_inventory(
                class_="wizard",
                race="Elf",
                background="Sage",
                level=1,
                character_id=char_id,
            )

        # Fallback retorna 6 itens
        assert len(result) == 6
        assert all(r["is_starting_item"] is True for r in result)

    @pytest.mark.asyncio
    async def test_uses_correct_slots_for_class(self):
        char_id = uuid4()
        captured_slots: list[list[str]] = []

        async def mock_llm(**kwargs):
            captured_slots.append(kwargs["slots"])
            return [
                {
                    "item_name": "X",
                    "item_type": "weapon",
                    "slot": s,
                    "rarity": "common",
                    "quantity": 1,
                    "weight": 1.0,
                    "value_gp": 1.0,
                    "equipped": False,
                    "stat_bonuses": {},
                    "special_effects": [],
                    "description": None,
                    "properties": {},
                }
                for s in kwargs["slots"]
            ]

        with patch(
            "infrastructure.inventory_generator._call_llm",
            new=AsyncMock(side_effect=mock_llm),
        ):
            await generate_starting_inventory(
                class_="mago",
                race="Elf",
                background="Sage",
                level=1,
                character_id=char_id,
            )

        assert len(captured_slots) == 1
        assert "livro_de_magias" in captured_slots[0]

    @pytest.mark.asyncio
    async def test_unknown_class_uses_default_slots(self):
        char_id = uuid4()

        with patch(
            "infrastructure.inventory_generator._call_llm",
            new=AsyncMock(side_effect=RuntimeError("forced fallback")),
        ):
            result = await generate_starting_inventory(
                class_="classo_inexistente",
                race="Orc",
                background="Outlander",
                level=1,
                character_id=char_id,
            )

        # Fallback com _DEFAULT_SLOTS (6 itens)
        assert len(result) == 6

    @pytest.mark.asyncio
    async def test_character_name_defaults_to_empty(self):
        """generate_starting_inventory deve funcionar sem character_name."""
        char_id = uuid4()
        with patch(
            "infrastructure.inventory_generator._call_llm",
            new=AsyncMock(side_effect=RuntimeError("forced fallback")),
        ):
            result = await generate_starting_inventory(
                class_="barbarian",
                race="Half-Orc",
                background="Outlander",
                level=1,
                character_id=char_id,
                # character_name omitido
            )
        assert len(result) == 6
