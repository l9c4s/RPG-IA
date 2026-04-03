from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID


# ---------------------------------------------------------------------------
# Input DTOs
# ---------------------------------------------------------------------------


@dataclass
class AttributesInputDTO:
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    armor_class: int = 10
    initiative: int = 0
    speed: int = 30


@dataclass
class CreateCharacterDTO:
    name: str
    race: str
    class_: str
    level: int = 1
    subclass: Optional[str] = None
    background: Optional[str] = None
    alignment: Optional[str] = None
    char_type: str = "player"
    backstory: Optional[str] = None
    appearance: Optional[str] = None
    campaign_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    attributes: Optional[AttributesInputDTO] = None


@dataclass
class UpdateCharacterDTO:
    name: Optional[str] = None
    race: Optional[str] = None
    class_: Optional[str] = None
    subclass: Optional[str] = None
    background: Optional[str] = None
    alignment: Optional[str] = None
    char_type: Optional[str] = None
    backstory: Optional[str] = None
    appearance: Optional[str] = None
    campaign_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None


@dataclass
class UpdateCharacterStatusDTO:
    hp_current: Optional[int] = None
    hp_temp: Optional[int] = None
    hp_max: Optional[int] = None
    conditions: Optional[list[str]] = None
    spell_slots: Optional[dict[str, int]] = None
    exhaustion: Optional[int] = None
    death_saves_success: Optional[int] = None
    death_saves_failure: Optional[int] = None


@dataclass
class AddInventoryItemDTO:
    character_id: UUID
    item_name: str
    item_type: str = "misc"
    quantity: int = 1
    weight: float = 0.0
    value_gp: float = 0.0
    properties: dict[str, Any] = field(default_factory=dict)
    equipped: bool = False


@dataclass
class AddAbilityDTO:
    character_id: UUID
    ability_name: str
    ability_type: str = "feature"
    description: Optional[str] = None
    spell_level: Optional[int] = None
    uses_max: Optional[int] = None
    recharge: Optional[str] = None


# ---------------------------------------------------------------------------
# Output DTOs
# ---------------------------------------------------------------------------


@dataclass
class CharacterStatusDTO:
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


@dataclass
class CharacterAttributesDTO:
    id: UUID
    character_id: UUID
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    armor_class: int
    initiative: int
    speed: int


@dataclass
class InventoryItemDTO:
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


@dataclass
class AbilityDTO:
    id: UUID
    character_id: UUID
    ability_name: str
    ability_type: str
    description: Optional[str]
    spell_level: Optional[int]
    uses_max: Optional[int]
    uses_remaining: Optional[int]
    recharge: Optional[str]


@dataclass
class CharacterDTO:
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
    status: Optional[CharacterStatusDTO] = None
    attributes: Optional[CharacterAttributesDTO] = None
    inventory: list[InventoryItemDTO] = field(default_factory=list)
    abilities: list[AbilityDTO] = field(default_factory=list)


@dataclass
class LevelUpDTO:
    character_id: UUID
    new_level: int
    new_proficiency_bonus: int
    message: str
