from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AttributesRequest(BaseModel):
    strength: int = Field(default=10, ge=1, le=30)
    dexterity: int = Field(default=10, ge=1, le=30)
    constitution: int = Field(default=10, ge=1, le=30)
    intelligence: int = Field(default=10, ge=1, le=30)
    wisdom: int = Field(default=10, ge=1, le=30)
    charisma: int = Field(default=10, ge=1, le=30)
    armor_class: int = Field(default=10, ge=0, le=30)
    initiative: int = Field(default=0, ge=-10, le=20)
    speed: int = Field(default=30, ge=0, le=200)


class CharacterCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    race: str = Field(..., min_length=1, max_length=100)
    class_: str = Field(..., alias="class", min_length=1, max_length=100)
    subclass: Optional[str] = Field(default=None, max_length=100)
    level: int = Field(default=1, ge=1, le=20)
    background: Optional[str] = Field(default=None, max_length=200)
    alignment: Optional[str] = Field(default=None, max_length=50)
    char_type: str = Field(default="player", pattern=r"^(player|npc|ai_companion)$")
    backstory: Optional[str] = Field(default=None, max_length=5000)
    appearance: Optional[str] = Field(default=None, max_length=2000)
    campaign_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    attributes: Optional[AttributesRequest] = None

    model_config = {"populate_by_name": True}


class CharacterUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    race: Optional[str] = Field(default=None, min_length=1, max_length=100)
    class_: Optional[str] = Field(default=None, alias="class", max_length=100)
    subclass: Optional[str] = Field(default=None, max_length=100)
    background: Optional[str] = Field(default=None, max_length=200)
    alignment: Optional[str] = Field(default=None, max_length=50)
    char_type: Optional[str] = Field(default=None, pattern=r"^(player|npc|ai_companion)$")
    backstory: Optional[str] = Field(default=None, max_length=5000)
    appearance: Optional[str] = Field(default=None, max_length=2000)
    campaign_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None

    model_config = {"populate_by_name": True}


class CharacterStatusUpdateRequest(BaseModel):
    hp_current: Optional[int] = Field(default=None, ge=0)
    hp_temp: Optional[int] = Field(default=None, ge=0)
    hp_max: Optional[int] = Field(default=None, ge=0)
    conditions: Optional[list[str]] = None
    spell_slots: Optional[dict[str, int]] = None
    exhaustion: Optional[int] = Field(default=None, ge=0, le=6)
    death_saves_success: Optional[int] = Field(default=None, ge=0, le=3)
    death_saves_failure: Optional[int] = Field(default=None, ge=0, le=3)

    @field_validator("conditions", mode="before")
    @classmethod
    def validate_conditions(cls, v: Any) -> Any:
        if v is not None and not isinstance(v, list):
            raise ValueError("conditions deve ser uma lista de strings")
        return v

    @field_validator("spell_slots", mode="before")
    @classmethod
    def validate_spell_slots(cls, v: Any) -> Any:
        if v is not None:
            for key, val in v.items():
                if not str(key).isdigit():
                    raise ValueError(
                        "As chaves de spell_slots devem ser números de nível (ex: '1', '2')"
                    )
                if not isinstance(val, int) or val < 0:
                    raise ValueError(
                        "Os valores de spell_slots devem ser inteiros não-negativos"
                    )
        return v


class InventoryItemCreateRequest(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=200)
    item_type: str = Field(default="misc", max_length=50)
    quantity: int = Field(default=1, ge=1)
    weight: float = Field(default=0.0, ge=0.0)
    value_gp: float = Field(default=0.0, ge=0.0)
    properties: dict[str, Any] = Field(default_factory=dict)
    equipped: bool = Field(default=False)


class AbilityCreateRequest(BaseModel):
    ability_name: str = Field(..., min_length=1, max_length=200)
    ability_type: str = Field(
        default="feature",
        pattern=r"^(spell|feature|action|bonus_action|reaction)$",
    )
    description: Optional[str] = Field(default=None, max_length=3000)
    spell_level: Optional[int] = Field(default=None, ge=0, le=9)
    uses_max: Optional[int] = Field(default=None, ge=1)
    recharge: Optional[str] = Field(
        default=None, pattern=r"^(short_rest|long_rest|dawn)$"
    )

    @model_validator(mode="after")
    def spell_must_have_level(self) -> "AbilityCreateRequest":
        if self.ability_type == "spell" and self.spell_level is None:
            raise ValueError("Magias (type='spell') devem ter spell_level definido")
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CharacterStatusResponse(BaseModel):
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

    model_config = {"from_attributes": True}


class CharacterAttributesResponse(BaseModel):
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

    model_config = {"from_attributes": True}


class InventoryItemResponse(BaseModel):
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

    model_config = {"from_attributes": True}


class AbilityResponse(BaseModel):
    id: UUID
    character_id: UUID
    ability_name: str
    ability_type: str
    description: Optional[str]
    spell_level: Optional[int]
    uses_max: Optional[int]
    uses_remaining: Optional[int]
    recharge: Optional[str]

    model_config = {"from_attributes": True}


class CharacterResponse(BaseModel):
    id: UUID
    name: str
    race: str
    character_class: str = Field(alias="class_")
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
    status: Optional[CharacterStatusResponse] = None
    attributes: Optional[CharacterAttributesResponse] = None
    inventory: list[InventoryItemResponse] = Field(default_factory=list)
    abilities: list[AbilityResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True, "populate_by_name": True}


class LevelUpResponse(BaseModel):
    character_id: UUID
    new_level: int
    new_proficiency_bonus: int
    message: str
