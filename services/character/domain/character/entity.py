from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from domain.character.value_objects import AbilityType, CharacterType, RechargeType


# ---------------------------------------------------------------------------
# Domain helper
# ---------------------------------------------------------------------------


def calc_proficiency_bonus(level: int) -> int:
    """D&D 5e proficiency bonus: 2 + (level-1)//4"""
    return 2 + (level - 1) // 4


# Dado de vida máximo por classe (D&D 5e) — aceita nomes em PT e EN
_HIT_DICE: dict[str, int] = {
    # Português
    "bárbaro": 12, "bardo": 8, "clérigo": 8, "druida": 8,
    "guerreiro": 10, "monge": 8, "paladino": 10, "patrulheiro": 10,
    "ladino": 8, "feiticeiro": 6, "bruxo": 8, "mago": 6,
    # Inglês
    "barbarian": 12, "bard": 8, "cleric": 8, "druid": 8,
    "fighter": 10, "monk": 8, "paladin": 10, "ranger": 10,
    "rogue": 8, "sorcerer": 6, "warlock": 8, "wizard": 6,
}


def calc_initial_hp(class_: str, constitution: int, level: int = 1) -> int:
    """HP inicial = dado de vida máximo + MOD CON (mínimo 10)."""
    hit_die = _HIT_DICE.get(class_.lower(), 8)  # padrão d8 se classe desconhecida
    con_mod = (constitution - 10) // 2
    hp = max(1, hit_die + con_mod)
    # Níveis acima de 1: usa metade do dado + 1 por nível extra
    for _ in range(level - 1):
        hp += max(1, (hit_die // 2 + 1) + con_mod)
    return max(10, hp)


# ---------------------------------------------------------------------------
# Sub-entities
# ---------------------------------------------------------------------------


@dataclass
class CharacterStatus:
    id: UUID
    character_id: UUID
    hp_max: int
    hp_current: int
    hp_temp: int
    conditions: list[str]
    spell_slots: dict[str, int]
    exhaustion: int
    death_saves_success: int
    death_saves_failure: int
    updated_at: datetime

    @classmethod
    def create_default(cls, character_id: UUID) -> "CharacterStatus":
        return cls(
            id=uuid4(),
            character_id=character_id,
            hp_max=0,
            hp_current=0,
            hp_temp=0,
            conditions=[],
            spell_slots={},
            exhaustion=0,
            death_saves_success=0,
            death_saves_failure=0,
            updated_at=datetime.utcnow(),
        )

    def apply_update(self, updates: dict[str, Any]) -> None:
        for field_name, value in updates.items():
            if hasattr(self, field_name):
                setattr(self, field_name, value)


@dataclass
class CharacterAttributes:
    id: UUID
    character_id: UUID
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    armor_class: int = 10
    initiative: int = 0
    speed: int = 30

    @classmethod
    def create_default(cls, character_id: UUID, **overrides: Any) -> "CharacterAttributes":
        return cls(id=uuid4(), character_id=character_id, **overrides)


@dataclass
class InventoryItem:
    id: UUID
    character_id: UUID
    item_name: str
    item_type: str
    quantity: int
    weight: float
    value_gp: float
    properties: dict[str, Any]
    equipped: bool
    created_at: datetime

    @classmethod
    def create(
        cls,
        character_id: UUID,
        item_name: str,
        item_type: str = "misc",
        quantity: int = 1,
        weight: float = 0.0,
        value_gp: float = 0.0,
        properties: Optional[dict[str, Any]] = None,
        equipped: bool = False,
    ) -> "InventoryItem":
        return cls(
            id=uuid4(),
            character_id=character_id,
            item_name=item_name,
            item_type=item_type,
            quantity=quantity,
            weight=weight,
            value_gp=value_gp,
            properties=properties or {},
            equipped=equipped,
            created_at=datetime.utcnow(),
        )


@dataclass
class Ability:
    id: UUID
    character_id: UUID
    ability_name: str
    ability_type: str
    description: Optional[str]
    spell_level: Optional[int]
    uses_max: Optional[int]
    uses_remaining: Optional[int]
    recharge: Optional[str]

    @classmethod
    def create(
        cls,
        character_id: UUID,
        ability_name: str,
        ability_type: str = AbilityType.FEATURE,
        description: Optional[str] = None,
        spell_level: Optional[int] = None,
        uses_max: Optional[int] = None,
        recharge: Optional[str] = None,
    ) -> "Ability":
        if ability_type == AbilityType.SPELL and spell_level is None:
            raise ValueError("Magias (type='spell') devem ter spell_level definido")
        return cls(
            id=uuid4(),
            character_id=character_id,
            ability_name=ability_name,
            ability_type=ability_type,
            description=description,
            spell_level=spell_level,
            uses_max=uses_max,
            uses_remaining=uses_max,  # initializes to max
            recharge=recharge,
        )


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


@dataclass
class Character:
    id: UUID
    name: str
    race: str
    class_: str
    subclass: Optional[str]
    level: int
    proficiency_bonus: int
    background: Optional[str]
    alignment: Optional[str]
    char_type: str
    backstory: Optional[str]
    appearance: Optional[str]
    campaign_id: Optional[UUID]
    owner_id: Optional[UUID]
    is_alive: bool
    created_at: datetime
    updated_at: datetime
    status: Optional[CharacterStatus] = None
    attributes: Optional[CharacterAttributes] = None
    inventory: list[InventoryItem] = field(default_factory=list)
    abilities: list[Ability] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        name: str,
        race: str,
        class_: str,
        level: int = 1,
        subclass: Optional[str] = None,
        background: Optional[str] = None,
        alignment: Optional[str] = None,
        char_type: str = CharacterType.PLAYER,
        backstory: Optional[str] = None,
        appearance: Optional[str] = None,
        campaign_id: Optional[UUID] = None,
        owner_id: Optional[UUID] = None,
    ) -> "Character":
        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            name=name,
            race=race,
            class_=class_,
            subclass=subclass,
            level=level,
            proficiency_bonus=calc_proficiency_bonus(level),
            background=background,
            alignment=alignment,
            char_type=char_type,
            backstory=backstory,
            appearance=appearance,
            campaign_id=campaign_id,
            owner_id=owner_id,
            is_alive=True,
            created_at=now,
            updated_at=now,
        )

    def soft_delete(self) -> None:
        self.is_alive = False

    def level_up(self) -> None:
        if self.level >= 20:
            raise ValueError("O personagem já atingiu o nível máximo (20).")
        self.level += 1
        self.proficiency_bonus = calc_proficiency_bonus(self.level)

    def apply_update(self, updates: dict[str, Any]) -> None:
        for field_name, value in updates.items():
            if hasattr(self, field_name):
                setattr(self, field_name, value)
