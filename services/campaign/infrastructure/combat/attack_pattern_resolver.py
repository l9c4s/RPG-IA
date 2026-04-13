"""
AttackPatternResolver — Decide automaticamente como inimigos atacam.

Lógica híbrida:
  1. narrative_only → GM controla via tag [ATAQUE_INIMIGO:]. Backend não age.
  2. Grupo de inimigos com melee_single/ranged_single → cada um ataca um alvo.
  3. breath_cone / breath_line / aura / ranged_volley → todos os jogadores.
  4. Demais patterns → 1 alvo (o mais fraco).

Resultado: lista de AttackTarget que o use_case executa e transmite via WS.
"""

from __future__ import annotations

import random
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AttackTarget:
    """Um ataque de um inimigo específico contra um alvo específico."""
    enemy_id: str                # UUID do inimigo
    enemy_name: str              # display_name do inimigo
    enemy_slug: str              # slug para referência
    attack_name: str             # nome do ataque ("Mordida", "Garra", etc.)
    attack_bonus: int            # bônus de ataque
    damage_dice: str             # expressão de dano ("1d6+2")
    damage_type: str             # piercing | slashing | fire | etc.
    target_character_id: str     # UUID do personagem alvo
    target_character_name: str   # nome do personagem alvo
    is_group: bool = False       # True = dano de área (todos são alvos)


@dataclass
class AttackResolution:
    """Resultado calculado de um ataque."""
    target: AttackTarget
    attack_roll: int             # d20 + attack_bonus
    hit: bool                   # attack_roll >= target_ac
    damage: int                 # dano causado (0 se errou)
    damage_breakdown: str       # ex: "[4, 2] + 3 = 9"
    is_critical: bool = False   # d20 natural 20


# ─── Padrões e seus comportamentos ───────────────────────────────────────────

_GROUP_PATTERNS = {
    "breath_cone",
    "breath_line",
    "aura",
    "ranged_volley",
}

_SINGLE_PATTERNS = {
    "melee_single",
    "melee_multi",
    "ranged_single",
    "swarm",
    "grapple",
}


class AttackPatternResolver:
    """
    Resolve quais personagens são atacados por quais inimigos,
    baseado no attack_pattern de cada inimigo.
    """

    def resolve(
        self,
        enemies: list[dict],        # CombatEnemyORM convertidos para dict
        players: list[dict],        # personagens ativos com hp_current, armor_class
    ) -> list[AttackTarget]:
        """
        Gera a lista completa de ataques para o turno dos inimigos.

        enemies: lista de inimigos vivos (dicts com id, slug, display_name,
                 attack_pattern, attacks, hp_current, armor_class)
        players: lista de personagens humanos/IA (dicts com id, name,
                 hp_current, armor_class)
        """
        if not enemies or not players:
            return []

        targets: list[AttackTarget] = []

        # Agrupa inimigos por attack_pattern para tratar grupos
        by_pattern: dict[str, list[dict]] = {}
        for e in enemies:
            p = e.get("attack_pattern", "melee_single")
            by_pattern.setdefault(p, []).append(e)

        for pattern, group in by_pattern.items():
            if pattern == "narrative_only":
                # GM decide — não geramos ataques automáticos
                logger.debug(
                    "%d inimigo(s) com narrative_only — GM controla via tag",
                    len(group),
                )
                continue

            if pattern in _GROUP_PATTERNS:
                # Todos os jogadores são alvos — 1 inimigo representa o grupo
                representative = group[0]
                attack = self._pick_attack(representative)
                for player in players:
                    targets.append(
                        AttackTarget(
                            enemy_id=str(representative["id"]),
                            enemy_name=representative["display_name"],
                            enemy_slug=representative["slug"],
                            attack_name=attack["name"],
                            attack_bonus=attack["attack_bonus"],
                            damage_dice=attack["damage"],
                            damage_type=attack.get("damage_type", "untyped"),
                            target_character_id=str(player["id"]),
                            target_character_name=player["name"],
                            is_group=True,
                        )
                    )

            elif pattern in _SINGLE_PATTERNS:
                is_group_of_enemies = len(group) > 1

                if is_group_of_enemies:
                    # Vários inimigos do mesmo tipo: distribui alvos
                    # Ex: 5 goblins → cada um ataca um jogador diferente (round-robin)
                    for i, enemy in enumerate(group):
                        player = players[i % len(players)]
                        attack = self._pick_attack(enemy)
                        hits = attack.get("hits", 1)  # multi-ataque
                        for _ in range(hits):
                            targets.append(
                                AttackTarget(
                                    enemy_id=str(enemy["id"]),
                                    enemy_name=enemy["display_name"],
                                    enemy_slug=enemy["slug"],
                                    attack_name=attack["name"],
                                    attack_bonus=attack["attack_bonus"],
                                    damage_dice=attack["damage"],
                                    damage_type=attack.get("damage_type", "untyped"),
                                    target_character_id=str(player["id"]),
                                    target_character_name=player["name"],
                                    is_group=False,
                                )
                            )
                else:
                    # 1 inimigo → ataca o jogador com menos HP (mais fraco)
                    enemy = group[0]
                    player = self._pick_weakest(players)
                    attack = self._pick_attack(enemy)
                    hits = attack.get("hits", 1)
                    for _ in range(hits):
                        targets.append(
                            AttackTarget(
                                enemy_id=str(enemy["id"]),
                                enemy_name=enemy["display_name"],
                                enemy_slug=enemy["slug"],
                                attack_name=attack["name"],
                                attack_bonus=attack["attack_bonus"],
                                damage_dice=attack["damage"],
                                damage_type=attack.get("damage_type", "untyped"),
                                target_character_id=str(player["id"]),
                                target_character_name=player["name"],
                                is_group=False,
                            )
                        )
            else:
                logger.warning("Attack pattern desconhecido: '%s' — ignorando", pattern)

        return targets

    def roll_attacks(
        self,
        attack_targets: list[AttackTarget],
        player_ac_map: dict[str, int],
    ) -> list[AttackResolution]:
        """
        Rola d20 + attack_bonus vs AC para cada ataque.
        Retorna resultados com dano calculado.

        player_ac_map: {character_id: armor_class}
        """
        resolutions: list[AttackResolution] = []
        for t in attack_targets:
            ac = player_ac_map.get(t.target_character_id, 10)
            d20 = random.randint(1, 20)
            total = d20 + t.attack_bonus
            is_crit = d20 == 20
            hit = is_crit or total >= ac

            damage = 0
            breakdown = ""
            if hit:
                damage, breakdown = self._roll_damage(t.damage_dice, is_crit)

            resolutions.append(
                AttackResolution(
                    target=t,
                    attack_roll=total,
                    hit=hit,
                    damage=damage,
                    damage_breakdown=breakdown,
                    is_critical=is_crit,
                )
            )
        return resolutions

    # ─── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _pick_attack(enemy: dict) -> dict:
        """
        Seleciona qual ataque usar.
        Para multi-ataque usa o ataque principal (primeiro da lista).
        """
        attacks = enemy.get("attacks") or []
        if not attacks:
            # Fallback genérico
            return {
                "name": "Ataque",
                "attack_bonus": 3,
                "damage": "1d6",
                "damage_type": "slashing",
                "hits": 1,
            }
        # Usa o primeiro ataque (normalmente o mais forte)
        return attacks[0]

    @staticmethod
    def _pick_weakest(players: list[dict]) -> dict:
        """Retorna o jogador com menor HP atual."""
        return min(players, key=lambda p: p.get("hp_current", 999))

    @staticmethod
    def _roll_damage(damage_expr: str, is_crit: bool = False) -> tuple[int, str]:
        """
        Rola dano a partir de expressão como '2d6+3'.
        Crítico: dobra os dados (não o modificador).
        """
        m = re.match(
            r"^(?P<num>\d+)d(?P<sides>\d+)(?P<mod>[+-]\d+)?$",
            damage_expr.strip(),
            re.IGNORECASE,
        )
        if not m:
            # Valor fixo
            try:
                val = int(damage_expr.strip())
                return (val * 2 if is_crit else val), str(val)
            except ValueError:
                return 1, "1"

        num = int(m.group("num"))
        sides = int(m.group("sides"))
        modifier = int(m.group("mod") or "+0")

        dice_count = num * 2 if is_crit else num
        rolls = [random.randint(1, sides) for _ in range(dice_count)]
        total = sum(rolls) + modifier
        total = max(0, total)

        mod_str = f" + {modifier}" if modifier > 0 else (f" - {abs(modifier)}" if modifier < 0 else "")
        breakdown = f"{rolls}{mod_str} = {total}"
        if is_crit:
            breakdown = f"[CRÍTICO] {breakdown}"

        return total, breakdown


import re  # noqa: E402 (necessário para _roll_damage ser método estático com re.match)
