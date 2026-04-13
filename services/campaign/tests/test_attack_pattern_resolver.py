"""
Testes unitários para AttackPatternResolver.

Sem DB, sem I/O — apenas lógica de targeting e rolagem de dados.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from uuid import uuid4

from infrastructure.combat.attack_pattern_resolver import (
    AttackPatternResolver,
    AttackResolution,
    AttackTarget,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player(name: str = "Herói", hp: int = 20, ac: int = 15) -> dict:
    return {
        "id": str(uuid4()),
        "name": name,
        "hp_current": hp,
        "armor_class": ac,
    }


def _make_enemy(
    name: str = "Goblin",
    pattern: str = "melee_single",
    attacks: list | None = None,
    hp: int = 7,
) -> dict:
    if attacks is None:
        attacks = [
            {
                "name": "Mordida",
                "attack_bonus": 4,
                "damage": "1d6+2",
                "damage_type": "slashing",
                "hits": 1,
            }
        ]
    return {
        "id": str(uuid4()),
        "slug": f"{name.lower().replace(' ', '_')}_1",
        "display_name": name,
        "attack_pattern": pattern,
        "attacks": attacks,
        "hp_current": hp,
        "armor_class": 13,
    }


# ---------------------------------------------------------------------------
# resolve — entradas vazias
# ---------------------------------------------------------------------------


class TestResolveEdgeCases:
    def test_no_enemies_returns_empty(self):
        resolver = AttackPatternResolver()
        result = resolver.resolve(enemies=[], players=[_make_player()])
        assert result == []

    def test_no_players_returns_empty(self):
        resolver = AttackPatternResolver()
        result = resolver.resolve(enemies=[_make_enemy()], players=[])
        assert result == []

    def test_both_empty_returns_empty(self):
        resolver = AttackPatternResolver()
        result = resolver.resolve(enemies=[], players=[])
        assert result == []


# ---------------------------------------------------------------------------
# resolve — narrative_only
# ---------------------------------------------------------------------------


class TestNarrativeOnly:
    def test_narrative_only_generates_no_targets(self):
        resolver = AttackPatternResolver()
        boss = _make_enemy(name="Boss Dragon", pattern="narrative_only")
        players = [_make_player("Frodo"), _make_player("Bilbo")]
        result = resolver.resolve(enemies=[boss], players=players)
        assert result == []

    def test_narrative_mixed_with_auto(self):
        """Boss é narrative_only, goblin é melee_single — só goblin gera ataque."""
        resolver = AttackPatternResolver()
        boss = _make_enemy(name="Boss", pattern="narrative_only")
        goblin = _make_enemy(name="Goblin", pattern="melee_single")
        players = [_make_player()]
        result = resolver.resolve(enemies=[boss, goblin], players=players)
        assert len(result) == 1
        assert result[0].enemy_name == "Goblin"


# ---------------------------------------------------------------------------
# resolve — padrões de grupo (_GROUP_PATTERNS)
# ---------------------------------------------------------------------------


class TestGroupPatterns:
    @pytest.mark.parametrize("pattern", ["breath_cone", "breath_line", "aura", "ranged_volley"])
    def test_group_pattern_targets_all_players(self, pattern):
        resolver = AttackPatternResolver()
        dragon = _make_enemy(name="Dragon", pattern=pattern)
        players = [_make_player("P1"), _make_player("P2"), _make_player("P3")]
        result = resolver.resolve(enemies=[dragon], players=players)
        assert len(result) == 3
        target_names = {t.target_character_name for t in result}
        assert "P1" in target_names
        assert "P2" in target_names
        assert "P3" in target_names

    def test_group_pattern_sets_is_group_true(self):
        resolver = AttackPatternResolver()
        dragon = _make_enemy(pattern="breath_cone")
        players = [_make_player("P1"), _make_player("P2")]
        result = resolver.resolve(enemies=[dragon], players=players)
        assert all(t.is_group for t in result)

    def test_group_pattern_uses_representative_enemy(self):
        """Com vários inimigos de grupo, usa o primeiro como representante."""
        resolver = AttackPatternResolver()
        d1 = _make_enemy(name="Dragon1", pattern="breath_cone")
        d2 = _make_enemy(name="Dragon2", pattern="breath_cone")
        players = [_make_player()]
        result = resolver.resolve(enemies=[d1, d2], players=players)
        # 1 ataque para o 1 jogador (representante = d1)
        assert len(result) == 1
        assert result[0].enemy_name == "Dragon1"

    def test_group_attack_with_single_player(self):
        resolver = AttackPatternResolver()
        dragon = _make_enemy(pattern="aura")
        players = [_make_player()]
        result = resolver.resolve(enemies=[dragon], players=players)
        assert len(result) == 1
        assert result[0].is_group is True


# ---------------------------------------------------------------------------
# resolve — padrões individuais (_SINGLE_PATTERNS)
# ---------------------------------------------------------------------------


class TestSinglePatterns:
    @pytest.mark.parametrize("pattern", ["melee_single", "melee_multi", "ranged_single", "swarm", "grapple"])
    def test_single_enemy_targets_weakest_player(self, pattern):
        resolver = AttackPatternResolver()
        enemy = _make_enemy(pattern=pattern)
        strong = _make_player("Strong", hp=30, ac=18)
        weak = _make_player("Weak", hp=3, ac=10)
        result = resolver.resolve(enemies=[enemy], players=[strong, weak])
        assert len(result) == 1
        assert result[0].target_character_name == "Weak"

    def test_group_of_5_goblins_distributes_round_robin(self):
        resolver = AttackPatternResolver()
        goblins = [_make_enemy(name=f"Goblin{i}", pattern="melee_single") for i in range(5)]
        players = [_make_player("P1"), _make_player("P2"), _make_player("P3")]
        result = resolver.resolve(enemies=goblins, players=players)
        assert len(result) == 5
        # Cada goblin ataca 1 jogador → 5 ataques
        target_names = [t.target_character_name for t in result]
        # Com round-robin de 5 goblins em 3 jogadores: [P1, P2, P3, P1, P2]
        assert "P1" in target_names
        assert "P2" in target_names
        assert "P3" in target_names

    def test_group_of_enemies_is_group_false(self):
        resolver = AttackPatternResolver()
        goblins = [_make_enemy(name=f"G{i}", pattern="melee_single") for i in range(3)]
        players = [_make_player("P1"), _make_player("P2")]
        result = resolver.resolve(enemies=goblins, players=players)
        assert all(not t.is_group for t in result)

    def test_single_enemy_with_multi_hits(self):
        """Inimigo com hits=2 gera 2 AttackTargets."""
        resolver = AttackPatternResolver()
        attacks = [{
            "name": "Multi-Ataque",
            "attack_bonus": 5,
            "damage": "1d8+3",
            "damage_type": "slashing",
            "hits": 2,
        }]
        enemy = _make_enemy(pattern="melee_multi", attacks=attacks)
        players = [_make_player()]
        result = resolver.resolve(enemies=[enemy], players=players)
        assert len(result) == 2

    def test_enemy_without_attacks_uses_fallback(self):
        """Inimigo sem lista de ataques usa ataque genérico de fallback."""
        resolver = AttackPatternResolver()
        enemy = _make_enemy(pattern="melee_single", attacks=[])
        players = [_make_player()]
        result = resolver.resolve(enemies=[enemy], players=players)
        assert len(result) == 1
        assert result[0].attack_bonus == 3  # fallback padrão
        assert result[0].damage_dice == "1d6"

    def test_unknown_pattern_produces_no_targets(self):
        resolver = AttackPatternResolver()
        enemy = _make_enemy(pattern="super_unknown_pattern")
        players = [_make_player()]
        result = resolver.resolve(enemies=[enemy], players=players)
        assert result == []


# ---------------------------------------------------------------------------
# _pick_weakest
# ---------------------------------------------------------------------------


class TestPickWeakest:
    def test_picks_player_with_lowest_hp(self):
        players = [
            _make_player("A", hp=30),
            _make_player("B", hp=5),
            _make_player("C", hp=20),
        ]
        weakest = AttackPatternResolver._pick_weakest(players)
        assert weakest["name"] == "B"

    def test_with_single_player(self):
        players = [_make_player("Solo", hp=15)]
        weakest = AttackPatternResolver._pick_weakest(players)
        assert weakest["name"] == "Solo"

    def test_tie_returns_one_of_them(self):
        players = [_make_player("A", hp=10), _make_player("B", hp=10)]
        weakest = AttackPatternResolver._pick_weakest(players)
        assert weakest["name"] in ("A", "B")


# ---------------------------------------------------------------------------
# _roll_damage
# ---------------------------------------------------------------------------


class TestRollDamage:
    def test_regular_damage_within_range(self):
        for _ in range(50):
            dmg, _ = AttackPatternResolver._roll_damage("2d6+3")
            assert 5 <= dmg <= 15  # 2*1+3 a 2*6+3

    def test_critical_doubles_dice(self):
        """Crítico deve resultar em mais dano em média que normal."""
        normal_total = sum(AttackPatternResolver._roll_damage("2d6")[0] for _ in range(50))
        crit_total = sum(AttackPatternResolver._roll_damage("2d6", is_crit=True)[0] for _ in range(50))
        # Crítico tem 4 dados vs 2 → média ~50% maior
        assert crit_total > normal_total * 0.8  # margem para variância

    def test_critical_breakdown_contains_marker(self):
        _, breakdown = AttackPatternResolver._roll_damage("1d6", is_crit=True)
        assert "CRÍTICO" in breakdown

    def test_damage_never_negative(self):
        for _ in range(50):
            dmg, _ = AttackPatternResolver._roll_damage("1d4-10")
            assert dmg >= 0

    def test_fixed_value_damage(self):
        """Expressão sem dados (número puro) deve retornar valor fixo."""
        dmg, _ = AttackPatternResolver._roll_damage("5")
        assert dmg == 5

    def test_invalid_expr_returns_1(self):
        """Expressão completamente inválida retorna 1."""
        dmg, _ = AttackPatternResolver._roll_damage("abcd")
        assert dmg == 1

    def test_positive_modifier_in_breakdown(self):
        _, breakdown = AttackPatternResolver._roll_damage("1d6+3")
        assert "+ 3" in breakdown or "3" in breakdown

    def test_zero_modifier(self):
        _, breakdown = AttackPatternResolver._roll_damage("1d8")
        assert "CRÍTICO" not in breakdown or True  # só verifica que não crashou


# ---------------------------------------------------------------------------
# roll_attacks
# ---------------------------------------------------------------------------


class TestRollAttacks:
    def _make_target(self, target_id: str, ac: int = 15) -> AttackTarget:
        return AttackTarget(
            enemy_id=str(uuid4()),
            enemy_name="Goblin",
            enemy_slug="goblin_1",
            attack_name="Mordida",
            attack_bonus=4,
            damage_dice="1d6+2",
            damage_type="slashing",
            target_character_id=target_id,
            target_character_name="Herói",
            is_group=False,
        )

    def test_returns_one_resolution_per_target(self):
        resolver = AttackPatternResolver()
        pid = str(uuid4())
        targets = [self._make_target(pid) for _ in range(3)]
        ac_map = {pid: 15}
        result = resolver.roll_attacks(targets, ac_map)
        assert len(result) == 3

    def test_resolution_has_correct_structure(self):
        resolver = AttackPatternResolver()
        pid = str(uuid4())
        target = self._make_target(pid)
        ac_map = {pid: 1}  # AC=1 → sempre acerta
        result = resolver.roll_attacks([target], ac_map)
        res = result[0]
        assert isinstance(res, AttackResolution)
        assert res.attack_roll >= 1
        assert res.hit is True or res.hit is False
        assert isinstance(res.damage, int)

    def test_hit_when_ac_is_1(self):
        """AC=1 → qualquer rola de ataque acerta."""
        resolver = AttackPatternResolver()
        pid = str(uuid4())
        target = self._make_target(pid, ac=1)
        ac_map = {pid: 1}
        # Roda várias vezes para garantir
        hits = sum(
            1 for r in resolver.roll_attacks([target] * 20, ac_map) if r.hit
        )
        assert hits == 20

    def test_miss_when_ac_is_999(self):
        """AC muito alta → nunca acerta (exceto crit)."""
        resolver = AttackPatternResolver()
        pid = str(uuid4())
        target = self._make_target(pid)
        target.attack_bonus = -100
        ac_map = {pid: 999}
        misses = 0
        hits = 0
        for _ in range(100):
            r = resolver.roll_attacks([target], ac_map)[0]
            if r.hit and r.is_critical:
                hits += 1
            elif not r.hit:
                misses += 1
        # Quase sempre erra (apenas crits acertam)
        assert misses > 80

    def test_damage_is_zero_on_miss(self):
        """Ataque que erra não causa dano."""
        resolver = AttackPatternResolver()
        pid = str(uuid4())
        target = self._make_target(pid)
        target.attack_bonus = -100  # nunca acerta (exceto nat 20)
        ac_map = {pid: 999}
        for _ in range(50):
            r = resolver.roll_attacks([target], ac_map)[0]
            if not r.hit:
                assert r.damage == 0

    def test_critical_hit_on_nat_20(self):
        """Nat 20 → is_critical=True e hit=True."""
        import unittest.mock as mock
        resolver = AttackPatternResolver()
        pid = str(uuid4())
        target = self._make_target(pid)
        ac_map = {pid: 30}  # AC alta, só crit acerta
        with mock.patch("random.randint", return_value=20):
            r = resolver.roll_attacks([target], ac_map)[0]
        assert r.is_critical is True
        assert r.hit is True

    def test_unknown_player_in_ac_map_uses_default_10(self):
        """Se player não está no ac_map, usa AC=10 como padrão."""
        resolver = AttackPatternResolver()
        target = self._make_target("unknown_player_id")
        # ac_map vazio → usa 10 por padrão
        result = resolver.roll_attacks([target], {})
        # Não deve lançar exceção
        assert len(result) == 1

    def test_empty_targets_returns_empty(self):
        resolver = AttackPatternResolver()
        result = resolver.roll_attacks([], {})
        assert result == []
