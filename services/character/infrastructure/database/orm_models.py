from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CharacterDB(Base):
    __tablename__ = "characters"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    race: Mapped[str] = mapped_column(String(100), nullable=False)
    class_: Mapped[str] = mapped_column("class", String(100), nullable=False)
    subclass: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    proficiency_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    background: Mapped[str | None] = mapped_column(String(200), nullable=True)
    alignment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    char_type: Mapped[str] = mapped_column(String(20), nullable=False, default="pc")
    backstory: Mapped[str | None] = mapped_column(Text, nullable=True)
    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    campaign_id: Mapped[UUID | None] = mapped_column(nullable=True)
    owner_id: Mapped[UUID | None] = mapped_column(nullable=True)
    is_alive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    status: Mapped["CharacterStatusDB"] = relationship(
        "CharacterStatusDB", back_populates="character", uselist=False, lazy="select"
    )
    attributes: Mapped["CharacterAttributesDB"] = relationship(
        "CharacterAttributesDB", back_populates="character", uselist=False, lazy="select"
    )
    inventory: Mapped[list["InventoryItemDB"]] = relationship(
        "InventoryItemDB", back_populates="character", lazy="select"
    )
    abilities: Mapped[list["AbilityDB"]] = relationship(
        "AbilityDB", back_populates="character", lazy="select"
    )


class CharacterStatusDB(Base):
    __tablename__ = "character_status"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    hp_max: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hp_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hp_temp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conditions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    spell_slots: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    exhaustion: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Banco usa JSONB: {"successes": 0, "failures": 0}
    death_saves: Mapped[dict] = mapped_column(JSON, nullable=False, default=lambda: {"successes": 0, "failures": 0})
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    character: Mapped["CharacterDB"] = relationship("CharacterDB", back_populates="status")


class CharacterAttributesDB(Base):
    __tablename__ = "character_attributes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    strength: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    dexterity: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    constitution: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    intelligence: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    wisdom: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    charisma: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    armor_class: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    initiative: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    speed: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    proficiency: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    saving_throws: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    skill_profs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    character: Mapped["CharacterDB"] = relationship(
        "CharacterDB", back_populates="attributes"
    )


class InventoryItemDB(Base):
    __tablename__ = "inventory_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False, default="misc")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    value_gp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    equipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ─── Campos de stats e raridade (Sprint 2 — Sistema de Combate) ──────────
    stat_bonuses: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # ex: {"strength":2,"armor_class":1,"attack_bonus":1,"damage_bonus":2,"max_hp":5}

    special_effects: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # ex: [{"trigger":"on_hit","effect":"1d6 fire damage"},
    #       {"trigger":"on_equip","effect":"advantage on stealth checks"}]

    rarity: Mapped[str] = mapped_column(String(20), nullable=False, default="common")
    # common | uncommon | rare | very_rare | legendary

    is_starting_item: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # True para os 6 itens gerados na criação do personagem

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Descrição narrativa do item (gerada pelo LLM)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    character: Mapped["CharacterDB"] = relationship("CharacterDB", back_populates="inventory")


class AbilityDB(Base):
    __tablename__ = "character_abilities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    ability_name: Mapped[str] = mapped_column(String(200), nullable=False)
    ability_type: Mapped[str] = mapped_column(String(50), nullable=False, default="feature")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    spell_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uses_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uses_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recharge: Mapped[str | None] = mapped_column(String(50), nullable=True)

    character: Mapped["CharacterDB"] = relationship("CharacterDB", back_populates="abilities")
