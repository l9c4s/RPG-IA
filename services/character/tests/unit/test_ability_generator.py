"""
Testes unitários para o gerador de habilidades iniciais (P3).
"""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from unittest.mock import patch
from uuid import uuid4


class TestAbilityGenerator:
    @pytest.mark.asyncio
    async def test_fallback_abilities_returned_on_llm_failure(self):
        from infrastructure.ability_generator import generate_starting_abilities

        with patch("infrastructure.ability_generator._call_llm", side_effect=Exception("API down")):
            abilities = await generate_starting_abilities(
                class_="guerreiro",
                race="Humano",
                level=1,
                character_id=uuid4(),
                character_name="Teste",
            )
        assert len(abilities) >= 1
        assert all("ability_name" in a for a in abilities)
        assert all("character_id" in a for a in abilities)

    @pytest.mark.asyncio
    async def test_fallback_for_unknown_class(self):
        from infrastructure.ability_generator import generate_starting_abilities

        with patch("infrastructure.ability_generator._call_llm", side_effect=Exception("API down")):
            abilities = await generate_starting_abilities(
                class_="inventor",
                race="Gnomo",
                level=1,
                character_id=uuid4(),
            )
        assert len(abilities) >= 1

    @pytest.mark.asyncio
    async def test_llm_result_has_character_id(self):
        from infrastructure.ability_generator import generate_starting_abilities

        mock_abilities = [
            {"ability_name": "Ataque Extra", "ability_type": "action",
             "uses_max": None, "recharge": None, "description": "Ataca duas vezes."},
            {"ability_name": "Estilo de Combate", "ability_type": "feature",
             "uses_max": None, "recharge": None, "description": "Especialização."},
        ]
        with patch("infrastructure.ability_generator._call_llm", return_value=mock_abilities):
            char_id = uuid4()
            abilities = await generate_starting_abilities(
                class_="guerreiro", race="Humano", level=1, character_id=char_id,
            )

        assert all(a["character_id"] == char_id for a in abilities)

    def test_invalid_ability_type_normalized(self):
        from infrastructure.ability_generator import _attach_character_id

        raw = [{"ability_name": "Habilidade", "ability_type": "INVALID_TYPE",
                "description": "Desc", "uses_max": None, "recharge": None}]
        result = _attach_character_id(raw, uuid4())
        assert result[0]["ability_type"] == "feature"

    def test_uses_current_matches_uses_max(self):
        from infrastructure.ability_generator import _attach_character_id

        raw = [{"ability_name": "Fúria", "ability_type": "action",
                "uses_max": 2, "recharge": "long_rest", "description": "Entra em fúria."}]
        result = _attach_character_id(raw, uuid4())
        assert result[0]["uses_current"] == result[0]["uses_max"] == 2

    def test_invalid_recharge_normalized_to_none(self):
        from infrastructure.ability_generator import _attach_character_id

        raw = [{"ability_name": "Habilidade", "ability_type": "feature",
                "uses_max": 1, "recharge": "INVALID", "description": "Desc."}]
        result = _attach_character_id(raw, uuid4())
        assert result[0]["recharge"] is None

    def test_fallback_uses_current_equals_uses_max(self):
        from infrastructure.ability_generator import _fallback_abilities

        abilities = _fallback_abilities("guerreiro", uuid4())
        for ab in abilities:
            if ab["uses_max"] is not None:
                assert ab["uses_current"] == ab["uses_max"]
