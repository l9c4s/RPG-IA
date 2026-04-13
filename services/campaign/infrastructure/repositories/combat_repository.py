"""
CombatRepository — CRUD para encontros, inimigos e eventos de combate.

Responsabilidades:
  - Criar/buscar combat_encounters por sessão
  - Spawnar instâncias de inimigos (combat_enemies) com HP rolado
  - Aplicar dano e matar inimigos
  - Buscar inimigos vivos por encontro
  - Registrar eventos de combate no log
  - Buscar/criar enemy_templates (catálogo global)
"""

from __future__ import annotations

import random
import re
import logging
from uuid import UUID, uuid4
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.orm_models import (
    CombatEncounterORM,
    CombatEnemyORM,
    CombatEventORM,
    EnemyTemplateORM,
)

logger = logging.getLogger(__name__)

# Regex para expressões de dados: "2d8", "3d6+4", "1d20-1"
_DICE_RE = re.compile(r"^(?P<num>\d+)d(?P<sides>\d+)(?P<mod>[+-]\d+)?$", re.IGNORECASE)

# Tabela XP por CR (D&D 5e SRD)
_XP_BY_CR: dict[float, int] = {
    0: 10, 0.125: 25, 0.25: 50, 0.5: 100,
    1: 200, 2: 450, 3: 700, 4: 1100, 5: 1800,
    6: 2300, 7: 2900, 8: 3900, 9: 5000, 10: 5900,
    11: 7200, 12: 8400, 13: 10000, 14: 11500, 15: 13000,
    16: 15000, 17: 18000, 18: 20000, 19: 22000, 20: 25000,
    21: 33000, 22: 41000, 23: 50000, 24: 62000, 25: 75000,
    30: 155000,
}


def _xp_for_cr(cr: float | None) -> int:
    """Retorna XP por Challenge Rating (D&D 5e). Fallback por HP se CR None."""
    if cr is None:
        return 50  # fallback: inimigo genérico sem CR definido
    # Busca exata ou arredonda para o CR mais próximo disponível
    if cr in _XP_BY_CR:
        return _XP_BY_CR[cr]
    # Interpola para o CR imediatamente abaixo
    for threshold in sorted(_XP_BY_CR.keys(), reverse=True):
        if cr >= threshold:
            return _XP_BY_CR[threshold]
    return 10


def _roll_dice(expr: str) -> int:
    """Rola uma expressão de dados e retorna o resultado."""
    m = _DICE_RE.match(expr.strip())
    if not m:
        # Tenta interpretar como número fixo
        try:
            return int(expr.strip())
        except ValueError:
            return 8  # fallback
    num = int(m.group("num"))
    sides = int(m.group("sides"))
    modifier = int(m.group("mod") or "+0")
    result = sum(random.randint(1, sides) for _ in range(num)) + modifier
    return max(1, result)


def _make_slug(name: str, index: int) -> str:
    """Gera slug único: 'Goblin Arqueiro' + 2 → 'goblin_arqueiro_2'."""
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"{base}_{index}"


class CombatRepository:
    """Repositório concreto para o sistema de combate."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ─── Encontros ───────────────────────────────────────────────────────────

    async def create_encounter(
        self,
        session_id: UUID,
        round_id: UUID | None = None,
        location_desc: str | None = None,
    ) -> CombatEncounterORM:
        """Cria um novo encontro de combate para a sessão."""
        encounter = CombatEncounterORM(
            id=uuid4(),
            session_id=session_id,
            round_id_start=round_id,
            status="active",
            location_desc=location_desc,
        )
        self._db.add(encounter)
        await self._db.flush()
        await self._db.refresh(encounter)
        return encounter

    async def get_active_encounter(self, session_id: UUID) -> CombatEncounterORM | None:
        """Retorna o encontro ativo da sessão, ou None se não houver combate."""
        result = await self._db.execute(
            select(CombatEncounterORM)
            .where(
                CombatEncounterORM.session_id == session_id,
                CombatEncounterORM.status == "active",
            )
            .order_by(CombatEncounterORM.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def resolve_encounter(self, encounter_id: UUID) -> None:
        """Marca o encontro como resolvido (todos os inimigos derrotados)."""
        orm = await self._db.get(CombatEncounterORM, encounter_id)
        if orm:
            orm.status = "resolved"
            orm.ended_at = datetime.now(timezone.utc)
            await self._db.flush()

    # ─── Templates de Inimigos ───────────────────────────────────────────────

    async def find_template_by_name(self, name: str) -> EnemyTemplateORM | None:
        """Busca template por nome exato (case-insensitive)."""
        result = await self._db.execute(
            select(EnemyTemplateORM).where(
                EnemyTemplateORM.name.ilike(f"%{name}%")
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def save_template(self, data: dict) -> EnemyTemplateORM:
        """Salva um novo template de inimigo no catálogo."""
        template = EnemyTemplateORM(
            id=uuid4(),
            name=data["name"],
            enemy_type=data.get("enemy_type", "humanoid"),
            size=data.get("size", "medium"),
            cr=data.get("cr", 1),
            hp_dice=data.get("hp_dice", "2d8"),
            armor_class=data.get("armor_class", 12),
            speed=data.get("speed", 30),
            strength=data.get("strength", 10),
            dexterity=data.get("dexterity", 10),
            constitution=data.get("constitution", 10),
            intelligence=data.get("intelligence", 3),
            wisdom=data.get("wisdom", 10),
            charisma=data.get("charisma", 5),
            attack_pattern=data.get("attack_pattern", "melee_single"),
            attacks=data.get("attacks", []),
            special_abilities=data.get("special_abilities", []),
            damage_immunities=data.get("damage_immunities", []),
            damage_resistances=data.get("damage_resistances", []),
            condition_immunities=data.get("condition_immunities", []),
            loot_table=data.get("loot_table", []),
            source=data.get("source", "generated"),
        )
        self._db.add(template)
        await self._db.flush()
        await self._db.refresh(template)
        return template

    # ─── Inimigos ────────────────────────────────────────────────────────────

    async def spawn_enemies(
        self,
        encounter_id: UUID,
        enemy_list: list[dict],
    ) -> list[CombatEnemyORM]:
        """
        Spawna uma lista de inimigos em um encontro.

        enemy_list: lista de dicts com campos do GM:
          [{"nome":"Goblin","tipo":"goblin","hp":7,"ca":13,"atk":4,"dano":"1d6+2"}]
          ou completo como template.

        Retorna instâncias criadas com slugs únicos.
        """
        spawned: list[CombatEnemyORM] = []

        # Conta quantos de cada nome já existem no encontro (para slugs únicos)
        name_counts: dict[str, int] = {}

        for raw in enemy_list:
            name = raw.get("nome") or raw.get("name", "Inimigo Desconhecido")
            enemy_type = raw.get("tipo") or raw.get("enemy_type", "humanoid")
            size = raw.get("size", "medium")
            attack_pattern = raw.get("attack_pattern", self._infer_pattern(enemy_type))

            # HP: usa valor fixo se fornecido, ou rola o dado
            hp_raw = raw.get("hp") or raw.get("hp_max")
            if isinstance(hp_raw, int):
                hp_max = max(1, hp_raw)
            elif isinstance(hp_raw, str):
                hp_max = max(1, _roll_dice(hp_raw))
            else:
                hp_max = max(1, _roll_dice(raw.get("hp_dice", "2d8")))

            ac = raw.get("ca") or raw.get("armor_class", 12)

            # Ataques: monta a partir dos campos simplificados do GM
            atk_bonus = raw.get("atk") or raw.get("attack_bonus", 3)
            damage_dice = raw.get("dano") or raw.get("damage", "1d6")
            damage_type = raw.get("damage_type", "slashing")
            attacks = raw.get("attacks") or [
                {
                    "name": "Ataque",
                    "attack_bonus": atk_bonus,
                    "damage": damage_dice,
                    "damage_type": damage_type,
                }
            ]

            # Slug único
            name_counts[name] = name_counts.get(name, 0) + 1
            idx = name_counts[name]
            slug = _make_slug(name, idx)
            display_name = f"{name} #{idx}" if idx > 1 else name

            # Loot rolado do template
            loot_rolled = self._roll_loot(raw.get("loot_table", []))

            enemy = CombatEnemyORM(
                id=uuid4(),
                encounter_id=encounter_id,
                template_id=raw.get("template_id"),
                name=name,
                slug=slug,
                display_name=display_name,
                enemy_type=enemy_type,
                size=size,
                hp_current=hp_max,
                hp_max=hp_max,
                armor_class=ac,
                attack_pattern=attack_pattern,
                attacks=attacks,
                special_abilities=raw.get("special_abilities", []),
                is_alive=True,
                conditions=[],
                strength=raw.get("strength", 10),
                dexterity=raw.get("dexterity", 10),
                constitution=raw.get("constitution", 10),
                loot_rolled=loot_rolled,
            )
            self._db.add(enemy)
            spawned.append(enemy)

        await self._db.flush()
        for e in spawned:
            await self._db.refresh(e)
        return spawned

    async def get_alive_enemies(self, encounter_id: UUID) -> list[CombatEnemyORM]:
        """Retorna todos os inimigos vivos em um encontro."""
        result = await self._db.execute(
            select(CombatEnemyORM)
            .where(
                CombatEnemyORM.encounter_id == encounter_id,
                CombatEnemyORM.is_alive == True,  # noqa: E712
            )
            .order_by(CombatEnemyORM.spawned_at.asc())
        )
        return list(result.scalars().all())

    async def get_all_enemies(self, encounter_id: UUID) -> list[CombatEnemyORM]:
        """Retorna todos os inimigos (vivos e mortos) de um encontro."""
        result = await self._db.execute(
            select(CombatEnemyORM)
            .where(CombatEnemyORM.encounter_id == encounter_id)
            .order_by(CombatEnemyORM.spawned_at.asc())
        )
        return list(result.scalars().all())

    async def find_enemy_by_slug(
        self, encounter_id: UUID, slug_hint: str
    ) -> CombatEnemyORM | None:
        """
        Busca inimigo por slug com match fuzzy.
        "goblin_1", "goblin1", "Goblin #1", "goblin" → goblin_1
        """
        # Normaliza o hint
        normalized = re.sub(r"[^a-z0-9]+", "_", slug_hint.lower()).strip("_")

        result = await self._db.execute(
            select(CombatEnemyORM).where(
                CombatEnemyORM.encounter_id == encounter_id,
                CombatEnemyORM.is_alive == True,  # noqa: E712
            )
        )
        enemies = list(result.scalars().all())

        # Match exato
        for e in enemies:
            if e.slug == normalized:
                return e

        # Match parcial: normalized está contido no slug ou vice-versa
        for e in enemies:
            if normalized in e.slug or e.slug.split("_")[0] in normalized:
                return e

        # Se só tem 1 inimigo vivo, retorna ele (contexto implícito)
        if len(enemies) == 1:
            return enemies[0]

        return None

    async def apply_damage_to_enemy(
        self, enemy_id: UUID, damage: int
    ) -> CombatEnemyORM:
        """
        Aplica dano a um inimigo. Se HP chegar a 0, mata o inimigo.
        Retorna o inimigo atualizado.
        """
        enemy = await self._db.get(CombatEnemyORM, enemy_id)
        if enemy is None:
            raise ValueError(f"Inimigo {enemy_id} não encontrado.")

        enemy.hp_current = max(0, enemy.hp_current - damage)
        if enemy.hp_current == 0:
            enemy.is_alive = False

        await self._db.flush()
        await self._db.refresh(enemy)
        return enemy

    async def get_kill_payload(
        self, enemy: CombatEnemyORM, killer_name: str
    ) -> dict:
        """
        Monta o payload completo de morte de um inimigo para broadcast WS.
        Inclui XP calculado por CR (do template, se houver) e loot rolado.
        """
        cr: float | None = None
        if enemy.template_id:
            template = await self._db.get(EnemyTemplateORM, enemy.template_id)
            if template and template.cr is not None:
                cr = float(template.cr)

        # Fallback de CR por HP máximo (inimigos gerados sem template)
        if cr is None:
            if enemy.hp_max <= 10:
                cr = 0.125
            elif enemy.hp_max <= 25:
                cr = 0.25
            elif enemy.hp_max <= 50:
                cr = 0.5
            elif enemy.hp_max <= 80:
                cr = 1
            else:
                cr = 2

        xp = _xp_for_cr(cr)
        loot = list(enemy.loot_rolled or [])

        return {
            "enemy_name": enemy.display_name,
            "enemy_type": enemy.enemy_type,
            "killer": killer_name,
            "xp_gained": xp,
            "loot": loot,
            "hp_max": enemy.hp_max,
            "cr": cr,
        }

    async def apply_condition(
        self, enemy_id: UUID, condition: str
    ) -> None:
        """Aplica uma condição a um inimigo (poisoned, prone, etc.)."""
        enemy = await self._db.get(CombatEnemyORM, enemy_id)
        if enemy and enemy.is_alive:
            conditions = list(enemy.conditions or [])
            if condition not in conditions:
                conditions.append(condition)
            enemy.conditions = conditions
            await self._db.flush()

    # ─── Eventos ─────────────────────────────────────────────────────────────

    async def log_event(
        self,
        encounter_id: UUID,
        event_type: str,
        round_id: UUID | None = None,
        **kwargs,
    ) -> CombatEventORM:
        """Registra um evento no log de combate."""
        event = CombatEventORM(
            id=uuid4(),
            encounter_id=encounter_id,
            round_id=round_id,
            event_type=event_type,
            source_type=kwargs.get("source_type"),
            source_name=kwargs.get("source_name"),
            source_id=kwargs.get("source_id"),
            target_type=kwargs.get("target_type"),
            target_name=kwargs.get("target_name"),
            target_id=kwargs.get("target_id"),
            is_group_attack=kwargs.get("is_group_attack", False),
            damage_dealt=kwargs.get("damage_dealt"),
            damage_type=kwargs.get("damage_type"),
            is_hit=kwargs.get("is_hit"),
            attack_roll=kwargs.get("attack_roll"),
            damage_roll=kwargs.get("damage_roll"),
            item_data=kwargs.get("item_data"),
            narrative=kwargs.get("narrative"),
        )
        self._db.add(event)
        await self._db.flush()
        return event

    # ─── Helpers privados ────────────────────────────────────────────────────

    @staticmethod
    def _infer_pattern(enemy_type: str) -> str:
        """
        Infere o padrão de ataque baseado no tipo de inimigo.
        Serve como fallback quando o template não especifica.
        """
        mapping = {
            "dragon": "breath_cone",
            "dragão": "breath_cone",
            "beast": "melee_single",
            "ooze": "melee_single",
            "swarm": "swarm",
            "undead": "melee_single",
            "construct": "melee_single",
            "fiend": "melee_single",
            "humanoid": "melee_single",
            "giant": "melee_single",
            "elemental": "melee_single",
            "fey": "melee_single",
            "monstrosity": "melee_single",
        }
        return mapping.get(enemy_type.lower(), "melee_single")

    @staticmethod
    def _roll_loot(loot_table: list[dict]) -> list[dict]:
        """Rola o loot de um inimigo baseado na sua tabela de loot."""
        rolled = []
        for entry in loot_table:
            chance = entry.get("chance", 1.0)
            if random.random() <= chance:
                qty_raw = entry.get("qty", 1)
                qty = _roll_dice(str(qty_raw)) if isinstance(qty_raw, str) else qty_raw
                rolled.append({
                    "item": entry.get("item", "Item desconhecido"),
                    "qty": qty,
                })
        return rolled

    def format_enemies_for_gm(self, enemies: list[CombatEnemyORM]) -> str:
        """
        Formata o estado dos inimigos vivos para injetar no prompt do GM.
        Ex: "Goblin #1 [slug: goblin_1]: 4/7 HP, CA 13 | Goblin #2 [slug: goblin_2]: 7/7 HP, CA 13"
        """
        if not enemies:
            return "Nenhum inimigo ativo."
        parts = []
        for e in enemies:
            hp_bar = f"{e.hp_current}/{e.hp_max} HP"
            conditions = f" ({', '.join(e.conditions)})" if e.conditions else ""
            parts.append(
                f"{e.display_name} [slug: {e.slug}]: {hp_bar}, CA {e.armor_class}{conditions}"
            )
        return " | ".join(parts)
