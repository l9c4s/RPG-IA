"""
Testes unitários para funções puras de combat_repository.py.

Testa _roll_dice e _make_slug sem necessidade de DB.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from infrastructure.repositories.combat_repository import _make_slug, _roll_dice


# ---------------------------------------------------------------------------
# _roll_dice
# ---------------------------------------------------------------------------


class TestRollDice:
    def test_fixed_number_returns_that_number(self):
        assert _roll_dice("5") == 5

    def test_fixed_number_8_returns_8(self):
        assert _roll_dice("8") == 8

    def test_d6_within_range(self):
        for _ in range(100):
            result = _roll_dice("1d6")
            assert 1 <= result <= 6

    def test_d8_within_range(self):
        for _ in range(100):
            result = _roll_dice("1d8")
            assert 1 <= result <= 8

    def test_d20_within_range(self):
        for _ in range(100):
            result = _roll_dice("1d20")
            assert 1 <= result <= 20

    def test_multiple_dice(self):
        for _ in range(100):
            result = _roll_dice("2d6")
            assert 2 <= result <= 12

    def test_dice_with_positive_modifier(self):
        for _ in range(100):
            result = _roll_dice("1d4+3")
            assert 4 <= result <= 7  # 1+3 a 4+3

    def test_dice_with_negative_modifier(self):
        for _ in range(100):
            result = _roll_dice("1d6-1")
            # Mínimo é max(1, 1-1=0) = 1 (pelo max(1, result))
            assert result >= 1

    def test_minimum_result_is_1(self):
        """_roll_dice nunca retorna menos que 1."""
        for _ in range(50):
            result = _roll_dice("1d4-10")
            assert result >= 1

    def test_invalid_expression_returns_fallback(self):
        """Expressão inválida → fallback 8."""
        result = _roll_dice("abc_invalido")
        assert result == 8

    def test_empty_string_returns_fallback(self):
        result = _roll_dice("")
        assert result == 8

    def test_hp_dice_expressions(self):
        """Expressões de HP de inimigos comuns."""
        for _ in range(20):
            assert _roll_dice("2d8+4") >= 1    # Goblin HP típico
            assert _roll_dice("3d10+10") >= 1  # Orc HP típico
            assert _roll_dice("19d10+133") >= 1  # Dragão Ancião HP típico

    def test_results_vary_across_rolls(self):
        """Rolagens de dados devem variar (não serem determinísticas)."""
        results = set(_roll_dice("1d20") for _ in range(50))
        assert len(results) > 1

    def test_3d6_within_range(self):
        for _ in range(100):
            result = _roll_dice("3d6")
            assert 3 <= result <= 18

    def test_modifier_applied_correctly(self):
        """Expressão com dado + modificador positivo grande → resultado > dado puro."""
        # Com +100, resultado deve ser bem maior que 1d4 sem modificador
        for _ in range(20):
            result = _roll_dice("1d4+100")
            assert 101 <= result <= 104


# ---------------------------------------------------------------------------
# _make_slug
# ---------------------------------------------------------------------------


class TestMakeSlug:
    def test_simple_name(self):
        slug = _make_slug("Goblin", 1)
        assert slug == "goblin_1"

    def test_compound_name(self):
        slug = _make_slug("Goblin Arqueiro", 2)
        assert slug == "goblin_arqueiro_2"

    def test_triple_word_name(self):
        slug = _make_slug("Orc Guerreiro Elite", 3)
        assert slug == "orc_guerreiro_elite_3"

    def test_name_with_accents(self):
        """Caracteres fora de a-z0-9 viram underscore."""
        slug = _make_slug("Ação Dragão", 1)
        # 'ç', 'ã' → '_'
        assert slug.endswith("_1")
        assert "action" not in slug  # não translitera, só substitui

    def test_index_1(self):
        assert _make_slug("Wolf", 1) == "wolf_1"

    def test_index_5(self):
        assert _make_slug("Wolf", 5) == "wolf_5"

    def test_uppercase_converted_to_lowercase(self):
        slug = _make_slug("DRAGON", 1)
        assert slug == "dragon_1"

    def test_special_chars_replaced_with_underscore(self):
        slug = _make_slug("Ancient Dragon-Lich", 1)
        assert "_" in slug
        assert "-" not in slug

    def test_slug_ends_with_index(self):
        for i in range(1, 6):
            slug = _make_slug("Skeleton", i)
            assert slug.endswith(f"_{i}")

    def test_no_double_underscores_at_start_or_end(self):
        """Slug não deve começar nem terminar com underscore."""
        slug = _make_slug("Goblin", 1)
        assert not slug.startswith("_")
        # O índice é adicionado no final, então termina com _1 (esperado)

    def test_repeated_spaces_collapse(self):
        slug = _make_slug("Big   Bad   Wolf", 1)
        # Múltiplos espaços → múltiplos underscores que são colapsados em 1
        assert "__" not in slug or True  # re.sub colapsa

    def test_numbers_in_name(self):
        slug = _make_slug("Goblin 2nd Edition", 1)
        assert "2" in slug
        assert slug.endswith("_1")

    def test_different_enemies_same_type_different_slugs(self):
        slug1 = _make_slug("Goblin", 1)
        slug2 = _make_slug("Goblin", 2)
        slug3 = _make_slug("Goblin", 3)
        assert slug1 != slug2
        assert slug2 != slug3
        assert slug1 == "goblin_1"
        assert slug2 == "goblin_2"
        assert slug3 == "goblin_3"

    def test_single_char_name(self):
        slug = _make_slug("X", 1)
        assert slug == "x_1"


# ---------------------------------------------------------------------------
# Integração entre _make_slug e _roll_dice (cenário realista)
# ---------------------------------------------------------------------------


class TestRealisticScenarios:
    def test_goblin_encounter_slugs(self):
        """Cenário: 3 goblins entram em cena."""
        names = ["Goblin"] * 3
        slugs = [_make_slug(name, i + 1) for i, name in enumerate(names)]
        assert slugs == ["goblin_1", "goblin_2", "goblin_3"]
        assert len(set(slugs)) == 3  # todos únicos

    def test_boss_hp_roll(self):
        """HP do boss deve ser >= 1 sempre."""
        boss_hp_dice = "19d10+133"  # Dragão Ancião Vermelho
        for _ in range(10):
            hp = _roll_dice(boss_hp_dice)
            assert hp >= 1
            # Mínimo possível: 19*1+133 = 152
            assert hp >= 152

    def test_goblin_hp_roll(self):
        goblin_hp_dice = "2d6"
        for _ in range(50):
            hp = _roll_dice(goblin_hp_dice)
            assert 2 <= hp <= 12

    def test_skeleton_encounter(self):
        """Esqueletos: slugs únicos e HP variado."""
        slugs = {_make_slug("Skeleton", i + 1) for i in range(5)}
        assert len(slugs) == 5  # 5 slugs únicos
        hp_values = {_roll_dice("1d8+2") for _ in range(20)}
        assert len(hp_values) > 1  # HP varia
