"""
Testes unitários para as novas tags de combate em infrastructure/ai/state_parser.py.

Tags testadas:
  [INIMIGOS: [...JSON...]]
  [DANO_INIMIGO: slug:dano]
  [ATAQUE_INIMIGO: alvo:dano:grupo]
  [ITEM_GANHO: personagem:item:tipo]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import pytest

from infrastructure.ai.state_parser import parse_gm_response


# ---------------------------------------------------------------------------
# Tag [INIMIGOS:]
# ---------------------------------------------------------------------------


class TestInimigosTag:
    def test_extracts_single_enemy(self):
        enemies_json = json.dumps([
            {"nome": "Goblin", "tipo": "goblin", "hp": 7, "ca": 13, "atk": 4, "dano": "1d6+2"}
        ])
        text = f"De repente, inimigos aparecem! [INIMIGOS: {enemies_json}]"
        result = parse_gm_response(text)
        assert len(result["new_enemies"]) == 1
        assert result["new_enemies"][0]["nome"] == "Goblin"

    def test_extracts_multiple_enemies(self):
        enemies_json = json.dumps([
            {"nome": "Goblin", "tipo": "goblin", "hp": 7, "ca": 13, "atk": 4, "dano": "1d6"},
            {"nome": "Hobgoblin", "tipo": "hobgoblin", "hp": 11, "ca": 14, "atk": 5, "dano": "1d8+2"},
            {"nome": "Goblin Arqueiro", "tipo": "goblin", "hp": 5, "ca": 12, "atk": 3, "dano": "1d6"},
        ])
        text = f"[INIMIGOS: {enemies_json}]"
        result = parse_gm_response(text)
        assert len(result["new_enemies"]) == 3

    def test_invalid_json_is_ignored(self):
        text = "[INIMIGOS: {isso nao e json valido}]"
        result = parse_gm_response(text)
        assert result["new_enemies"] == []

    def test_non_list_json_is_ignored(self):
        text = '[INIMIGOS: {"nome": "Goblin"}]'
        result = parse_gm_response(text)
        assert result["new_enemies"] == []

    def test_tag_stripped_from_clean_text(self):
        enemies_json = json.dumps([{"nome": "Goblin", "hp": 7}])
        text = f"Emboscada! [INIMIGOS: {enemies_json}] Cuidado!"
        result = parse_gm_response(text)
        assert "[INIMIGOS:" not in result["clean_text"]
        assert "Emboscada" in result["clean_text"]
        assert "Cuidado" in result["clean_text"]

    def test_multiline_json_supported(self):
        enemies_json = json.dumps([
            {"nome": "Dragão", "tipo": "dragon", "hp": 200, "ca": 19, "atk": 10, "dano": "2d10+7"},
        ], indent=2)
        text = f"[INIMIGOS: {enemies_json}]"
        result = parse_gm_response(text)
        assert len(result["new_enemies"]) == 1
        assert result["new_enemies"][0]["tipo"] == "dragon"

    def test_case_insensitive_tag(self):
        enemies_json = json.dumps([{"nome": "Lobo", "hp": 11}])
        text = f"[inimigos: {enemies_json}]"
        result = parse_gm_response(text)
        assert len(result["new_enemies"]) == 1

    def test_empty_enemies_array(self):
        text = "[INIMIGOS: []]"
        result = parse_gm_response(text)
        assert result["new_enemies"] == []

    def test_no_tag_returns_empty(self):
        text = "Você entra na taverna. O estalajadeiro acena."
        result = parse_gm_response(text)
        assert result["new_enemies"] == []

    def test_enemy_fields_preserved(self):
        enemies_json = json.dumps([{
            "nome": "Orc Guerreiro",
            "tipo": "orc",
            "hp": 15,
            "ca": 14,
            "atk": 5,
            "dano": "1d8+3",
        }])
        text = f"[INIMIGOS: {enemies_json}]"
        result = parse_gm_response(text)
        enemy = result["new_enemies"][0]
        assert enemy["hp"] == 15
        assert enemy["ca"] == 14
        assert enemy["dano"] == "1d8+3"


# ---------------------------------------------------------------------------
# Tag [DANO_INIMIGO:]
# ---------------------------------------------------------------------------


class TestDanoInimigo:
    def test_extracts_single_damage(self):
        text = "Você acerta o goblin! [DANO_INIMIGO: goblin_1:8] O monstro geme."
        result = parse_gm_response(text)
        assert len(result["enemy_damage"]) == 1
        slug, damage = result["enemy_damage"][0]
        assert slug == "goblin_1"
        assert damage == 8

    def test_extracts_multiple_damage_tags(self):
        text = (
            "[DANO_INIMIGO: goblin_1:5] "
            "[DANO_INIMIGO: hobgoblin_1:12] "
            "A batalha avança."
        )
        result = parse_gm_response(text)
        assert len(result["enemy_damage"]) == 2
        slugs = [d[0] for d in result["enemy_damage"]]
        assert "goblin_1" in slugs
        assert "hobgoblin_1" in slugs

    def test_damage_is_int(self):
        text = "[DANO_INIMIGO: orc_1:15]"
        result = parse_gm_response(text)
        _, damage = result["enemy_damage"][0]
        assert isinstance(damage, int)
        assert damage == 15

    def test_slug_with_spaces_stripped(self):
        text = "[DANO_INIMIGO:  goblin_2 :10]"
        result = parse_gm_response(text)
        slug, _ = result["enemy_damage"][0]
        assert slug == "goblin_2"

    def test_tag_stripped_from_clean_text(self):
        text = "Ataque! [DANO_INIMIGO: goblin_1:6] Bem feito!"
        result = parse_gm_response(text)
        assert "[DANO_INIMIGO:" not in result["clean_text"]
        assert "Ataque" in result["clean_text"]
        assert "Bem feito" in result["clean_text"]

    def test_zero_damage_captured(self):
        text = "[DANO_INIMIGO: goblin_1:0]"
        result = parse_gm_response(text)
        _, damage = result["enemy_damage"][0]
        assert damage == 0

    def test_large_damage_captured(self):
        text = "[DANO_INIMIGO: dragon_1:99]"
        result = parse_gm_response(text)
        _, damage = result["enemy_damage"][0]
        assert damage == 99

    def test_no_tag_returns_empty(self):
        text = "Você erra o ataque."
        result = parse_gm_response(text)
        assert result["enemy_damage"] == []


# ---------------------------------------------------------------------------
# Tag [ATAQUE_INIMIGO:]
# ---------------------------------------------------------------------------


class TestAtaqueInimigo:
    def test_extracts_individual_attack(self):
        text = "[ATAQUE_INIMIGO: Aragorn:8:false] O goblin acerta!"
        result = parse_gm_response(text)
        assert len(result["player_attacks"]) == 1
        attack = result["player_attacks"][0]
        assert attack["target"] == "Aragorn"
        assert attack["damage"] == 8
        assert attack["is_group"] is False

    def test_extracts_group_attack_with_true(self):
        text = "[ATAQUE_INIMIGO: todos:12:true] O dragão sopra fogo!"
        result = parse_gm_response(text)
        attack = result["player_attacks"][0]
        assert attack["is_group"] is True
        assert attack["damage"] == 12

    def test_extracts_group_attack_with_grupo(self):
        text = "[ATAQUE_INIMIGO: todos:10:grupo]"
        result = parse_gm_response(text)
        assert result["player_attacks"][0]["is_group"] is True

    def test_extracts_individual_attack_with_individual(self):
        text = "[ATAQUE_INIMIGO: Gandalf:5:individual]"
        result = parse_gm_response(text)
        assert result["player_attacks"][0]["is_group"] is False

    def test_extracts_multiple_attacks(self):
        text = (
            "[ATAQUE_INIMIGO: Legolas:7:false]"
            "[ATAQUE_INIMIGO: Gimli:9:false]"
            "A batalha continua."
        )
        result = parse_gm_response(text)
        assert len(result["player_attacks"]) == 2

    def test_tag_stripped_from_clean_text(self):
        text = "O goblin ataca! [ATAQUE_INIMIGO: Herói:6:false] Você leva dano."
        result = parse_gm_response(text)
        assert "[ATAQUE_INIMIGO:" not in result["clean_text"]
        assert "O goblin ataca" in result["clean_text"]
        assert "Você leva dano" in result["clean_text"]

    def test_damage_is_int(self):
        text = "[ATAQUE_INIMIGO: Player:15:false]"
        result = parse_gm_response(text)
        assert isinstance(result["player_attacks"][0]["damage"], int)

    def test_no_tag_returns_empty(self):
        text = "Nenhum inimigo ataca neste turno."
        result = parse_gm_response(text)
        assert result["player_attacks"] == []


# ---------------------------------------------------------------------------
# Tag [ITEM_GANHO:]
# ---------------------------------------------------------------------------


class TestItemGanho:
    def test_extracts_weapon_item(self):
        text = "[ITEM_GANHO: Aragorn:Espada Longa:weapon] Você encontra uma espada!"
        result = parse_gm_response(text)
        assert len(result["items_gained"]) == 1
        item = result["items_gained"][0]
        assert item["char_name"] == "Aragorn"
        assert item["item_name"] == "Espada Longa"
        assert item["item_type"] == "weapon"

    def test_extracts_armor_item(self):
        text = "[ITEM_GANHO: Legolas:Cota de Malha:armor]"
        result = parse_gm_response(text)
        assert result["items_gained"][0]["item_type"] == "armor"

    def test_extracts_consumable_item(self):
        text = "[ITEM_GANHO: Gimli:Poção de Cura:consumable]"
        result = parse_gm_response(text)
        assert result["items_gained"][0]["item_type"] == "consumable"

    def test_extracts_misc_item(self):
        text = "[ITEM_GANHO: Herói:Tocha:misc]"
        result = parse_gm_response(text)
        assert result["items_gained"][0]["item_type"] == "misc"

    def test_unknown_type_normalized_to_misc(self):
        text = "[ITEM_GANHO: Herói:Orbe Misterioso:artifact]"
        result = parse_gm_response(text)
        assert result["items_gained"][0]["item_type"] == "misc"

    def test_extracts_multiple_items(self):
        text = (
            "[ITEM_GANHO: Herói:Espada:weapon]"
            "[ITEM_GANHO: Bardo:Flauta Mágica:misc]"
        )
        result = parse_gm_response(text)
        assert len(result["items_gained"]) == 2

    def test_tag_stripped_from_clean_text(self):
        text = "Você saqueia o baú! [ITEM_GANHO: Herói:Anel de Poder:misc] Impressionante!"
        result = parse_gm_response(text)
        assert "[ITEM_GANHO:" not in result["clean_text"]
        assert "Você saqueia" in result["clean_text"]
        assert "Impressionante" in result["clean_text"]

    def test_item_type_lowercased(self):
        text = "[ITEM_GANHO: Herói:Espada:WEAPON]"
        result = parse_gm_response(text)
        assert result["items_gained"][0]["item_type"] == "weapon"

    def test_no_tag_returns_empty(self):
        text = "Nenhum item encontrado nesta sala."
        result = parse_gm_response(text)
        assert result["items_gained"] == []

    def test_char_name_stripped(self):
        text = "[ITEM_GANHO:  Aragorn :Espada:weapon]"
        result = parse_gm_response(text)
        assert result["items_gained"][0]["char_name"] == "Aragorn"

    def test_item_name_stripped(self):
        text = "[ITEM_GANHO: Herói: Espada Longa :weapon]"
        result = parse_gm_response(text)
        assert result["items_gained"][0]["item_name"] == "Espada Longa"


# ---------------------------------------------------------------------------
# Combinações de múltiplas tags
# ---------------------------------------------------------------------------


class TestCombinedTags:
    def test_all_combat_tags_in_one_response(self):
        enemies_json = json.dumps([
            {"nome": "Goblin", "tipo": "goblin", "hp": 7, "ca": 13, "atk": 4, "dano": "1d6"}
        ])
        text = (
            f"Os goblins atacam! [INIMIGOS: {enemies_json}] "
            "[DANO_INIMIGO: goblin_1:5] "
            "[ATAQUE_INIMIGO: Herói:3:false] "
            "[ITEM_GANHO: Herói:Adaga:weapon] "
            "A batalha continua."
        )
        result = parse_gm_response(text)
        assert len(result["new_enemies"]) == 1
        assert len(result["enemy_damage"]) == 1
        assert len(result["player_attacks"]) == 1
        assert len(result["items_gained"]) == 1
        assert "[INIMIGOS:" not in result["clean_text"]
        assert "[DANO_INIMIGO:" not in result["clean_text"]
        assert "[ATAQUE_INIMIGO:" not in result["clean_text"]
        assert "[ITEM_GANHO:" not in result["clean_text"]
        assert "Os goblins atacam" in result["clean_text"]
        assert "A batalha continua" in result["clean_text"]

    def test_new_tags_coexist_with_existing_tags(self):
        """Novas tags não devem interferir com [ROLAGEM:], [ESTADO:], [IMAGEM:]."""
        enemies_json = json.dumps([{"nome": "Orc", "hp": 15}])
        text = (
            f"[ROLAGEM:1d20+5] Você ataca! "
            f"[INIMIGOS: {enemies_json}] "
            "[DANO_INIMIGO: orc_1:8] "
            "[ESTADO:hp_current=10] "
            "[IMAGEM:Um orc ferido]"
        )
        result = parse_gm_response(text)
        assert len(result["roll_results"]) == 1
        assert len(result["state_updates"]) == 1
        assert result["image_description"] == "Um orc ferido"
        assert len(result["new_enemies"]) == 1
        assert len(result["enemy_damage"]) == 1
        # Texto limpo não deve ter nenhuma tag
        for tag in ["[ROLAGEM:", "[ESTADO:", "[IMAGEM:", "[INIMIGOS:", "[DANO_INIMIGO:"]:
            assert tag not in result["clean_text"]

    def test_response_structure_always_contains_combat_keys(self):
        """parse_gm_response sempre retorna as 4 chaves de combate, mesmo sem tags."""
        result = parse_gm_response("Você entra na taverna.")
        assert "new_enemies" in result
        assert "enemy_damage" in result
        assert "player_attacks" in result
        assert "items_gained" in result

    def test_empty_text_returns_empty_combat_data(self):
        result = parse_gm_response("")
        assert result["new_enemies"] == []
        assert result["enemy_damage"] == []
        assert result["player_attacks"] == []
        assert result["items_gained"] == []
